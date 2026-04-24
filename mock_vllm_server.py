import json
import math
import random
import time
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Mock vLLM API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATE_FILE = "/tmp/ai_os_state.json"

MOCK_MODELS = {
    "Gemma-4-31B-Abliterated": {
        "running": True,
        "status": "running",
        "port": 8000,
        "service": "vllm-aiclient",
        "active_requests": 3,
        "preloaded": True,
        "last_used": datetime.now().isoformat(),
        "supports_images": True,
        "supports_tool_calling": False,
        "supports_image_generation": False,
        "description": "Gemma 4 31B Abliterated",
        "required_memory": "16GB",
        "backend_type": "vllm",
    },
    "Qwen3.6-35B": {
        "running": False,
        "status": "stopped",
        "port": None,
        "service": "vllm-aiclient",
        "active_requests": 0,
        "preloaded": False,
        "last_used": None,
        "supports_images": True,
        "supports_tool_calling": True,
        "supports_image_generation": False,
        "description": "Qwen 3.6 35B",
        "required_memory": "20GB",
        "backend_type": "vllm",
    },
    "DeepSeek-V3-0324": {
        "running": False,
        "status": "stopped",
        "port": None,
        "service": "vllm-aiclient",
        "active_requests": 0,
        "preloaded": False,
        "last_used": None,
        "supports_images": False,
        "supports_tool_calling": True,
        "supports_image_generation": False,
        "description": "DeepSeek V3 0324",
        "required_memory": "24GB",
        "backend_type": "vllm",
    },
}

# 运行时状态转换追踪
model_loading_state = {
    "current_model": "Gemma-4-31B-Abliterated",
    "target_model": None,
    "start_time": None,
    "duration": 0,
    "error_triggered": False
}

def update_external_state():
    """同步状态到文件供 nvidia-smi mock 使用"""
    status = "stopped"
    running_model = None
    for name, info in MOCK_MODELS.items():
        if info["running"]:
            if info["status"] == "loading":
                status = "loading"
            else:
                status = "active"
            running_model = name
            break
            
    state = {
        "vllm": {
            "status": status,
            "model": running_model,
            "vram_used_mb": 22000 if status == "active" else (12000 if status == "loading" else 450)
        },
        "gpu": {
            "name": "NVIDIA GeForce RTX 4090",
            "vram_total_mb": 24576,
            "temperature": 55 if status == "active" else (65 if status == "loading" else 42),
            "utilization": 5 if status == "active" else (85 if status == "loading" else 0)
        }
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def check_loading_transitions():
    """检查并处理模型加载状态转换"""
    if model_loading_state["target_model"] and model_loading_state["start_time"]:
        elapsed = (datetime.now() - model_loading_state["start_time"]).total_seconds()
        target = model_loading_state["target_model"]
        
        # 模拟随机加载失败 (如 5% 概率 OOM)
        if not model_loading_state["error_triggered"] and elapsed > 15 and random.random() < 0.05:
            model_loading_state["error_triggered"] = True
            MOCK_MODELS[target]["status"] = "error"
            MOCK_MODELS[target]["error_message"] = "Out of Memory during weights loading"
            MOCK_MODELS[target]["running"] = False
            update_external_state()
            return

        if elapsed >= model_loading_state["duration"]:
            # 加载完成
            MOCK_MODELS[target]["status"] = "running"
            MOCK_MODELS[target]["running"] = True
            MOCK_MODELS[target]["port"] = 8000
            model_loading_state["current_model"] = target
            model_loading_state["target_model"] = None
            model_loading_state["start_time"] = None
            update_external_state()

DEFAULT_MODEL = "Gemma-4-31B-Abliterated"
update_external_state()

def _gpu_point(ts_offset: int) -> dict:
    now = datetime.now() - timedelta(seconds=ts_offset)
    
    # 根据历史偏移决定当时的状态（简化模拟：历史假设是稳定的）
    state = "active" # Default for history
    
    # 只有当前时间点(ts_offset=0)才考虑实时加载状态
    if ts_offset == 0:
        check_loading_transitions()
        state = "idle"
        for m in MOCK_MODELS.values():
            if m["running"]:
                state = "active" if m["status"] == "running" else "loading"
                break
            
    if state == "loading":
        base_util = 85 + random.uniform(-5, 5)
        base_temp = 68 + random.uniform(-2, 2)
        base_mem_util = 45 + random.uniform(-5, 5)
        base_power = 350 + random.uniform(-20, 20)
    elif state == "active":
        base_util = 5 + 15 * abs(math.sin(ts_offset / 60))
        base_temp = 55 + 5 * math.sin(ts_offset / 90)
        base_mem_util = 88 + random.uniform(-1, 1)
        base_power = 150 + 40 * math.sin(ts_offset / 70)
    else:
        base_util = 0.5
        base_temp = 42
        base_mem_util = 2.0
        base_power = 30

    return {
        "timestamp": now.isoformat(),
        "utilization": round(base_util, 1),
        "temperature": round(base_temp, 1),
        "power_draw": round(base_power, 1),
        "power_percent": round(base_power / 450 * 100, 1),
        "memory_utilization": round(base_mem_util, 1),
        "used_memory": round((base_mem_util / 100) * 24576 * 1024 * 1024),
        "available_memory": round((1 - base_mem_util / 100) * 24576 * 1024 * 1024),
        "total_memory": 24576 * 1024 * 1024,
        "fan_speed": round(30 + base_temp/2),
        "clock_sm": round(2100 if state != "idle" else 300),
        "clock_mem": round(10501 if state != "idle" else 400),
    }

def _system_point(ts_offset: int) -> dict:
    now = datetime.now() - timedelta(seconds=ts_offset)
    base_cpu = 35 + 10 * math.sin(ts_offset / 50)
    base_mem = 58 + 5 * math.sin(ts_offset / 40)
    return {
        "timestamp": now.isoformat(),
        "cpu_percent": round(base_cpu + random.uniform(-2, 2), 1),
        "memory_percent": round(base_mem + random.uniform(-1, 1), 1),
    }

def _token_point(ts_offset: int) -> dict:
    now = datetime.now() - timedelta(seconds=ts_offset)
    prompt = random.randint(500, 3000)
    completion = random.randint(200, 1500)
    return {
        "timestamp": now.isoformat(),
        "total_tokens": prompt + completion,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "models": {
            model_loading_state["current_model"]: {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion},
        },
    }

@app.get("/health")
async def health():
    check_loading_transitions()
    return {"status": "ok"}

@app.get("/manage/gpu/summary")
async def gpu_summary():
    check_loading_transitions()
    current = _gpu_point(0)
    current["name"] = "NVIDIA GeForce RTX 4090"
    current["gpu_count"] = 1
    history = [_gpu_point(i * 10) for i in range(60)]
    return {"status": "available", "current": current, "history": history}

@app.get("/manage/gpu/history")
async def gpu_history(count: int = 60):
    check_loading_transitions()
    points = [_gpu_point(i * 10) for i in range(count)]
    return {"history": points, "count": count, "enabled": True, "max_days": 7}

@app.get("/manage/models")
async def models_status():
    check_loading_transitions()
    return MOCK_MODELS

@app.post("/manage/models/{model_name}/start")
async def start_model(model_name: str):
    if model_name not in MOCK_MODELS:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
        
    if MOCK_MODELS[model_name]["running"]:
        return {"status": "already_running", "model": model_name}
        
    MOCK_MODELS[model_name]["running"] = True
    MOCK_MODELS[model_name]["status"] = "loading"
    model_loading_state["target_model"] = model_name
    model_loading_state["start_time"] = datetime.now()
    model_loading_state["duration"] = random.randint(20, 60)
    model_loading_state["error_triggered"] = False
    
    update_external_state()
    return {"status": "starting", "model": model_name, "estimated_duration": model_loading_state["duration"]}

@app.post("/manage/models/{model_name}/stop")
async def stop_model(model_name: str):
    if model_name in MOCK_MODELS:
        MOCK_MODELS[model_name]["running"] = False
        MOCK_MODELS[model_name]["status"] = "stopped"
        MOCK_MODELS[model_name]["port"] = None
        if model_loading_state["target_model"] == model_name:
            model_loading_state["target_model"] = None
            model_loading_state["start_time"] = None
        update_external_state()
        return {"status": "ok", "model": model_name, "message": f"Model {model_name} stopped"}
    return {"status": "error", "message": f"Model {model_name} not found"}

@app.post("/manage/models/{model_name}/switch")
async def switch_model(model_name: str, test_enabled: bool = True):
    if model_name not in MOCK_MODELS:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
        
    for name, m in MOCK_MODELS.items():
        m["running"] = False
        m["status"] = "stopped"
        m["port"] = None
        
    MOCK_MODELS[model_name]["running"] = True
    MOCK_MODELS[model_name]["status"] = "loading"
    model_loading_state["target_model"] = model_name
    model_loading_state["start_time"] = datetime.now()
    model_loading_state["duration"] = random.randint(20, 60)
    model_loading_state["error_triggered"] = False
    
    update_external_state()
    return {"status": "switching", "model": model_name, "estimated_duration": model_loading_state["duration"]}

@app.get("/manage/system/status")
async def system_status(include_history: bool = False, history_count: int = 60):
    check_loading_transitions()
    status = {
        "cpu": {"percent": round(25 + random.uniform(-5, 5), 1), "cores": 12, "cores_physical": 6},
        "memory": {"total_mb": 65536, "available_mb": 27307, "used_mb": 38229, "percent": 58.4},
        "disk": {"total_gb": 500, "used_gb": 235, "free_gb": 265, "percent": 47.0},
        "timestamp": datetime.now().isoformat(),
    }
    if include_history:
        status["history"] = [_system_point(i * 10) for i in range(history_count)]
    return status

@app.get("/manage/queue")
async def queue_status():
    check_loading_transitions()
    return {
        "Gemma-4-31B-Abliterated": {"active_requests": random.randint(0, 5), "concurrency_limit": 32, "can_accept": True},
        "Qwen3.6-35B": {"active_requests": 0, "concurrency_limit": 16, "can_accept": True},
    }

@app.get("/manage/health/alert")
async def health_alert():
    check_loading_transitions()
    return {
        "should_alert": False,
        "health_score": 85.5,
        "status": "healthy",
        "alert_reasons": ["GPU temperature within normal range", "Memory usage stable"],
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/manage/token/stats")
async def token_stats():
    check_loading_transitions()
    return {
        "total_prompt_tokens": 52800,
        "total_completion_tokens": 23400,
        "total_tokens": 76200,
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/manage/token/history")
async def token_history(count: int = 60):
    check_loading_transitions()
    points = [_token_point(i * 10) for i in range(count)]
    return {"history": points, "count": count}

@app.get("/v1/models")
async def v1_models():
    models_data = []
    for name, info in MOCK_MODELS.items():
        models_data.append({"id": name, "object": "model", "created": int(time.time()), "owned_by": "local"})
    return {"object": "list", "data": models_data}

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    check_loading_transitions()
    running_model = None
    for name, info in MOCK_MODELS.items():
        if info["running"]:
            if info["status"] == "loading":
                raise HTTPException(status_code=503, detail="Model is still loading")
            running_model = name
            break
            
    if not running_model:
         raise HTTPException(status_code=503, detail="No model running")
         
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": running_model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "This is a mock response."}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
    }

@app.post("/v1/test/model/{model_name}")
async def test_model(model_name: str):
    return {"status": "ok", "message": f"Test for {model_name} completed", "report": {
        "model_name": model_name,
        "test_timestamp": datetime.now().isoformat(),
        "overall_status": "passed",
        "feature_support": {"chat": True, "tool_calling": False, "image": True, "multimodal": True, "image_generation": False},
        "performance_metrics": {"overall": {"avg_tps": 45.2, "avg_latency": 120.5, "tests_passed": 3, "tests_total": 4, "pass_rate": 0.75}},
    }}

@app.get("/v1/test/reports")
async def test_reports():
    return {"status": "ok", "reports": {}}

@app.get("/manage/default-model")
async def get_default_model():
    return {"default_model": DEFAULT_MODEL}

@app.post("/manage/default-model/{model_name}")
async def set_default_model(model_name: str):
    global DEFAULT_MODEL
    if model_name not in MOCK_MODELS:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
    DEFAULT_MODEL = model_name
    return {"status": "ok", "default_model": model_name}

@app.delete("/manage/default-model")
async def clear_default_model():
    global DEFAULT_MODEL
    DEFAULT_MODEL = None
    return {"status": "ok", "default_model": None}

@app.get("/manage/agent/tools")
async def agent_list_tools(categories: Optional[str] = None):
    return {
        "tools": [
            {"type": "function", "function": {"name": "get_system_info", "description": "Get system info", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "list_models", "description": "List models", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "start_model", "description": "Start model", "parameters": {"type": "object", "properties": {"model_name": {"type": "string"}}, "required": ["model_name"]}}},
            {"type": "function", "function": {"name": "stop_model", "description": "Stop model", "parameters": {"type": "object", "properties": {"model_name": {"type": "string"}}, "required": ["model_name"]}}},
            {"type": "function", "function": {"name": "get_gpu_status", "description": "Get GPU status", "parameters": {"type": "object", "properties": {}, "required": []}}},
        ],
        "categories": ["system", "models", "gpu", "chat", "files", "web"],
        "count": 5,
    }

@app.get("/manage/agent/tools/{tool_name}")
async def agent_get_tool(tool_name: str):
    return {
        "name": tool_name,
        "description": f"Tool {tool_name}",
        "parameters": [],
        "category": "system",
        "dangerous": False,
        "requires_confirmation": False,
        "openai_schema": {"type": "function", "function": {"name": tool_name, "description": f"Tool {tool_name}", "parameters": {"type": "object", "properties": {}, "required": []}}},
    }

@app.post("/manage/agent/execute/{tool_name}")
async def agent_execute_single(tool_name: str, request: Request):
    return {"tool_name": tool_name, "success": True, "result": {"mock": True}, "execution_time": 0.1}

@app.post("/manage/agent/execute")
async def agent_execute_batch(request: Request):
    return {"results": [], "success": True}

@app.get("/manage/agent/history")
async def agent_history(limit: int = 100):
    return {"history": [], "statistics": {"total_calls": 0, "success_rate": 0}}

@app.delete("/manage/agent/history")
async def agent_clear_history():
    return {"status": "success", "message": "History cleared"}

@app.post("/manage/agent/chat")
async def agent_chat(request: Request):
    body = await request.json()
    running_model = None
    for name, info in MOCK_MODELS.items():
        if info["running"] and info["status"] == "running":
            running_model = name
            break
    return {
        "id": "agent-mock",
        "model": running_model or "mock",
        "message": {"role": "assistant", "content": "This is a mock agent response."},
        "iterations": 1,
        "finished": True,
    }

@app.get("/manage/system/history")
async def system_history(count: int = 60):
    points = [_system_point(i * 10) for i in range(count)]
    return {"history": points, "count": count}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=35000)
