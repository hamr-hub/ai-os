import json
import math
import random
import time
import os
import sys
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.path.join(os.path.dirname(__file__), "mocks"))
from state_manager import StateManager

app = FastAPI(title="Mock vLLM Management API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MOCK_MODELS = {
    "Gemma-4-31B-Abliterated": {
        "service": "vllm-aiclient",
        "port": 8000,
        "required_memory": "16GB",
        "description": "Gemma 4 31B Abliterated",
        "supports_images": True,
        "supports_tool_calling": True,
        "supports_image_generation": False,
        "backend_type": "vllm",
    },
    "Qwen3.6-35B": {
        "service": "vllm-aiclient",
        "port": 8000,
        "required_memory": "20GB",
        "description": "Qwen 3.6 35B",
        "supports_images": False,
        "supports_tool_calling": True,
        "supports_image_generation": False,
        "backend_type": "vllm",
    },
    "DeepSeek-V3-0324": {
        "service": "vllm-aiclient",
        "port": 8000,
        "required_memory": "24GB",
        "description": "DeepSeek V3 0324",
        "supports_images": False,
        "supports_tool_calling": True,
        "supports_image_generation": False,
        "backend_type": "vllm",
    },
}

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "gpu_status",
            "description": "Get current GPU status including utilization, memory, temperature",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_models",
            "description": "List all available models and their status",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_model",
            "description": "Start a model by name",
            "parameters": {
                "type": "object",
                "properties": {"model_name": {"type": "string", "description": "Model name to start"}},
                "required": ["model_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_model",
            "description": "Stop a running model",
            "parameters": {
                "type": "object",
                "properties": {"model_name": {"type": "string", "description": "Model name to stop"}},
                "required": ["model_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_status",
            "description": "Get system status (CPU, memory, disk)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "chat_completion",
            "description": "Send a chat message to the current model",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "User message"},
                    "model": {"type": "string", "description": "Model name (optional)"},
                },
                "required": ["message"],
            },
        },
    },
]

TOOL_HISTORY = []
TOOL_CATEGORIES = ["system", "models", "gpu", "chat", "files", "web"]


def _gpu_point(ts_offset: int) -> dict:
    now = datetime.now() - timedelta(seconds=ts_offset)
    StateManager.update_vllm_status()
    state = StateManager.get_state()
    vllm = state["vllm"]
    gpu_base = state["gpu"]

    status = vllm["status"]
    if status == "loading":
        base_util = 85 + random.uniform(-5, 5)
        base_temp = 68 + random.uniform(-2, 2)
        base_mem_util = 45 + random.uniform(-5, 5)
        base_power = 350 + random.uniform(-20, 20)
    elif status == "active":
        base_util = 5 + 15 * abs(math.sin(ts_offset / 60))
        base_temp = 55 + 5 * math.sin(ts_offset / 90)
        base_mem_util = 88 + random.uniform(-1, 1)
        base_power = 150 + 40 * math.sin(ts_offset / 70)
    else:
        base_util = 0.5
        base_temp = 42
        base_mem_util = 2.0
        base_power = 30

    total_mem = gpu_base["vram_total_mb"] * 1024 * 1024
    return {
        "timestamp": now.isoformat(),
        "utilization": round(base_util, 1),
        "temperature": round(base_temp, 1),
        "power_draw": round(base_power, 1),
        "power_percent": round(base_power / 450 * 100, 1),
        "memory_utilization": round(base_mem_util, 1),
        "used_memory": round((base_mem_util / 100) * total_mem),
        "available_memory": round((1 - base_mem_util / 100) * total_mem),
        "total_memory": total_mem,
        "fan_speed": round(30 + base_temp / 2),
        "clock_sm": round(2100 if status != "stopped" else 300),
        "clock_mem": round(10501 if status != "stopped" else 400),
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/detailed")
async def health_detailed():
    return {"status": "ok", "services": {"vllm": "active", "redis": "connected", "gpu": "available"}}


@app.get("/manage/gpu/summary")
async def gpu_summary():
    current = _gpu_point(0)
    current["name"] = "NVIDIA GeForce RTX 4090"
    current["gpu_count"] = 1
    current["power_limit"] = 450
    history = [_gpu_point(i * 10) for i in range(60)]
    return {"status": "available", "current": current, "history": history}


@app.get("/manage/gpu/enhanced")
async def gpu_enhanced():
    StateManager.update_vllm_status()
    state = StateManager.get_state()
    vllm = state["vllm"]
    gpu_base = state["gpu"]
    is_active = vllm["status"] == "active"
    return {
        "gpu_count": 1,
        "gpus": [
            {
                "index": 0,
                "name": gpu_base["name"],
                "utilization": gpu_base["utilization"] if is_active else 0.5,
                "temperature": gpu_base["temperature"],
                "memory_utilization": gpu_base["vram_used_mb"] / gpu_base["vram_total_mb"] * 100,
                "used_memory": gpu_base["vram_used_mb"] * 1024 * 1024,
                "available_memory": (gpu_base["vram_total_mb"] - gpu_base["vram_used_mb"]) * 1024 * 1024,
                "total_memory": gpu_base["vram_total_mb"] * 1024 * 1024,
                "power_draw": gpu_base["power_draw"],
                "power_limit": 450,
                "power_percent": gpu_base["power_draw"] / 450 * 100,
                "fan_speed": round(30 + gpu_base["temperature"] / 2),
                "clock_sm": 2100 if is_active else 300,
                "clock_mem": 10501 if is_active else 400,
                "persistence_mode": True,
                "pcie_rx_throughput": random.uniform(0, 100) if is_active else 0,
                "pcie_tx_throughput": random.uniform(0, 100) if is_active else 0,
                "bar1_total_memory": 256 * 1024 * 1024,
                "bar1_used_memory": random.uniform(0, 128) * 1024 * 1024,
                "processes": [
                    {"pid": 12345, "name": "vllm", "used_gpu_memory": gpu_base["vram_used_mb"] * 1024 * 1024}
                ] if is_active else [],
                "vbios_version": "96.00.45.00.01",
                "driver_version": "550.54.14",
            }
        ],
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/manage/gpu/processes")
async def gpu_processes():
    StateManager.update_vllm_status()
    state = StateManager.get_state()
    vllm = state["vllm"]
    is_active = vllm["status"] == "active"
    processes = []
    if is_active:
        processes = [{"pid": 12345, "name": "python3 (vllm)", "used_gpu_memory": state["gpu"]["vram_used_mb"] * 1024 * 1024}]
    return {"processes": processes, "count": len(processes)}


@app.get("/manage/gpu/history")
async def gpu_history(count: int = 60):
    history = [_gpu_point(i * 10) for i in range(count)]
    return {"history": history, "count": len(history), "enabled": True, "max_days": 7}


@app.get("/manage/models")
async def models_status():
    StateManager.update_vllm_status()
    state = StateManager.get_state()
    vllm = state["vllm"]

    res = {}
    for name, info in MOCK_MODELS.items():
        is_running = vllm["current_model"] == name and vllm["status"] in ["active", "loading"]
        res[name] = {
            "running": is_running,
            "port": info["port"] if is_running else None,
            "service": info["service"] if is_running else None,
            "active_requests": random.randint(0, 5) if is_running and vllm["status"] == "active" else 0,
            "preloaded": name == "Gemma-4-31B-Abliterated",
            "last_used": datetime.now().isoformat() if is_running else None,
            "supports_images": info["supports_images"],
            "supports_tool_calling": info["supports_tool_calling"],
            "supports_image_generation": info["supports_image_generation"],
            "description": info["description"],
            "required_memory": info["required_memory"],
            "backend_type": info["backend_type"],
        }
    return res


@app.post("/manage/models/{name}/start")
async def start_model(name: str):
    if name not in MOCK_MODELS:
        raise HTTPException(status_code=404, detail=f"Model {name} not found")
    state = StateManager.get_state()
    state["vllm"]["current_model"] = name
    state["vllm"]["status"] = "loading"
    state["vllm"]["loading_start"] = time.time()
    state["vllm"]["loading_target_duration"] = 10
    StateManager.save_state(state)
    return {"status": "ok", "model": name, "message": f"Starting model {name}"}


@app.post("/manage/models/{name}/stop")
async def stop_model(name: str):
    state = StateManager.get_state()
    state["vllm"]["status"] = "stopped"
    state["vllm"]["current_model"] = None
    state["vllm"]["error"] = None
    StateManager.save_state(state)
    return {"status": "ok", "model": name, "message": f"Stopped model {name}"}


@app.post("/manage/models/{name}/switch")
async def switch_model(name: str, request: Request = None):
    if name not in MOCK_MODELS:
        raise HTTPException(status_code=404, detail=f"Model {name} not found")
    state = StateManager.get_state()
    state["vllm"]["current_model"] = name
    state["vllm"]["status"] = "loading"
    state["vllm"]["loading_start"] = time.time()
    state["vllm"]["loading_target_duration"] = 10
    state["vllm"]["error"] = None
    StateManager.save_state(state)
    return {"status": "ok", "model": name, "message": f"Switching to model {name}"}


@app.get("/manage/default-model")
async def default_model():
    return {"default_model": "Gemma-4-31B-Abliterated"}


@app.post("/manage/default-model/{name}")
async def set_default_model(name: str):
    return {"status": "ok", "model": name}


@app.delete("/manage/default-model")
async def clear_default_model():
    return {"status": "ok", "model": None}


@app.get("/manage/system/status")
async def system_status(include_history: bool = False, history_count: int = 60):
    result = {
        "cpu": {"percent": round(25 + random.uniform(-5, 5), 1), "cores": 12, "cores_physical": 6},
        "memory": {"total_mb": 65536, "available_mb": 27307, "used_mb": 38229, "percent": 58.4},
        "disk": {"total_gb": 500, "used_gb": 250, "free_gb": 250, "percent": 50.0},
        "timestamp": datetime.now().isoformat(),
    }
    if include_history:
        history = []
        for i in range(history_count):
            ts = datetime.now() - timedelta(seconds=i * 10)
            history.append({
                "timestamp": ts.isoformat(),
                "cpu_percent": round(25 + random.uniform(-5, 5), 1),
                "memory_percent": round(58 + random.uniform(-2, 2), 1),
            })
        result["history"] = history
    return result


@app.get("/manage/system/history")
async def system_history(count: int = 60):
    history = []
    for i in range(count):
        ts = datetime.now() - timedelta(seconds=i * 10)
        history.append({
            "timestamp": ts.isoformat(),
            "cpu_percent": round(25 + random.uniform(-5, 5), 1),
            "memory_percent": round(58 + random.uniform(-2, 2), 1),
        })
    return {"history": history, "count": len(history)}


@app.get("/manage/vllm/metrics")
async def vllm_metrics():
    StateManager.update_vllm_status()
    state = StateManager.get_state()
    vllm = state["vllm"]
    available = vllm["status"] == "active"
    if available:
        return {
            "vllm_available": True,
            "running_requests": random.randint(1, 8),
            "waiting_requests": random.randint(0, 3),
            "gpu_cache_usage": round(35 + random.uniform(-5, 5), 1),
            "cpu_cache_usage": round(2.5 + random.uniform(-1, 1), 1),
            "generation_throughput": round(120 + random.uniform(-30, 30), 1),
            "prompt_throughput": round(50 + random.uniform(-10, 10), 1),
            "time_to_first_token": round(0.05 + random.uniform(-0.02, 0.02), 4),
            "time_per_output_token": round(0.015 + random.uniform(-0.005, 0.005), 4),
            "prefix_cache_hit_rate": round(75 + random.uniform(-10, 10), 1),
            "scraped_at": datetime.now().isoformat(),
        }
    return {
        "vllm_available": False,
        "running_requests": 0,
        "waiting_requests": 0,
        "gpu_cache_usage": 0,
        "cpu_cache_usage": 0,
        "generation_throughput": 0,
        "prompt_throughput": 0,
        "time_to_first_token": 0,
        "time_per_output_token": 0,
        "prefix_cache_hit_rate": 0,
        "scraped_at": datetime.now().isoformat(),
    }


@app.get("/manage/queue")
async def queue_status():
    StateManager.update_vllm_status()
    state = StateManager.get_state()
    vllm = state["vllm"]
    res = {}
    for name in MOCK_MODELS:
        is_running = vllm["current_model"] == name and vllm["status"] == "active"
        if is_running:
            res[name] = {
                "active_requests": random.randint(0, 5),
                "concurrency_limit": 10,
                "can_accept": True,
            }
    return res


@app.get("/manage/health/alert")
async def health_alert():
    return {
        "should_alert": False,
        "health_score": 85.5,
        "status": "healthy",
        "alert_reasons": ["GPU temperature within normal range", "Memory usage stable"],
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/manage/token/stats")
async def token_stats():
    return {
        "total_prompt_tokens": 150000,
        "total_completion_tokens": 80000,
        "total_tokens": 230000,
        "models": {
            "Gemma-4-31B-Abliterated": {"prompt_tokens": 100000, "completion_tokens": 55000, "total_tokens": 155000},
            "Qwen3.6-35B": {"prompt_tokens": 30000, "completion_tokens": 15000, "total_tokens": 45000},
            "DeepSeek-V3-0324": {"prompt_tokens": 20000, "completion_tokens": 10000, "total_tokens": 30000},
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/manage/token/history")
async def token_history(count: int = 60):
    history = []
    for i in range(count):
        ts = datetime.now() - timedelta(seconds=i * 10)
        history.append({
            "timestamp": ts.isoformat(),
            "total_tokens": random.randint(200, 5000),
            "prompt_tokens": random.randint(100, 3000),
            "completion_tokens": random.randint(50, 2000),
            "models": {"Gemma-4-31B-Abliterated": random.randint(100, 2000)},
        })
    return {"history": history, "count": len(history)}


@app.post("/manage/faults")
async def set_faults(faults: dict):
    state = StateManager.get_state()
    state["faults"].update(faults)
    StateManager.save_state(state)
    return {"status": "ok", "faults": state["faults"]}


# --- v1 endpoints ---


@app.get("/v1/models")
async def v1_models():
    StateManager.update_vllm_status()
    state = StateManager.get_state()
    vllm = state["vllm"]
    models = []
    for name, info in MOCK_MODELS.items():
        models.append({
            "id": name,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "vllm",
        })
    return {"object": "list", "data": models}


@app.post("/v1/chat/completions")
async def v1_chat_completions(request: Request):
    StateManager.update_vllm_status()
    state = StateManager.get_state()
    vllm = state["vllm"]
    if vllm["status"] == "loading":
        raise HTTPException(status_code=503, detail="Model is loading")
    if vllm["status"] != "active":
        raise HTTPException(status_code=503, detail="Service Unavailable")

    body = await request.json()
    model = body.get("model", vllm.get("current_model", "mock-model"))
    stream = body.get("stream", False)
    messages = body.get("messages", [])
    last_user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            content = m.get("content", "")
            if isinstance(content, list):
                last_user_msg = " ".join([c.get("text", "") for c in content if c.get("type") == "text"])
            else:
                last_user_msg = content
            break

    content = f"Mock response from {model}. Your message: {last_user_msg[:100]}"

    if stream:
        async def event_generator():
            words = content.split()
            for i, word in enumerate(words):
                chunk = {
                    "id": "chatcmpl-mock",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None if i < len(words) - 1 else "stop"}],
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        return {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }


@app.post("/v1/embeddings")
async def v1_embeddings(request: Request):
    body = await request.json()
    return {
        "object": "list",
        "data": [{"object": "embedding", "embedding": [random.uniform(-1, 1) for _ in range(768)], "index": 0}],
        "model": body.get("model", "mock-model"),
        "usage": {"prompt_tokens": 5, "total_tokens": 5},
    }


@app.post("/v1/test/model/{name}")
async def v1_test_model(name: str):
    if name not in MOCK_MODELS:
        raise HTTPException(status_code=404, detail=f"Model {name} not found")
    return {
        "status": "ok",
        "message": f"Test completed for {name}",
        "report": {
            "model_name": name,
            "test_timestamp": datetime.now().isoformat(),
            "overall_status": "passed",
            "feature_support": {
                "chat": True,
                "tool_calling": MOCK_MODELS[name]["supports_tool_calling"],
                "image": MOCK_MODELS[name]["supports_images"],
                "multimodal": MOCK_MODELS[name]["supports_images"],
                "image_generation": MOCK_MODELS[name]["supports_image_generation"],
            },
            "performance_metrics": {
                "chat": {"avg_tps": 120.5, "avg_latency": 0.05, "avg_token_count": 100, "tests_passed": 5},
                "overall": {"avg_tps": 120.5, "avg_latency": 0.05, "tests_passed": 5, "tests_total": 5, "pass_rate": 1.0},
            },
            "resource_utilization": {
                "test_duration_seconds": 15.2,
                "gpu": {
                    "available": True,
                    "start_utilization": 5.0,
                    "end_utilization": 85.0,
                    "start_memory_used_mb": 450,
                    "end_memory_used_mb": 22000,
                    "start_temperature": 42,
                    "end_temperature": 68,
                },
            },
        },
    }


@app.get("/v1/test/report/{name}")
async def v1_test_report(name: str):
    if name not in MOCK_MODELS:
        raise HTTPException(status_code=404, detail=f"Model {name} not found")
    return {
        "status": "ok",
        "message": f"Test report for {name}",
        "report": {
            "model_name": name,
            "test_timestamp": datetime.now().isoformat(),
            "overall_status": "passed",
            "feature_support": {
                "chat": True,
                "tool_calling": MOCK_MODELS[name]["supports_tool_calling"],
                "image": MOCK_MODELS[name]["supports_images"],
                "multimodal": MOCK_MODELS[name]["supports_images"],
                "image_generation": MOCK_MODELS[name]["supports_image_generation"],
            },
        },
    }


@app.get("/v1/test/reports")
async def v1_test_reports():
    reports = {}
    for name in MOCK_MODELS:
        reports[name] = {
            "model_name": name,
            "test_timestamp": datetime.now().isoformat(),
            "overall_status": "passed",
            "feature_support": {
                "chat": True,
                "tool_calling": MOCK_MODELS[name]["supports_tool_calling"],
                "image": MOCK_MODELS[name]["supports_images"],
                "multimodal": MOCK_MODELS[name]["supports_images"],
                "image_generation": MOCK_MODELS[name]["supports_image_generation"],
            },
        }
    return {"status": "ok", "reports": reports}


# --- Agent endpoints ---


@app.get("/manage/agent/tools")
async def agent_tools(categories: Optional[str] = None):
    filtered = AGENT_TOOLS
    if categories:
        cats = categories.split(",")
        filtered = [t for t in AGENT_TOOLS if any(c in t["function"]["name"] for c in cats)]
    return {"tools": filtered, "categories": TOOL_CATEGORIES, "count": len(filtered)}


@app.get("/manage/agent/tools/{name}")
async def agent_tool_info(name: str):
    for t in AGENT_TOOLS:
        if t["function"]["name"] == name:
            return {
                "name": name,
                "description": t["function"]["description"],
                "parameters": t["function"]["parameters"],
                "category": "system",
                "dangerous": False,
                "requires_confirmation": False,
            }
    raise HTTPException(status_code=404, detail=f"Tool {name} not found")


@app.post("/manage/agent/execute/{name}")
async def agent_execute_tool(name: str, request: Request):
    body = await request.json()
    args = body.get("arguments", {})
    start_time = time.time()
    result = {"tool_name": name, "executed_at": datetime.now().isoformat(), "args": args}

    if name == "gpu_status":
        gpu_data = await gpu_summary()
        result["result"] = gpu_data
    elif name == "list_models":
        models_data = await models_status()
        result["result"] = models_data
    elif name == "system_status":
        sys_data = await system_status()
        result["result"] = sys_data
    elif name in ("start_model", "stop_model"):
        model_name = args.get("model_name", "unknown")
        result["result"] = {"status": "ok", "model": model_name}
    else:
        result["result"] = {"message": f"Mock execution of {name}"}

    entry = {
        "tool_name": name,
        "success": True,
        "result": result["result"],
        "execution_time": round(time.time() - start_time, 3),
    }
    TOOL_HISTORY.append(entry)
    return entry


@app.post("/manage/agent/execute")
async def agent_execute_batch(request: Request):
    body = await request.json()
    calls = body.get("calls", [])
    results = []
    for call in calls:
        tool_name = call.get("name", "")
        args = call.get("arguments", {})
        start_time = time.time()
        entry = {
            "tool_name": tool_name,
            "success": True,
            "result": {"message": f"Mock execution of {tool_name}", "args": args},
            "execution_time": round(time.time() - start_time + random.uniform(0.01, 0.5), 3),
        }
        TOOL_HISTORY.append(entry)
        results.append(entry)
    return {"results": results, "success": True}


@app.get("/manage/agent/history")
async def agent_history(limit: int = 100):
    return {"history": TOOL_HISTORY[-limit:], "statistics": {"total_calls": len(TOOL_HISTORY), "success_rate": 1.0}}


@app.delete("/manage/agent/history")
async def agent_clear_history():
    TOOL_HISTORY.clear()
    return {"status": "ok"}


@app.post("/manage/agent/chat")
async def agent_chat(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    model = body.get("model", "Gemma-4-31B-Abliterated")

    last_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_msg = m.get("content", "")
            break

    content = f"Mock agent response from {model}. Received: {last_msg[:200]}"

    if stream:
        async def event_generator():
            words = content.split()
            for i, word in enumerate(words):
                chunk = {
                    "id": "agent-mock",
                    "model": model,
                    "message": {"role": "assistant", "content": word + " "},
                    "iterations": 1,
                    "finished": i == len(words) - 1,
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            final = {
                "id": "agent-mock",
                "model": model,
                "message": {"role": "assistant", "content": content},
                "iterations": 1,
                "finished": True,
            }
            yield f"data: {json.dumps(final)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        return {
            "id": "agent-mock",
            "model": model,
            "message": {"role": "assistant", "content": content},
            "iterations": 1,
            "finished": True,
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=35000)
