"""Tool Executor for Agent System

Handles the execution of tool calls with proper error handling and logging.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import asyncio
import json
import logging
from datetime import datetime

from tools.definitions import ToolRegistry, ToolDefinition


logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result of a tool execution"""
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp
        }


class ToolExecutor:
    """Executes tool calls from agents"""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry()
        self._execution_history: List[ToolResult] = []
        self._max_history = 1000

    async def execute(self, tool_name: str, arguments: Dict[str, Any],
                     auto_confirm: bool = False) -> ToolResult:
        """Execute a tool with the given arguments

        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            auto_confirm: If True, skip confirmation for dangerous tools

        Returns:
            ToolResult with execution result or error
        """
        start_time = datetime.now()

        # Get tool definition
        tool = self.registry.get(tool_name)
        if not tool:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=f"Tool '{tool_name}' not found"
            )

        # Check if confirmation is required
        if tool.requires_confirmation and not auto_confirm:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=f"Tool '{tool_name}' requires user confirmation"
            )

        try:
            # Validate arguments
            validated_args = self._validate_arguments(tool, arguments)
            if validated_args is None:
                return ToolResult(
                    tool_name=tool_name,
                    success=False,
                    result=None,
                    error="Invalid arguments"
                )

            # Execute the tool handler
            if tool.handler:
                result = await tool.handler(**validated_args)
            else:
                # Use default implementation
                result = await self._default_handler(tool_name, validated_args)

            execution_time = (datetime.now() - start_time).total_seconds()

            tool_result = ToolResult(
                tool_name=tool_name,
                success=True,
                result=result,
                execution_time=execution_time
            )

            self._add_to_history(tool_result)
            return tool_result

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Tool execution failed: {tool_name} - {str(e)}")

            tool_result = ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=str(e),
                execution_time=execution_time
            )

            self._add_to_history(tool_result)
            return tool_result

    def _validate_arguments(self, tool: ToolDefinition,
                          arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate and prepare arguments for tool execution"""
        validated = {}

        for param in tool.parameters:
            value = arguments.get(param.name, param.default)

            # Check required parameters
            if param.required and value is None:
                logger.warning(f"Missing required parameter: {param.name}")
                return None

            # Skip if not provided and not required
            if value is None:
                continue

            # Type conversion and validation
            try:
                if param.type == "string":
                    validated[param.name] = str(value)
                elif param.type == "integer":
                    validated[param.name] = int(value)
                    if param.min_value is not None and validated[param.name] < param.min_value:
                        return None
                    if param.max_value is not None and validated[param.name] > param.max_value:
                        return None
                elif param.type == "number":
                    validated[param.name] = float(value)
                    if param.min_value is not None and validated[param.name] < param.min_value:
                        return None
                    if param.max_value is not None and validated[param.name] > param.max_value:
                        return None
                elif param.type == "boolean":
                    validated[param.name] = bool(value)
                elif param.type == "array":
                    if isinstance(value, list):
                        validated[param.name] = value
                    elif isinstance(value, str):
                        validated[param.name] = json.loads(value)
                    else:
                        return None
                elif param.type == "object":
                    if isinstance(value, dict):
                        validated[param.name] = value
                    elif isinstance(value, str):
                        validated[param.name] = json.loads(value)
                    else:
                        return None

                # Enum validation
                if param.enum and validated[param.name] not in param.enum:
                    logger.warning(f"Invalid enum value: {validated[param.name]}")
                    return None

            except (ValueError, TypeError, json.JSONDecodeError) as e:
                logger.warning(f"Parameter validation failed: {param.name} - {str(e)}")
                return None

        return validated

    async def _default_handler(self, tool_name: str,
                              arguments: Dict[str, Any]) -> Any:
        """Default handler for tools without custom handlers

        This provides basic implementations for common tools.
        """
        import main as app_module

        if tool_name == "get_system_info":
            gpu_monitor = app_module.gpu_monitor
            scheduler = app_module.scheduler

            gpu_status = gpu_monitor.get_gpu_status() if gpu_monitor else None
            models = scheduler.get_available_models() if scheduler else []
            running_models = [m for m in models if scheduler.is_model_running(m)] if scheduler else []

            return {
                "gpu": gpu_status,
                "models": {
                    "total": len(models),
                    "running": len(running_models),
                    "list": running_models
                },
                "timestamp": datetime.now().isoformat()
            }

        elif tool_name == "list_models":
            scheduler = app_module.scheduler
            if not scheduler:
                return {"error": "Scheduler not available"}

            models = scheduler.get_available_models()
            model_list = []
            for m in models:
                config = scheduler.get_model_config(m)
                model_list.append({
                    "name": m,
                    "running": scheduler.is_model_running(m),
                    "description": config.get("description", "") if config else "",
                    "supports_images": scheduler.get_model_supports_images(m)
                })

            return {"models": model_list, "count": len(model_list)}

        elif tool_name == "get_gpu_status":
            gpu_monitor = app_module.gpu_monitor
            if not gpu_monitor:
                return {"error": "GPU monitor not available"}

            status = gpu_monitor.get_gpu_status()
            return status or {"error": "No GPU detected"}

        elif tool_name in ("start_model", "stop_model", "switch_model"):
            scheduler = app_module.scheduler
            if not scheduler:
                return {"error": "Scheduler not available"}

            model_name = arguments.get("model_name")
            if not model_name:
                return {"error": "model_name is required"}

            if tool_name == "start_model":
                if scheduler.is_model_running(model_name):
                    return {"status": "already_running", "model": model_name}
                success = await scheduler.start_model(model_name)
                return {
                    "status": "started" if success else "failed",
                    "model": model_name
                }

            elif tool_name == "stop_model":
                if not scheduler.is_model_running(model_name):
                    return {"status": "already_stopped", "model": model_name}
                success = await scheduler.stop_model(model_name)
                return {
                    "status": "stopped" if success else "failed",
                    "model": model_name
                }

            elif tool_name == "switch_model":
                success = await scheduler.switch_model(model_name)
                return {
                    "status": "switched" if success else "failed",
                    "model": model_name
                }

        elif tool_name == "optimize_gpu_memory":
            scheduler = app_module.scheduler
            if not scheduler:
                return {"error": "Scheduler not available"}

            strategy = arguments.get("strategy", "balanced")
            # Try to call optimize_memory if available
            if hasattr(scheduler, 'optimize_memory'):
                result = await scheduler.optimize_memory(strategy)
                return result
            else:
                # Fallback: flush cache
                if hasattr(scheduler, 'flush_cache'):
                    await scheduler.flush_cache()
                return {"status": "optimized", "strategy": strategy}

        elif tool_name == "get_vllm_metrics":
            vllm_metrics = getattr(app_module, 'vllm_metrics_scraper', None)
            if not vllm_metrics:
                return {"error": "vLLM metrics scraper not available"}
            try:
                metrics = vllm_metrics.scrape_metrics()
                return metrics or {"error": "vLLM service not running"}
            except Exception as e:
                return {"error": f"Failed to scrape vLLM metrics: {e}"}

        elif tool_name == "restart_vllm_service":
            orchestrator = getattr(app_module, 'model_switch_orchestrator', None)
            if not orchestrator:
                return {"error": "Model switch orchestrator not available"}
            model_name = arguments.get("model_name")
            try:
                result = await orchestrator.start(model_name)
                return {"status": "restarted", "model": model_name, "result": result}
            except Exception as e:
                return {"error": f"Failed to restart vLLM service: {e}"}

        elif tool_name == "get_engine_status":
            engine_scheduler = getattr(app_module, 'model_engine_scheduler', None)
            if not engine_scheduler:
                return {"error": "Engine scheduler not available"}
            try:
                status = engine_scheduler.get_scheduler_status()
                return status
            except Exception as e:
                return {"error": f"Failed to get engine status: {e}"}

        elif tool_name == "switch_engine":
            engine_scheduler = getattr(app_module, 'model_engine_scheduler', None)
            if not engine_scheduler:
                return {"error": "Engine scheduler not available"}
            engine_type = arguments.get("engine_type")
            model_name = arguments.get("model_name")
            if not engine_type:
                return {"error": "engine_type is required"}
            try:
                result = await engine_scheduler.switch_engine(engine_type, model_name)
                return {"status": "switched", "engine": engine_type, "model": model_name, "result": result}
            except Exception as e:
                return {"error": f"Failed to switch engine: {e}"}

        else:
            return {"error": f"No handler for tool: {tool_name}"}

    def _add_to_history(self, result: ToolResult) -> None:
        """Add result to execution history"""
        self._execution_history.append(result)
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history"""
        return [r.to_dict() for r in self._execution_history[-limit:]]

    def clear_history(self) -> None:
        """Clear execution history"""
        self._execution_history.clear()

    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics"""
        if not self._execution_history:
            return {
                "total_executions": 0,
                "successful": 0,
                "failed": 0,
                "average_time": 0.0
            }

        successful = sum(1 for r in self._execution_history if r.success)
        total_time = sum(r.execution_time for r in self._execution_history)

        return {
            "total_executions": len(self._execution_history),
            "successful": successful,
            "failed": len(self._execution_history) - successful,
            "average_time": total_time / len(self._execution_history),
            "tools_used": list(set(r.tool_name for r in self._execution_history))
        }

    async def execute_batch(self, calls: List[Dict[str, Any]],
                           auto_confirm: bool = False) -> List[ToolResult]:
        """Execute multiple tool calls in sequence

        Args:
            calls: List of dicts with 'name' and 'arguments' keys
            auto_confirm: Skip confirmation for dangerous tools

        Returns:
            List of ToolResult objects
        """
        results = []
        for call in calls:
            name = call.get("name") or call.get("function", {}).get("name")
            arguments = call.get("arguments") or call.get("function", {}).get("arguments", {})

            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}

            if name:
                result = await self.execute(name, arguments, auto_confirm)
                results.append(result)

        return results
