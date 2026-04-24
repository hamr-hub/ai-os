from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
import time
import json
import asyncio
import os
import random
import argparse

app = FastAPI()
STATE_FILE = "/tmp/ai_os_state.json"

def get_state():
    if not os.path.exists(STATE_FILE):
        return {"vllm": {"status": "stopped", "model": "unknown"}}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"vllm": {"status": "stopped", "model": "unknown"}}

def save_state(state):
    state["vllm"]["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

@app.on_event("startup")
async def startup_event():
    # Start a background task to check if we should transition from loading to active
    async def monitor_loading():
        while True:
            try:
                state = get_state()
                if state["vllm"]["status"] == "loading":
                    loading_start = state["vllm"].get("loading_start", time.time())
                    elapsed = time.time() - loading_start
                    
                    # Target loading time: 5-15s for mock (quicker for testing)
                    target = state["vllm"].get("loading_target_duration", 10)
                    
                    if elapsed >= target:
                        state["vllm"]["status"] = "active"
                        save_state(state)
                        print(f"DEBUG: Auto-transitioned to active after {elapsed:.1f}s")
            except Exception as e:
                print(f"Error in monitor_loading: {e}")
            await asyncio.sleep(1)
            
    asyncio.create_task(monitor_loading())

@app.get("/v1/models")
async def list_models():
    state = get_state()
    status = state["vllm"]["status"]
    
    if status == "stopped":
        raise HTTPException(status_code=503, detail="Service Unavailable")
    if status == "error":
        raise HTTPException(status_code=500, detail="Internal Server Error")
    if status == "loading":
        # Return 503 to simulate "not ready"
        raise HTTPException(status_code=503, detail="Model is loading")

    return {
        "object": "list",
        "data": [
            {
                "id": state["vllm"].get("model", "mock-model"),
                "object": "model",
                "created": int(time.time()),
                "owned_by": "vllm"
            }
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    state = get_state()
    status = state["vllm"]["status"]
    
    if status == "loading":
        raise HTTPException(status_code=503, detail="Model is loading")
    if status != "active":
        raise HTTPException(status_code=503, detail="Service Unavailable")

    body = await request.json()
    model = body.get("model", "mock-model")
    messages = body.get("messages", [])
    stream = body.get("stream", False)

    content = f"Mock response from {model}. Status: {status}."

    if stream:
        async def event_generator():
            words = content.split()
            for i, word in enumerate(words):
                chunk = {
                    "id": "chatcmpl-mock",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None if i < len(words)-1 else "stop"}]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.05)
            yield "data: [DONE]\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        return {
            "id": "chatcmpl-mock", "object": "chat.completion", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        }

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/v1/control")
async def control(request: Request):
    # Mock control endpoint for adjusting utilization
    body = await request.json()
    return {"status": "ok", "applied": body}

@app.post("/v1/cache/flush")
async def flush_cache():
    return {"status": "ok"}

@app.post("/v1/clear_cache")
async def clear_cache():
    return {"status": "ok"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)
