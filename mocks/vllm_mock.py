from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import time
import json
import os
import sys
import argparse

# Add current dir to path to import StateManager
sys.path.append(os.path.dirname(__file__))
from state_manager import StateManager

app = FastAPI()

@app.get("/v1/models")
async def list_models():
    StateManager.update_vllm_status()
    state = StateManager.get_state()
    status = state["vllm"]["status"]
    
    if status == "stopped":
        raise HTTPException(status_code=503, detail="Service Unavailable")
    if status == "error":
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {state['vllm'].get('error')}")
    if status == "loading":
        raise HTTPException(status_code=503, detail="Model is loading")

    return {
        "object": "list",
        "data": [
            {
                "id": state["vllm"].get("current_model", "mock-model"),
                "object": "model",
                "created": int(time.time()),
                "owned_by": "vllm"
            }
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    StateManager.update_vllm_status()
    state = StateManager.get_state()
    status = state["vllm"]["status"]
    
    if status == "loading":
        raise HTTPException(status_code=503, detail="Model is loading")
    if status != "active":
        raise HTTPException(status_code=503, detail="Service Unavailable")

    body = await request.json()
    model = body.get("model", "mock-model")
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
    body = await request.json()
    state = StateManager.get_state()
    # Allow adjusting fault injection from control API
    if "faults" in body:
        state["faults"].update(body["faults"])
    StateManager.save_state(state)
    return {"status": "ok", "applied": body}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port)
