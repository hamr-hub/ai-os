"""Agent API Routes

Provides endpoints for AI agent interactions with tool calling support.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import asyncio
import json
import os

from tools.definitions import ToolRegistry
from tools.executor import ToolExecutor, ToolResult
from middleware.error_handler import ModelNotFoundException, ModelServiceUnavailableException


agent_router = APIRouter(prefix="/manage/agent")


def _session_mgr():
    import main as m
    return m.agent_session_manager


# Pydantic models for request/response
class AgentMessage(BaseModel):
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class AgentRequest(BaseModel):
    model: Optional[str] = None
    messages: List[AgentMessage]
    tools: Optional[List[str]] = Field(None, description="Tool categories to enable")
    max_iterations: int = Field(5, description="Maximum tool call iterations")
    stream: bool = Field(True, description="Enable streaming response")
    auto_confirm: bool = Field(False, description="Auto-confirm dangerous tools")


class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]


class ExecuteToolsRequest(BaseModel):
    calls: List[ToolCallRequest]
    auto_confirm: bool = False


def _scheduler():
    import main as m
    return m.scheduler


def _gpu_monitor():
    import main as m
    return m.gpu_monitor


def _metrics():
    import main as m
    return m.metrics


def _get_executor() -> ToolExecutor:
    """Get or create tool executor instance"""
    return ToolExecutor()


def _get_registry() -> ToolRegistry:
    """Get tool registry singleton"""
    return ToolRegistry()


@agent_router.get("/tools")
async def list_tools(categories: Optional[str] = None):
    """List all available tools or tools in specific categories"""
    registry = _get_registry()

    if categories:
        category_list = [c.strip() for c in categories.split(",")]
        tools = []
        for cat in category_list:
            tools.extend(registry.get_by_category(cat))
    else:
        tools = registry.get_all()

    return {
        "tools": [t.to_openai_function() for t in tools],
        "categories": registry.get_categories(),
        "count": len(tools)
    }


@agent_router.get("/tools/{tool_name}")
async def get_tool_info(tool_name: str):
    """Get detailed information about a specific tool"""
    registry = _get_registry()
    tool = registry.get(tool_name)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": [p.__dict__ for p in tool.parameters],
        "category": tool.category,
        "dangerous": tool.dangerous,
        "requires_confirmation": tool.requires_confirmation,
        "openai_schema": tool.to_openai_function()
    }


@agent_router.post("/execute")
async def execute_tool(request: ExecuteToolsRequest):
    """Execute one or more tool calls"""
    executor = _get_executor()

    calls = [{"name": c.name, "arguments": c.arguments} for c in request.calls]
    results = await executor.execute_batch(calls, request.auto_confirm)

    return {
        "results": [r.to_dict() for r in results],
        "success": all(r.success for r in results)
    }


@agent_router.post("/execute/{tool_name}")
async def execute_single_tool(tool_name: str, request: ToolCallRequest):
    """Execute a single tool call"""
    executor = _get_executor()

    result = await executor.execute(tool_name, request.arguments, request.auto_confirm)
    return result.to_dict()


@agent_router.get("/history")
async def get_execution_history(limit: int = 100):
    """Get tool execution history"""
    executor = _get_executor()
    return {
        "history": executor.get_history(limit),
        "statistics": executor.get_statistics()
    }


@agent_router.delete("/history")
async def clear_execution_history():
    """Clear tool execution history"""
    executor = _get_executor()
    executor.clear_history()
    return {"status": "success", "message": "History cleared"}


@agent_router.post("/chat")
async def agent_chat(request: Request, body: AgentRequest):
    """Agent chat endpoint with automatic tool execution

    This implements an agentic loop:
    1. Send user message to model with available tools
    2. If model returns tool calls, execute them
    3. Feed tool results back to model
    4. Repeat until model returns final response or max iterations
    """
    scheduler = _scheduler()
    registry = _get_registry()
    executor = _get_executor()

    model_name = body.model or scheduler.get_default_model()
    if not model_name:
        raise HTTPException(status_code=400, detail="No model specified and no default set")

    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    # Ensure model is running
    if not scheduler.is_model_running(model_name):
        success = await scheduler.start_model(model_name)
        if not success:
            raise ModelServiceUnavailableException(model_name, "Failed to start model")
        await asyncio.sleep(5)

    # Get tools for the request
    if body.tools:
        tools = registry.get_openai_tools(body.tools)
    else:
        tools = registry.get_openai_tools()

    vllm_port = scheduler.get_model_port(model_name)
    backend_url = f"http://localhost:{vllm_port}"
    vllm_model_name = scheduler.get_model_path(model_name) or model_name
    print(f"[DEBUG] model_name={model_name}, vllm_model_name={vllm_model_name}, backend_url={backend_url}")

    if body.stream:
        return StreamingResponse(
            _agent_stream(
                backend_url, vllm_model_name, body.messages, tools, executor,
                body.max_iterations, body.auto_confirm
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
    else:
        result = await _agent_completion(
            backend_url, vllm_model_name, body.messages, tools, executor,
            body.max_iterations, body.auto_confirm
        )
        return result


async def _agent_completion(
    backend_url: str,
    model_name: str,
    messages: List[AgentMessage],
    tools: List[Dict],
    executor: ToolExecutor,
    max_iterations: int,
    auto_confirm: bool
) -> Dict[str, Any]:
    """Non-streaming agent completion with tool calling loop"""
    import httpx

    client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    openai_messages = _convert_messages(messages)
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        payload = {
            "model": model_name,
            "messages": openai_messages,
            "tools": tools,
            "tool_choice": "auto",
            "max_tokens": 2048
        }

        try:
            response = await client.post(f"{backend_url}/v1/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            return {"error": f"Model API error: {str(e)}"}

        message = data.get("choices", [{}])[0].get("message", {})
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            # No more tool calls, return final response
            return {
                "id": data.get("id"),
                "model": model_name,
                "message": message,
                "iterations": iteration,
                "finished": True
            }

        # Add assistant message with tool calls to history
        openai_messages.append(message)

        # Execute tool calls
        calls = []
        for tc in tool_calls:
            args = tc.get("function", {}).get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append({
                "name": tc.get("function", {}).get("name"),
                "arguments": args,
                "id": tc.get("id")
            })

        results = await executor.execute_batch(
            [{"name": c["name"], "arguments": c["arguments"]} for c in calls],
            auto_confirm
        )

        # Add tool results to messages
        for call, result in zip(calls, results):
            openai_messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result.result) if result.success else json.dumps({"error": result.error})
            })

    return {"error": "Max iterations reached", "iterations": iteration}


async def _agent_stream(
    backend_url: str,
    model_name: str,
    messages: List[AgentMessage],
    tools: List[Dict],
    executor: ToolExecutor,
    max_iterations: int,
    auto_confirm: bool
):
    """Streaming agent completion with tool calling loop"""
    import httpx

    client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0))
    openai_messages = _convert_messages(messages)
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # First get non-streaming response to check for tool calls
        payload = {
            "model": model_name,
            "messages": openai_messages,
            "tools": tools,
            "tool_choice": "auto",
            "max_tokens": 2048
        }

        try:
            response = await client.post(f"{backend_url}/v1/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        message = data.get("choices", [{}])[0].get("message", {})
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            # Stream the final response
            payload["stream"] = True
            async with client.stream("POST", f"{backend_url}/v1/chat/completions", json=payload) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        yield f"{line}\n\n"
            return

        # Notify about tool calls
        yield f"data: {json.dumps({'type': 'tool_calls_start', 'calls': len(tool_calls)})}\n\n"

        # Add assistant message to history
        openai_messages.append(message)

        # Execute tools and stream results
        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "unknown")
            args_str = func.get("arguments", "{}")
            tc_id = tc.get("id")

            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {}

            # Notify tool execution
            yield f"data: {json.dumps({'type': 'tool_executing', 'name': name, 'id': tc_id})}\n\n"

            result = await executor.execute(name, args, auto_confirm)

            # Send tool result
            yield f"data: {json.dumps({'type': 'tool_result', 'name': name, 'id': tc_id, 'success': result.success, 'result': result.result if result.success else None, 'error': result.error})}\n\n"

            # Add to message history
            openai_messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": json.dumps(result.result) if result.success else json.dumps({"error": result.error})
            })

        yield f"data: {json.dumps({'type': 'tool_calls_end', 'calls': len(tool_calls), 'iteration': iteration})}\n\n"

    yield f"data: {json.dumps({'error': 'Max iterations reached'})}\n\n"


def _convert_messages(messages: List[AgentMessage]) -> List[Dict]:
    """Convert AgentMessage list to OpenAI format"""
    result = []
    for msg in messages:
        item = {"role": msg.role, "content": msg.content}
        if msg.tool_calls:
            item["tool_calls"] = msg.tool_calls
        if msg.tool_call_id:
            item["tool_call_id"] = msg.tool_call_id
        if msg.name:
            item["name"] = msg.name
        result.append(item)
    return result


# ===== Session Management =====

class CreateSessionRequest(BaseModel):
    title: str = Field("", description="Session title")
    model: Optional[str] = Field(None, description="Model to use")


class AddMessageRequest(BaseModel):
    role: str = Field(..., description="Message role")
    content: str = Field(..., description="Message content")


@agent_router.post("/sessions")
async def create_session(request: CreateSessionRequest):
    mgr = _session_mgr()
    session = mgr.create_session(title=request.title, model=request.model)
    return session.to_dict()


@agent_router.get("/sessions")
async def list_sessions(archived: Optional[bool] = None):
    mgr = _session_mgr()
    return {"sessions": mgr.list_sessions(archived=archived), "total": len(mgr.list_sessions(archived=archived))}


@agent_router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    mgr = _session_mgr()
    session = mgr.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict_full()


@agent_router.post("/sessions/{session_id}/messages")
async def add_session_message(session_id: str, request: AddMessageRequest):
    mgr = _session_mgr()
    session = mgr.add_message(session_id, request.role, request.content)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


@agent_router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, limit: int = 100):
    mgr = _session_mgr()
    messages = mgr.get_session_messages(session_id, limit)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"messages": messages, "session_id": session_id}


@agent_router.delete("/sessions/{session_id}/messages")
async def clear_session_messages(session_id: str):
    mgr = _session_mgr()
    if not mgr.clear_session_messages(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success", "message": "Messages cleared"}


@agent_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    mgr = _session_mgr()
    if not mgr.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success", "session_id": session_id}


@agent_router.post("/sessions/{session_id}/archive")
async def archive_session(session_id: str):
    mgr = _session_mgr()
    session = mgr.archive_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()
