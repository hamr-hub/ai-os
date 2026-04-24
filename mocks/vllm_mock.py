from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
import time
import json
import asyncio
import os
import random

app = FastAPI()
STATE_FILE = "/tmp/ai_os_state.json"

def get_state():
    if not os.path.exists(STATE_FILE):
        return {"vllm": {"status": "stopped", "model": "unknown"}}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    state["vllm"]["last_update"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

async def loading_process():
    # Simulate model loading time 20-60s
    loading_time = random.randint(20, 60)
    print(f"DEBUG: Starting loading process, will take {loading_time}s")
    await asyncio.sleep(loading_time)
    
    state = get_state()
    if state["vllm"]["status"] == "loading":
        state["vllm"]["status"] = "active"
        save_state(state)
        print("DEBUG: Loading complete, status set to active")

@app.on_event("startup")
async def startup_event():
    # Start a background task to check if we should transition from loading to active
    async def monitor_loading():
        while True:
            state = get_state()
            if state["vllm"]["status"] == "loading":
                # If we just entered loading state and no background task is tracked (simulated)
                # For mock simplicity, we just wait and transition
                loading_start = state["vllm"].get("loading_start", time.time())
                elapsed = time.time() - loading_start
                # We use a fixed target for this mock loop or random one stored
                target = state["vllm"].get("loading_target_duration", random.randint(20, 40))
                if "loading_target_duration" not in state["vllm"]:
                    state["vllm"]["loading_target_duration"] = target
                    save_state(state)
                
                if elapsed >= target:
                    state["vllm"]["status"] = "active"
                    save_state(state)
                    print(f"DEBUG: Auto-transitioned to active after {elapsed:.1f}s")
            await asyncio.sleep(2)
            
    asyncio.create_task(monitor_loading())

@app.get("/v1/models")
async def list_models():
    state = get_state()
    status = state["vllm"]["status"]
    
    if status == "stopped":
        raise HTTPException(status_code=503, detail="Service Unavailable")
    if status == "error":
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
    # Even if loading, some vLLM versions might return models or 503
    # We'll return 503 during loading to simulate "not ready"
    if status == "loading":
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

@app.post("/mock/set_state")
async def set_mock_state(request: Request):
    new_vllm_state = await request.json()
    state = get_state()
    state["vllm"].update(new_vllm_state)
    if new_vllm_state.get("status") == "loading":
        state["vllm"]["loading_start"] = time.time()
        state["vllm"].pop("loading_target_duration", None)
    save_state(state)
    return state

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
