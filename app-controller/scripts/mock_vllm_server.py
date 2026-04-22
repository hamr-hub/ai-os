#!/usr/bin/env python3
"""
Mock vLLM Server - 模拟 vLLM API 接口
支持 /v1/chat/completions、/v1/models、/health 等接口
"""

import asyncio
import json
import time
import uuid
from typing import AsyncGenerator, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import argparse
import uvicorn

app = FastAPI(title="Mock vLLM Server", version="1.0.0")

MOCK_MODELS = [
    {"id": "mock-model-1", "object": "model", "owned_by": "mock-org", "permission": []},
    {"id": "mock-model-2", "object": "model", "owned_by": "mock-org", "permission": []},
    {"id": "Gemma-4-31B-Abliterated", "object": "model", "owned_by": "mock-org", "permission": []},
    {"id": "Qwen3-235B-A22B-Instruct-2507-AWQ", "object": "model", "owned_by": "mock-org", "permission": []},
]

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "mock-model-1"
    messages: List[Message]
    stream: bool = False
    max_tokens: Optional[int] = 100
    temperature: Optional[float] = 0.7

def generate_mock_response(request: ChatCompletionRequest) -> Dict:
    """生成 Mock 响应"""
    chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())
    
    mock_content = f"Mock response from {request.model}: Hello! This is a test response."
    
    return {
        "id": chat_id,
        "object": "chat.completion",
        "created": created,
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": mock_content
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 15,
            "total_tokens": 25
        }
    }

async def generate_mock_stream(request: ChatCompletionRequest) -> AsyncGenerator[str, None]:
    """生成 Mock 流式响应"""
    chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())
    
    mock_words = ["Mock", " response", " from", f" {request.model}:", " Hello!", " This", " is", " a", " test", " response."]
    
    for i, word in enumerate(mock_words):
        chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": request.model,
            "choices": [{
                "index": 0,
                "delta": {
                    "content": word
                },
                "finish_reason": None if i < len(mock_words) - 1 else "stop"
            }]
        }
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.1)
    
    yield "data: [DONE]\n\n"

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "mock-vllm-server"}

@app.get("/v1/models")
async def list_models():
    """列出模型"""
    return {
        "object": "list",
        "data": MOCK_MODELS
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """聊天补全接口"""
    if request.stream:
        return StreamingResponse(
            generate_mock_stream(request),
            media_type="text/event-stream"
        )
    else:
        return JSONResponse(content=generate_mock_response(request))

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Mock vLLM Server is running",
        "version": "1.0.0",
        "endpoints": ["/health", "/v1/models", "/v1/chat/completions"]
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock vLLM Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()
    
    print(f"🚀 Starting Mock vLLM Server on {args.host}:{args.port}")
    print(f"📋 Available endpoints:")
    print(f"   - GET  /health")
    print(f"   - GET  /v1/models")
    print(f"   - POST /v1/chat/completions")
    
    uvicorn.run(app, host=args.host, port=args.port)
