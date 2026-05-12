from fastapi import APIRouter, HTTPException, Request
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio
import copy
import os
import json

from core.vllm_manager import save_model_vllm_params, get_model_vllm_params
from middleware.error_handler import ModelNotFoundException
from schemas.service import ServiceControlRequest
from schemas.vllm_config import VLLMConfigResponse, VLLMConfigUpdateRequest
from core.deps import (
    scheduler as _scheduler, gpu_monitor as _gpu_monitor, sys_controller as _sys_controller,
    ws_manager as _ws_manager, metrics as _metrics, prometheus as _prometheus,
    cache_service as _cache_service, cache_updater as _cache_updater,
    structured_logger as _structured_logger, config_watcher as _config_watcher,
    logger as _logger, redis_client as _redis_client,
    gpu_memory_manager as _gpu_memory_manager, model_hub as _model_hub,
    llm_service_manager as _llm_service_manager, model_pool_manager as _model_pool_manager,
    download_task_manager as _download_task_manager, model_engine_scheduler as _model_engine_scheduler,
    model_tester as _model_tester,
)

scheduler = _scheduler
gpu_monitor = _gpu_monitor
sys_controller = _sys_controller
ws_manager = _ws_manager
metrics = _metrics
prometheus = _prometheus
cache_service = _cache_service
cache_updater = _cache_updater
structured_logger = _structured_logger
config_watcher = _config_watcher
logger = _logger
redis_client = _redis_client
gpu_memory_manager = _gpu_memory_manager
model_hub = _model_hub
llm_service_manager = _llm_service_manager
model_pool_manager = _model_pool_manager
download_task_manager = _download_task_manager
model_engine_scheduler = _model_engine_scheduler
model_tester = _model_tester

manage_router = APIRouter(prefix="/manage")
integration_router = APIRouter(prefix="/api/v1")


@manage_router.get("/switch/status")
async def get_switch_status():
    from core.deps import model_switch_orchestrator
    is_switching = model_switch_orchestrator.is_switching
    session = model_switch_orchestrator.current_session

    terminal_phases = {"completed", "failed", "rolled_back"}

    try:
        if session and not is_switching:
            session_phase_value = session.overall_phase.value if hasattr(session.overall_phase, 'value') else str(session.overall_phase)
            if session_phase_value not in terminal_phases:
                from core.model_switch_orchestrator import SwitchPhase as _SP
                session.overall_phase = _SP.FAILED
                session.error = session.error or "切换进程异常中断，锁已释放但任务未完成"
                if not session.finished_at:
                    session.finished_at = datetime.now().isoformat()
                logger.warning("Stale switch session detected: phase=%s, lock released. Marked as FAILED.", session_phase_value)
    except Exception as e:
        logger.error(f"Error processing switch session state: {e}")

    return {
        "is_switching": is_switching,
        "session": session.to_dict() if session else None,
        "timestamp": datetime.now().isoformat(),
    }


@manage_router.post("/switch/atomic")
async def atomic_switch_model(request: Request):
    from core.deps import model_switch_orchestrator
    from core.vllm_manager import get_current_model_info, MODEL_BASE_PATH
    import os

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    action = body.get("action", "switch")
    if action not in {"switch", "start", "stop"}:
        raise HTTPException(status_code=400, detail="action must be switch, start or stop")

    model_name = body.get("model_name") or body.get("target_model")
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name is required")

    set_as_default = body.get("set_as_default", False)
    model_path = body.get("model_path")

    if model_switch_orchestrator.is_switching:
        current = model_switch_orchestrator.current_session
        raise HTTPException(
            status_code=409,
            detail={
                "error": "模型切换正在进行中",
                "session_id": current.session_id if current else None,
                "target_model": current.target_model if current else None,
            }
        )

    model_switch_orchestrator.clear_completed_session()

    current_info = get_current_model_info()
    previous_model = current_info.get("name") if current_info else None
    previous_path = current_info.get("path") if current_info else None

    if action != "stop":
        if not scheduler.is_model_available(model_name):
            raise ModelNotFoundException(model_name)
        target_path = model_path
        if not target_path:
            config = scheduler.get_model_config(model_name)
            target_path = (config or {}).get("model_path") or os.path.join(MODEL_BASE_PATH, model_name)
        if not os.path.exists(target_path):
            raise HTTPException(status_code=404, detail=f"模型路径不存在: {target_path}")
    else:
        target_path = previous_path or ""

    if action == "switch":
        task = asyncio.create_task(
            model_switch_orchestrator.switch(
                target_model=model_name,
                target_model_path=target_path,
                previous_model=previous_model,
                previous_model_path=previous_path,
            )
        )
        status = "switching"
        message = "模型切换已启动，请通过 WebSocket 或轮询 /manage/switch/status 追踪进度"
    elif action == "start":
        task = asyncio.create_task(
            model_switch_orchestrator.start(
                target_model=model_name,
                target_model_path=target_path,
                previous_model=previous_model,
                previous_model_path=previous_path,
            )
        )
        status = "starting"
        message = "模型启动已启动，请通过 WebSocket 或轮询 /manage/switch/status 追踪进度"
    else:
        task = asyncio.create_task(
            model_switch_orchestrator.stop(
                target_model=model_name,
                previous_model=previous_model,
                previous_model_path=previous_path,
            )
        )
        status = "stopping"
        message = "模型停止已启动，请通过 WebSocket 或轮询 /manage/switch/status 追踪进度"

    async def _on_switch_done(t: asyncio.Task):
        try:
            session = t.result()
            if session.completed_successfully:
                if action in {"switch", "start"}:
                    scheduler.mark_model_selected(model_name)
                    if set_as_default:
                        scheduler.set_default_model(model_name)
                _clear_model_caches()
            else:
                logger.error("Model switch failed: %s", session.error or session.rollback_reason or "unknown")
                scheduler.clear_default_model()
                _clear_model_caches()
        except Exception as e:
            logger.error("Switch task callback error: %s", e)
            scheduler.clear_default_model()

    task.add_done_callback(lambda t: asyncio.create_task(_on_switch_done(t)))

    await asyncio.sleep(0.1)
    current_session = model_switch_orchestrator.current_session

    return {
        "status": status,
        "action": action,
        "session_id": current_session.session_id if current_session else None,
        "target_model": model_name,
        "previous_model": previous_model,
        "message": message,
    }


@manage_router.delete("/switch/cancel")
async def cancel_switch():
    from core.deps import model_switch_orchestrator
    if not model_switch_orchestrator.is_switching:
        return {"status": "no_switch_in_progress"}
    model_switch_orchestrator.request_cancel()
    return {"status": "cancel_requested"}


def _clear_model_caches():
    for key in [
        "api:manage:models:status", "api:manage:models:summary",
        "api:manage:preload:status", "api:manage:preload:detailed",
        "api:v1:status"
    ]:
        cache_service.delete(key)
    cache_service.delete_pattern("ai_controller:cache:model_running:*")


@manage_router.get("/gpu")
async def get_gpu_status(refresh: Optional[bool] = False):
    cache_key = "api:manage:gpu:status"

    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached

    status = gpu_monitor.get_gpu_status()
    if not status:
        result = {"status": "unavailable", "message": "No GPU detected", "serverTime": datetime.now().isoformat()}
    else:
        status["serverTime"] = datetime.now().isoformat()
        result = status

    cache_service.set(cache_key, result, ttl_seconds=10)
    return result


@manage_router.get("/gpu/summary")
async def get_gpu_summary():
    cache_key = "api:manage:gpu:summary"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    summary = gpu_monitor.get_gpu_summary()

    models = {}
    for model in scheduler.get_available_models():
        models[model] = {
            "running": scheduler.is_model_running(model),
            "engine": scheduler.get_model_backend_type(model),
            "port": scheduler.get_model_port(model),
            "pid": None,
            "started_at": None,
        }

    summary["models"] = models
    summary["current_model"] = scheduler.get_current_model_name()
    summary["default_model"] = scheduler.get_default_model()

    cache_service.set(cache_key, summary, ttl_seconds=30)
    return summary


@manage_router.get("/gpu/history")
async def get_gpu_history(count: int = 60):
    try:
        history = gpu_monitor.get_gpu_history(count)
        return {
            "history": history,
            "count": len(history),
            "enabled": gpu_monitor.get_history_enabled(),
            "max_days": gpu_monitor.get_max_history_days()
        }
    except Exception as e:
        logger.exception("Failed to get GPU history")
        raise HTTPException(status_code=500, detail=f"Failed to get GPU history: {str(e)}")


@manage_router.get("/gpu/processes")
async def get_gpu_processes():
    processes = gpu_monitor.get_gpu_processes()
    return {
        "processes": processes,
        "count": len(processes),
        "timestamp": datetime.now().isoformat()
    }


@manage_router.get("/gpu/enhanced")
async def get_gpu_enhanced():
    enhanced = gpu_monitor.get_gpu_enhanced_info()
    if not enhanced:
        return {"status": "unavailable", "message": "NVML not available or no GPU detected"}
    enhanced["timestamp"] = datetime.now().isoformat()
    return enhanced


@manage_router.get("/vllm/metrics")
async def get_vllm_metrics():
    vllm_metrics = gpu_monitor.get_vllm_metrics()
    if not vllm_metrics:
        return {"status": "unavailable", "message": "vLLM metrics not available"}
    return vllm_metrics


@manage_router.post("/gpu/history/config")
async def configure_gpu_history(enabled: Optional[bool] = None, max_days: Optional[int] = None):
    try:
        if enabled is not None:
            gpu_monitor.set_history_enabled(enabled)
        if max_days is not None and max_days > 0:
            gpu_monitor.set_max_history_days(max_days)
        return {
            "enabled": gpu_monitor.get_history_enabled(),
            "max_days": gpu_monitor.get_max_history_days()
        }
    except Exception as e:
        logger.exception("Failed to configure GPU history")
        raise HTTPException(status_code=500, detail=f"Failed to configure GPU history: {str(e)}")


@manage_router.get("/models")
async def get_model_status(refresh: Optional[bool] = False):
    cache_key = "api:manage:models:status"

    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached

    models = scheduler.get_available_models()
    status = {}
    for model in models:
        status[model] = {
            "running": scheduler.is_model_running(model),
            "port": scheduler.get_model_port(model),
            "service": scheduler.get_model_service(model),
            "active_requests": scheduler.get_active_requests(model),
            "preloaded": scheduler.is_model_preloaded(model),
            "last_used": scheduler.get_model_last_used(model).isoformat() if scheduler.get_model_last_used(model) else None,
            "supports_images": scheduler.get_model_supports_images(model),
            "supports_tool_calling": scheduler.get_model_supports_tool_calling(model),
            "supports_image_generation": scheduler.get_model_supports_image_generation(model),
            "description": scheduler.get_model_config(model).get("description", "") if scheduler.get_model_config(model) else "",
            "required_memory": scheduler.get_model_config(model).get("required_memory", "") if scheduler.get_model_config(model) else "",
            "backend_type": scheduler.get_model_backend_type(model),
        }

    cache_service.set(cache_key, status, ttl_seconds=5)
    return status


@manage_router.get("/models/summary")
async def models_summary(refresh: Optional[bool] = False):
    cache_key = "api:manage:models:summary"

    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached

    models = scheduler.get_available_models()
    summary = []
    for model in models:
        config = scheduler.get_model_config(model)
        summary.append({
            "name": model,
            "running": scheduler.is_model_running(model),
            "preloaded": scheduler.is_model_preloaded(model),
            "supports_images": scheduler.get_model_supports_images(model),
            "supports_tool_calling": scheduler.get_model_supports_tool_calling(model),
            "supports_image_generation": scheduler.get_model_supports_image_generation(model),
            "description": config.get("description", "") if config else "",
            "required_memory": config.get("required_memory", "") if config else "",
            "port": scheduler.get_model_port(model)
        })

    result = {
        "models": summary,
        "total": len(summary),
        "running_model": scheduler.get_current_model_name()
    }

    cache_service.set(cache_key, result, ttl_seconds=5)
    return result


@manage_router.get("/default-model")
async def get_default_model():
    return {"default_model": scheduler.get_default_model()}


@manage_router.post("/default-model/{model_name}")
async def set_default_model(model_name: str):
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    success = scheduler.set_default_model(model_name)
    if success:
        return {"status": "success", "default_model": model_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to set default model to {model_name}")


@manage_router.delete("/default-model")
async def clear_default_model():
    scheduler.clear_default_model()
    return {"status": "success", "message": "Default model cleared"}


@manage_router.get("/models/aggregated")
async def get_aggregated_models():
    cache_key = "api:manage:models:aggregated"

    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    from core.vllm_manager import get_aggregated_models as _get_aggregated_models

    aggregated = _get_aggregated_models()

    for group in aggregated:
        for variant in group.get("variants", []):
            model_name = variant["name"]
            variant["running"] = scheduler.is_model_running(model_name)
            variant["port"] = scheduler.get_model_port(model_name)
            variant["preloaded"] = scheduler.is_model_preloaded(model_name)
            variant["active_requests"] = scheduler.get_active_requests(model_name)
            variant["supports_images"] = scheduler.get_model_supports_images(model_name)
            variant["supports_tool_calling"] = scheduler.get_model_supports_tool_calling(model_name)
            variant["supports_image_generation"] = scheduler.get_model_supports_image_generation(model_name)
            config = scheduler.get_model_config(model_name)
            variant["description"] = config.get("description", "") if config else ""
            variant["required_memory"] = config.get("required_memory", "") if config else ""
            variant["backend_type"] = scheduler.get_model_backend_type(model_name)

            vllm_config = _get_model_vllm_config(model_name)
            variant["vllm_config"] = vllm_config

            model_path = variant.get("path", "")
            variant["path_exists"] = os.path.exists(model_path) if model_path else False

    current_model = scheduler.get_current_model_name()
    for group in aggregated:
        for variant in group.get("variants", []):
            variant["is_current"] = variant["name"] == current_model

    result = {
        "groups": aggregated,
        "total_groups": len(aggregated),
        "total_variants": sum(g["variant_count"] for g in aggregated),
        "current_model": current_model
    }

    cache_service.set(cache_key, result, ttl_seconds=10)
    return result


def _get_model_vllm_config(model_name: str) -> Dict[str, Any]:
    config = scheduler.get_model_config(model_name)
    if not config:
        return {
            "gpu_memory_utilization": None,
            "max_model_len": None,
            "max_num_seqs": None,
            "max_num_batched_tokens": None,
            "tensor_parallel_size": None,
            "has_custom_config": False
        }

    vllm_params = config.get("vllm_params", {})
    has_custom = bool(vllm_params)

    return {
        "gpu_memory_utilization": vllm_params.get("gpu_memory_utilization"),
        "max_model_len": vllm_params.get("max_model_len"),
        "max_num_seqs": vllm_params.get("max_num_seqs"),
        "max_num_batched_tokens": vllm_params.get("max_num_batched_tokens"),
        "tensor_parallel_size": vllm_params.get("tensor_parallel_size"),
        "has_custom_config": has_custom
    }


@manage_router.get("/models/{model_name}/vllm-config", response_model=VLLMConfigResponse)
async def get_model_vllm_config(model_name: str):
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    config = _get_model_vllm_config(model_name)
    return VLLMConfigResponse(
        model_name=model_name,
        gpu_memory_utilization=config.get("gpu_memory_utilization"),
        max_model_len=config.get("max_model_len"),
        max_num_seqs=config.get("max_num_seqs"),
        max_num_batched_tokens=config.get("max_num_batched_tokens"),
        tensor_parallel_size=config.get("tensor_parallel_size"),
        has_custom_config=config.get("has_custom_config", False)
    )


@manage_router.put("/models/{model_name}/vllm-config", response_model=VLLMConfigResponse)
async def update_model_vllm_config(model_name: str, request: VLLMConfigUpdateRequest):
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    current_config = config_watcher.get_config()
    if "models" not in current_config:
        current_config["models"] = {}
    if model_name not in current_config["models"]:
        current_config["models"][model_name] = {}

    vllm_params = {}
    if request.gpu_memory_utilization is not None:
        vllm_params["gpu_memory_utilization"] = request.gpu_memory_utilization
    if request.max_model_len is not None:
        vllm_params["max_model_len"] = request.max_model_len
    if request.max_num_seqs is not None:
        vllm_params["max_num_seqs"] = request.max_num_seqs
    if request.max_num_batched_tokens is not None:
        vllm_params["max_num_batched_tokens"] = request.max_num_batched_tokens
    if request.tensor_parallel_size is not None:
        vllm_params["tensor_parallel_size"] = request.tensor_parallel_size

    if vllm_params:
        current_config["models"][model_name]["vllm_params"] = vllm_params

    success = config_watcher.save_config(current_config)
    if success:
        from core.deps import _on_config_changed
        persisted_config = config_watcher.get_config()
        _on_config_changed(persisted_config)
        cache_service.delete("api:manage:models:aggregated")
    else:
        raise HTTPException(status_code=400, detail="Failed to save vLLM configuration")

    return VLLMConfigResponse(
        model_name=model_name,
        gpu_memory_utilization=vllm_params.get("gpu_memory_utilization"),
        max_model_len=vllm_params.get("max_model_len"),
        max_num_seqs=vllm_params.get("max_num_seqs"),
        max_num_batched_tokens=vllm_params.get("max_num_batched_tokens"),
        tensor_parallel_size=vllm_params.get("tensor_parallel_size"),
        has_custom_config=bool(vllm_params)
    )


@manage_router.get("/vllm/default-config")
async def get_vllm_default_config():
    cache_key = "api:manage:vllm:default_config"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    current_config = config_watcher.get_config()
    vllm_config = current_config.get("vllm", {})

    result = {
        "gpu_memory_utilization": vllm_config.get("default_gpu_memory_utilization", 0.92),
        "max_model_len": vllm_config.get("default_max_model_len", 32768),
        "max_num_seqs": vllm_config.get("default_max_num_seqs", 32),
        "max_num_batched_tokens": vllm_config.get("default_max_num_batched_tokens", 16384),
        "tensor_parallel_size": vllm_config.get("default_tensor_parallel_size", 1)
    }

    cache_service.set(cache_key, result, ttl_seconds=60)
    return result


@manage_router.get("/queue")
async def get_queue_status():
    cache_key = "api:manage:queue:status"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    models = scheduler.get_available_models()
    queue_info = {}
    for model in models:
        queue_info[model] = {
            "active_requests": scheduler.get_active_requests(model),
            "concurrency_limit": scheduler.get_concurrency_limit(),
            "can_accept": scheduler.can_accept_request(model)
        }

    cache_service.set(cache_key, queue_info, ttl_seconds=3)
    return queue_info


# --- 限流管理接口 ---
_rate_limit_config = {
    "max_requests": 500,
    "window_seconds": 60
}
_rate_limit_stats = {
    "total_requests": 0,
    "rate_limited_requests": 0
}


@manage_router.get("/ratelimit/config")
async def get_rate_limit_config():
    return _rate_limit_config


@manage_router.put("/ratelimit/config")
async def update_rate_limit_config(new_config: dict):
    global _rate_limit_config
    if "max_requests" in new_config:
        _rate_limit_config["max_requests"] = new_config["max_requests"]
    if "window_seconds" in new_config:
        _rate_limit_config["window_seconds"] = new_config["window_seconds"]
    return _rate_limit_config


@manage_router.get("/ratelimit/stats")
async def get_rate_limit_stats():
    return _rate_limit_stats


@manage_router.get("/preload")
async def get_preload():
    cache_key = "api:manage:preload:status"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    result = {
        "preloaded_models": scheduler.get_preloaded_models(),
        "all_models": scheduler.get_available_models()
    }

    cache_service.set(cache_key, result, ttl_seconds=60)
    return result


@manage_router.post("/preload/{model_name}")
async def preload_model(model_name: str):
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    success = await scheduler.start_model(model_name)
    if success:
        _clear_model_caches()
        return {"status": "preloaded", "model": model_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to preload model {model_name}")


@manage_router.get("/preload/status")
async def get_preload_status():
    cache_key = "api:manage:preload:detailed"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    preloaded = scheduler.get_preloaded_models()
    all_models = scheduler.get_available_models()
    preload_status = {}
    for model in all_models:
        config = scheduler.get_model_config(model)
        preload_status[model] = {
            "preloaded": model in preloaded,
            "running": scheduler.is_model_running(model),
            "preload_config": config.get("preload", False) if config else False
        }

    result = {"preloaded_models": preloaded, "all_models": all_models, "status": preload_status}
    cache_service.set(cache_key, result, ttl_seconds=30)
    return result


@manage_router.post("/preload/{model_name}/enable")
async def enable_preload(model_name: str):
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    success = scheduler.schedule_preload(model_name)
    if success:
        return {"status": "preload_enabled", "model": model_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to enable preload for model {model_name}")


@manage_router.post("/preload/{model_name}/disable")
async def disable_preload(model_name: str):
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    success = scheduler.cancel_preload(model_name)
    if success:
        return {"status": "preload_disabled", "model": model_name}
    else:
        return {"status": "already_disabled", "model": model_name}


@manage_router.get("/preload/all")
async def preload_all_models():
    results = {}
    for model_name in scheduler.get_available_models():
        success = scheduler.schedule_preload(model_name)
        results[model_name] = {"status": "preloading" if success else "failed"}
    return results


@manage_router.get("/token/stats")
async def get_token_stats():
    cache_key = "api:manage:token:stats"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    result = metrics.get_token_stats()
    cache_service.set(cache_key, result, ttl_seconds=10)
    return result


@manage_router.get("/metrics")
async def get_metrics():
    cache_key = "api:manage:metrics"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    result = metrics.get_metrics()
    cache_service.set(cache_key, result, ttl_seconds=10)
    return result


@manage_router.post("/metrics/reset")
async def reset_metrics():
    metrics.reset()
    cache_service.delete("api:manage:metrics")
    return {"status": "reset"}


@manage_router.get("/health/alert")
async def check_alert_status():
    cache_key = "api:manage:health:alert"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    gpu_status = gpu_monitor.get_gpu_status()
    vllm_metrics = gpu_monitor.get_vllm_metrics()
    health_info = metrics.get_comprehensive_health_score(gpu_status, vllm_metrics)
    alert_reasons = metrics.get_alert_reasons()

    result = {
        "should_alert": health_info["overall"] < 70,
        "health_score": health_info["overall"],
        "status": health_info["status"],
        "alert_reasons": alert_reasons,
        "timestamp": datetime.now().isoformat()
    }

    cache_service.set(cache_key, result, ttl_seconds=10)
    return result


@manage_router.get("/metrics/health-detail")
async def get_health_detail():
    gpu_status = gpu_monitor.get_gpu_status()
    vllm_metrics = gpu_monitor.get_vllm_metrics()
    health_scores = metrics.get_comprehensive_health_score(gpu_status, vllm_metrics)

    gpu_avail = gpu_status is not None and gpu_status.get("status") == "available"
    gpu_utilization = 0
    gpu_temp = 0
    gpu_mem_used_pct = 0
    if gpu_status:
        gpu_utilization = gpu_status.get("utilization", 0)
        gpu_temp = gpu_status.get("temperature", 0)
        gpu_mem_used_pct = gpu_status.get("memory_utilization", 0)

    vllm_running = vllm_metrics is not None and vllm_metrics.get("vllm_available", False)
    vllm_active_requests = vllm_metrics.get("running_requests", 0) if vllm_metrics else 0

    return {
        "overall_score": health_scores.get("overall", 0),
        "status": health_scores.get("status", "unknown"),
        "checks": {
            "gpu": {
                "available": gpu_avail,
                "utilization": gpu_utilization,
                "temperature": gpu_temp,
                "memory_used_pct": gpu_mem_used_pct,
            },
            "go_backend": {
                "reachable": True,
                "response_time_ms": 0,
            },
            "python_backend": {
                "reachable": True,
                "response_time_ms": 0,
            },
            "vllm_service": {
                "running": vllm_running,
                "active_requests": vllm_active_requests,
            },
            "redis": {
                "available": True,
                "connected": True,
            },
        },
        "alert_reasons": health_scores.get("alerts") or [],
        "timestamp": datetime.now().isoformat(),
    }


@manage_router.get("/cache/status")
async def get_cache_status():
    return {
        "cache_updater": cache_updater.get_status(),
        "cache_service": cache_service.get_stats(),
        "timestamp": datetime.now().isoformat()
    }


@manage_router.post("/cache/refresh")
async def refresh_cache(endpoint: Optional[str] = None):
    if endpoint:
        patterns = {
            'models': 'api:v1:models',
            'gpu': ['api:manage:gpu:status', 'api:manage:gpu:summary'],
            'models_status': 'api:manage:models:status',
            'queue': 'api:manage:queue:status',
            'health': ['api:health', 'api:health:detailed', 'api:manage:health:alert'],
            'metrics': 'api:manage:metrics',
            'system': 'api:manage:system:status',
            'preload': ['api:manage:preload:status', 'api:manage:preload:detailed'],
            'v1_status': 'api:v1:status'
        }

        keys_to_delete = patterns.get(endpoint)
        if keys_to_delete:
            if isinstance(keys_to_delete, list):
                for key in keys_to_delete:
                    cache_service.delete(key)
            else:
                cache_service.delete(keys_to_delete)
            return {"status": "refreshed", "endpoint": endpoint}
        else:
            return {"status": "error", "message": f"Unknown endpoint: {endpoint}"}
    else:
        cache_service.flush_all()
        return {"status": "all_refreshed"}


async def verify_go_config_consistency(config: Dict[str, Any]) -> tuple:
    """Verify config consistency with Go backend.

    Returns:
        (consistent: bool, message: str)
    """
    go_backend_url = os.getenv("GO_VLLM_API_URL", "http://localhost:35001")
    verify_url = f"{go_backend_url}/manage/config/verify"

    try:
        import aiohttp
        import json

        payload = {
            "version": config_watcher.get_version(),
            "config": config
        }

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(verify_url, json=payload) as resp:
                result = await resp.json()

                if resp.status == 200 and result.get("consistent"):
                    return True, "Go config is consistent with Python config"
                else:
                    differences = result.get("differences", [])
                    msg = f"Go config inconsistent: {'; '.join(differences)}"
                    _logger.warning("Config consistency check failed: %s", msg)
                    return False, msg
    except ImportError:
        _logger.warning("aiohttp not installed, skipping Go config consistency check")
        return True, "Skipped (aiohttp not installed)"
    except Exception as e:
        _logger.warning("Failed to verify Go config consistency: %s", e)
        return True, f"Skipped (connection error: {e})"


@manage_router.get("/cache/stats")
async def get_cache_stats():
    return cache_service.get_stats()


@manage_router.get("/config")
async def get_config():
    cfg = config_watcher.get_config()
    cfg["version"] = config_watcher.get_version()
    return cfg


@manage_router.put("/config")
async def update_config(request: Request):
    import yaml
    try:
        body = await request.json()

        expected_version = body.get("version")
        ok, current_version = config_watcher.check_version(expected_version)
        if not ok:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "version conflict",
                    "message": f"Expected version {expected_version}, but current is {current_version}. Please fetch the latest config and retry.",
                    "current_version": current_version,
                },
            )

        current_config = copy.deepcopy(config_watcher.get_config())

        if 'settings' in body:
            if 'settings' not in current_config:
                current_config['settings'] = {}
            current_config['settings'].update(body['settings'])

        if 'models' in body:
            if 'models' not in current_config:
                current_config['models'] = {}
            current_config['models'].update(body['models'])

        if 'vllm' in body:
            if 'vllm' not in current_config:
                current_config['vllm'] = {}
            current_config['vllm'].update(body['vllm'])

        before_config = copy.deepcopy(config_watcher.get_config())

        success = config_watcher.save_config(current_config)

        if success:
            from core.deps import _on_config_changed
            persisted_config = copy.deepcopy(config_watcher.get_config())
            _on_config_changed(persisted_config)

            operator = request.headers.get("X-Operator", "anonymous")
            config_watcher.log_operation(operator, "update", before_config, persisted_config)

            go_consistent, go_message = await verify_go_config_consistency(persisted_config)

            persisted_config["version"] = config_watcher.get_version()
            result = {"status": "success", "message": "Configuration updated and persisted", "config": persisted_config, "version": config_watcher.get_version()}
            if not go_consistent:
                result["go_consistency"] = {"consistent": False, "message": go_message}
            return result
        else:
            detail = config_watcher.get_last_error() or "Failed to persist configuration"
            raise HTTPException(status_code=400, detail=detail)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML format: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@manage_router.post("/config/reload")
async def reload_config():
    ok, new_config = config_watcher.load_config_with_status()
    if not ok:
        detail = config_watcher.get_last_error() or "Failed to reload configuration"
        raise HTTPException(status_code=400, detail=detail)
    from core.deps import _on_config_changed
    _on_config_changed(new_config)
    return {"status": "reloaded", "config": new_config}


@manage_router.get("/config/operation-log")
async def get_config_operation_log(limit: int = 50):
    from core.config_watcher import CONFIG_LOG_FILE
    if not os.path.exists(CONFIG_LOG_FILE):
        return {"items": [], "total": 0}
    items = []
    with open(CONFIG_LOG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                items.append({"raw": line})
    sliced = items[-max(1, min(limit, 500)):]
    return {"items": list(reversed(sliced)), "total": len(items)}


@manage_router.get("/service/status")
async def get_python_service_status(refresh: Optional[bool] = False):
    cache_key = "api:manage:service:status"

    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached

    services = {}
    for service in llm_service_manager.list_services():
        service_name = service.get("service_name") or f"service-{len(services)}"
        engine = service.get("engine_type") or "unknown"
        services[service_name] = {
            "running": service.get("status") == "running",
            "engine": engine,
            "port": service.get("port"),
            "pid": service.get("pid"),
            "started_at": datetime.fromtimestamp(
                time.time() - float(service.get("uptime_seconds", 0) or 0)
            ).isoformat() if service.get("status") == "running" else None,
        }

    if not services:
        service_name = "aiclient-python"
        status = sys_controller.get_service_status(service_name)
        service_info = sys_controller.get_service_info(service_name) or {}
        pid_raw = service_info.get("ExecMainPID") or service_info.get("MainPID")
        pid = None
        try:
            if pid_raw is not None:
                parsed_pid = int(pid_raw)
                pid = parsed_pid if parsed_pid > 0 else None
        except (TypeError, ValueError):
            pid = None
        services[service_name] = {
            "running": status == "active",
            "engine": "python",
            "port": None,
            "pid": pid,
            "started_at": None,
        }

    cache_service.set(cache_key, services, ttl_seconds=5)
    return services


@manage_router.get("/service/logs")
async def get_service_logs(lines: int = 100, service: str = "vllm-aiclient"):
    import subprocess
    try:
        result = subprocess.run(
            ["journalctl", "-u", service, "--no-pager", "-n", str(lines)],
            capture_output=True, text=True, timeout=10
        )
        log_lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        return {"logs": log_lines, "count": len(log_lines), "service": service}
    except subprocess.TimeoutExpired:
        return {"logs": [], "count": 0, "error": "日志读取超时"}
    except FileNotFoundError:
        return {"logs": [], "count": 0, "error": "journalctl 不可用"}
    except Exception as e:
        return {"logs": [], "count": 0, "error": str(e)}


@manage_router.post("/service/start")
async def start_python_service(request: ServiceControlRequest = None):
    service_name = request.service_name if request and request.service_name else "aiclient-python"
    success = sys_controller.start_service(service_name)
    if success:
        return {"status": "started", "service": service_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to start service: {service_name}")


@manage_router.post("/service/stop")
async def stop_python_service(request: ServiceControlRequest = None):
    service_name = request.service_name if request and request.service_name else "aiclient-python"

    success = sys_controller.stop_service(service_name)
    if success:
        return {"status": "stopped", "service": service_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to stop service: {service_name}")


@manage_router.post("/service/restart")
async def restart_python_service(request: ServiceControlRequest = None):
    service_name = request.service_name if request and request.service_name else "aiclient-python"

    success = sys_controller.restart_service(service_name)
    if success:
        return {"status": "restarted", "service": service_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to restart service: {service_name}")


@manage_router.get("/system/status")
async def system_status(include_history: bool = False, history_count: int = 60):
    cache_key = f"api:manage:system:status:{include_history}:{history_count}"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    import psutil

    cpu_percent = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    # 获取队列信息
    models = scheduler.get_available_models()
    queue_info = {}
    for model in models:
        queue_info[model] = {
            "active_requests": scheduler.get_active_requests(model),
            "concurrency_limit": scheduler.get_concurrency_limit(),
            "can_accept": scheduler.can_accept_request(model)
        }

    result = {
        "cpu": {
            "percent": cpu_percent,
            "cores": psutil.cpu_count(),
            "cores_physical": psutil.cpu_count(logical=False)
        },
        "memory": {
            "total_mb": memory.total // (1024**2),
            "available_mb": memory.available // (1024**2),
            "used_mb": memory.used // (1024**2),
            "percent": memory.percent
        },
        "disk": {
            "total_gb": disk.total // (1024**3),
            "used_gb": disk.used // (1024**3),
            "free_gb": disk.free // (1024**3),
            "percent": disk.percent
        },
        "queue": queue_info,
        "timestamp": datetime.now().isoformat()
    }
    
    if include_history:
        from core.deps import system_monitor
        result["history"] = system_monitor.get_system_history(history_count)

    cache_service.set(cache_key, result, ttl_seconds=5)
    return result

@manage_router.get("/system/history")
async def get_system_history(count: int = 60):
    from core.deps import system_monitor
    history = system_monitor.get_system_history(count)
    return {
        "history": history,
        "count": len(history)
    }

@manage_router.get("/token/history")
async def get_token_history(count: int = 60):
    history = metrics.get_token_history(count)
    return {
        "history": history,
        "count": len(history)
    }


@manage_router.get("/websocket/connections")
async def get_websocket_connections():
    return ws_manager.get_connection_stats()


@manage_router.get("/redis/health")
async def redis_health_check():
    try:
        connected = redis_client.is_connected()
        info = {}

        if connected:
            client = redis_client.get_client()
            if client:
                info = client.info()

        return {
            "status": "healthy" if connected else "unhealthy",
            "connected": connected,
            "info": info,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "connected": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@manage_router.get("/redis/keys")
async def get_redis_keys(pattern: str = "*"):
    try:
        if not redis_client.is_connected():
            raise HTTPException(status_code=503, detail="Redis not connected")

        keys = redis_client.keys(pattern)
        return {"keys": keys, "count": len(keys)}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.exception("Failed to get Redis keys")
        raise HTTPException(status_code=500, detail=f"Failed to get Redis keys: {str(e)}")


@manage_router.delete("/redis/flush")
async def flush_redis():
    try:
        if not redis_client.is_connected():
            raise HTTPException(status_code=503, detail="Redis not connected")

        success = redis_client.flush_db()
        return {"status": "success" if success else "failed"}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.exception("Failed to flush Redis")
        raise HTTPException(status_code=500, detail=f"Failed to flush Redis: {str(e)}")


@manage_router.get("/logs/test")
async def test_structured_logging():
    structured_logger.info("Test message", test=True, value=42)
    structured_logger.warning("Warning test", level="high")
    structured_logger.log_request("/test", "GET", 200, 0.123)
    structured_logger.log_model_event("test-model", "started", duration=10.5)
    return {"status": "logging_test_completed"}


@manage_router.get("/monitor/all")
async def get_monitor_all():
    gpu_summary = gpu_monitor.get_gpu_summary()
    models = scheduler.get_available_models()

    model_status = {}
    for model in models:
        model_status[model] = {
            "running": scheduler.is_model_running(model),
            "port": scheduler.get_model_port(model),
            "service": scheduler.get_model_service(model),
            "active_requests": scheduler.get_active_requests(model),
            "preloaded": scheduler.is_model_preloaded(model),
            "last_used": scheduler.get_model_last_used(model).isoformat() if scheduler.get_model_last_used(model) else None,
            "supports_images": scheduler.get_model_supports_images(model),
            "supports_tool_calling": scheduler.get_model_supports_tool_calling(model),
            "supports_image_generation": scheduler.get_model_supports_image_generation(model),
        }

    queue_info = {}
    for model in models:
        queue_info[model] = {
            "active_requests": scheduler.get_active_requests(model),
            "concurrency_limit": scheduler.get_concurrency_limit(),
            "can_accept": scheduler.can_accept_request(model)
        }

    model_summary = []
    for model in models:
        config = scheduler.get_model_config(model)
        model_summary.append({
            "name": model,
            "running": scheduler.is_model_running(model),
            "preloaded": scheduler.is_model_preloaded(model),
            "supports_images": scheduler.get_model_supports_images(model),
            "supports_tool_calling": scheduler.get_model_supports_tool_calling(model),
            "supports_image_generation": scheduler.get_model_supports_image_generation(model),
            "description": config.get("description", "") if config else "",
            "required_memory": config.get("required_memory", "") if config else "",
            "port": scheduler.get_model_port(model)
        })

    gpu_status = gpu_monitor.get_gpu_status()
    vllm_metrics = gpu_monitor.get_vllm_metrics()
    health_info = metrics.get_comprehensive_health_score(gpu_status, vllm_metrics)

    service_name = "aiclient-python"
    service_info = {
        "service": service_name,
        "status": sys_controller.get_service_status(service_name),
        "running": sys_controller.is_service_running(service_name),
        "info": sys_controller.get_service_info(service_name)
    }

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "gpu": gpu_summary,
        "models": model_status,
        "queue": queue_info,
        "summary": {
            "models": model_summary,
            "total": len(model_summary),
            "running_model": scheduler.get_current_model_name()
        },
        "health": {
            "status": health_info["status"],
            "health_score": health_info["overall"],
            "details": health_info
        },
        "service": service_info
    }


@integration_router.get("/status")
async def node_integration_status():
    cache_key = "api:v1:status"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    gpu_status = gpu_monitor.get_gpu_status()
    models = scheduler.get_available_models()
    model_statuses = {}
    for model in models:
        model_statuses[model] = {
            "available": scheduler.is_model_available(model),
            "running": scheduler.is_model_running(model),
            "preloaded": scheduler.is_model_preloaded(model),
            "port": scheduler.get_model_port(model),
            "supports_images": scheduler.get_model_supports_images(model),
            "supports_tool_calling": scheduler.get_model_supports_tool_calling(model),
            "supports_image_generation": scheduler.get_model_supports_image_generation(model),
            "active_requests": scheduler.get_active_requests(model),
            "can_accept": scheduler.can_accept_request(model)
        }

    result = {
        "service": "ai-controller",
        "status": "healthy" if gpu_status else "degraded",
        "timestamp": datetime.now().isoformat(),
        "gpu": {
            "available": gpu_status is not None,
            "memory_mb": gpu_status.get("total_memory", 0) // (1024**2) if gpu_status else 0,
            "used_mb": gpu_status.get("used_memory", 0) // (1024**2) if gpu_status else 0,
            "utilization_percent": gpu_status.get("utilization", 0) if gpu_status else 0
        } if gpu_status else {"available": False},
        "models": model_statuses,
        "queue": {
            "concurrency_limit": scheduler.get_concurrency_limit()
        }
    }

    cache_service.set(cache_key, result, ttl_seconds=5)
    return result


@integration_router.get("/models/{model_name}/info")
async def model_info(model_name: str, refresh: Optional[bool] = False):
    cache_key = f"api:v1:models:{model_name}:info"

    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached

    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    config = scheduler.get_model_config(model_name)
    result = {
        "name": model_name,
        "available": True,
        "running": scheduler.is_model_running(model_name),
        "preloaded": scheduler.is_model_preloaded(model_name),
        "port": scheduler.get_model_port(model_name),
        "model_path": scheduler.get_model_path(model_name),
        "service": scheduler.get_model_service(model_name),
        "supports_images": scheduler.get_model_supports_images(model_name),
        "supports_tool_calling": scheduler.get_model_supports_tool_calling(model_name),
        "supports_image_generation": scheduler.get_model_supports_image_generation(model_name),
        "description": config.get("description", "") if config else "",
        "required_memory": config.get("required_memory", "") if config else "",
        "active_requests": scheduler.get_active_requests(model_name),
        "can_accept": scheduler.can_accept_request(model_name),
        "last_used": scheduler.get_model_last_used(model_name).isoformat() if scheduler.get_model_last_used(model_name) else None
    }

    cache_service.set(cache_key, result, ttl_seconds=10)
    return result


@manage_router.get("/models/{model_name}/vllm-params")
async def get_model_vllm_params_route(model_name: str):
    params = get_model_vllm_params(model_name)
    return {"model_name": model_name, "vllm_params": params}


@manage_router.put("/models/{model_name}/vllm-params")
async def update_model_vllm_params(model_name: str, request: Request):
    try:
        body = await request.json()
        vllm_params = body.get("vllm_params", {})
        
        required_keys = ["max_num_seqs", "gpu_memory_utilization", "max_model_len"]
        for key in required_keys:
            if key not in vllm_params:
                raise HTTPException(status_code=400, detail=f"Missing required parameter: {key}")
        
        if not (0 < vllm_params["gpu_memory_utilization"] <= 1.0):
            raise HTTPException(status_code=400, detail="gpu_memory_utilization must be between 0 and 1")
        
        if vllm_params["max_num_seqs"] < 1 or vllm_params["max_num_seqs"] > 1024:
            raise HTTPException(status_code=400, detail="max_num_seqs must be between 1 and 1024")
        
        if vllm_params["max_model_len"] < 1024 or vllm_params["max_model_len"] > 131072:
            raise HTTPException(status_code=400, detail="max_model_len must be between 1024 and 131072")
        
        success = save_model_vllm_params(model_name, vllm_params)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save vLLM parameters")
        
        cache_service.delete("api:manage:models:aggregated")
        return {"status": "success", "model_name": model_name, "vllm_params": vllm_params}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update vLLM parameters: {str(e)}")


# ===== Model Hub 新增路由 =====

@manage_router.get("/models/search")
async def search_models(keyword: str, source: str = "all", limit: int = 10, sort: Optional[str] = None):
    if not keyword:
        raise HTTPException(status_code=400, detail="缺少keyword参数")
    try:
        results = model_engine_scheduler.search(keyword, source, limit, sort=sort)
        return {
            "results": [r.__dict__ for r in results],
            "total": len(results),
            "keyword": keyword,
            "source": source,
            "sort": sort,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"搜索失败: {str(e)}")


@manage_router.get("/gpu/recommend")
async def recommend_model(keyword: str, source: str = "all"):
    if not keyword:
        raise HTTPException(status_code=400, detail="缺少keyword参数")
    try:
        result = model_engine_scheduler.recommend(keyword, source)
        rec = result.get("recommended")
        return {
            "recommended": rec.__dict__ if rec else None,
            "gpu_info": result.get("gpu_info"),
            "candidates": [r.__dict__ for r in result.get("candidates", [])],
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"推荐失败: {str(e)}")


@manage_router.get("/gpu/memory-check")
async def get_gpu_memory_info():
    gpu_info = gpu_memory_manager.get_gpu_info()
    if not gpu_info:
        from core.gpu_memory_checker import GPUMemoryChecker
        checker = GPUMemoryChecker()
        gpu_info = checker.detect_all()
    loaded_models = gpu_memory_manager.get_loaded_models_summary()
    return {
        "gpu": gpu_info,
        "loaded_models": loaded_models,
        "timestamp": datetime.now().isoformat(),
    }


@manage_router.post("/gpu/memory-check/{model_name}")
async def check_model_memory(model_name: str):
    from core.gpu_memory_manager import GPUMemoryManager as _GM
    size_b = _GM(None)._parse_size(model_name) if hasattr(_GM(None), '_parse_size') else None
    quant = _GM(None)._parse_quant(model_name) if hasattr(_GM(None), '_parse_quant') else None
    import re
    size_match = re.search(r'(\d+(?:\.\d+)?)B', model_name, re.IGNORECASE)
    if not size_match:
        raise HTTPException(status_code=404, detail="无法从模型名提取参数大小")
    size_b = float(size_match.group(1))
    quant_match = re.search(r'(4bit|int4|8bit|int8|fp16|awq|gptq|gguf)', model_name, re.IGNORECASE)
    quant = quant_match.group(1).lower() if quant_match else None
    result = gpu_memory_manager.check_model_feasibility(model_name, size_b=size_b, quant=quant)
    if not result.get("gpu_available"):
        raise HTTPException(status_code=503, detail="GPU检测失败，无法校验显存")
    return result


@manage_router.post("/models/download")
async def start_download(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")
    model_name = body.get("model_name")
    source = body.get("source", "hf")
    save_dir = body.get("save_dir")
    if not model_name:
        raise HTTPException(status_code=400, detail="缺少model_name参数")
    result = download_task_manager.create_task(
        model_name, source, save_dir,
        hf_token=body.get("hf_token"),
        allow_patterns=body.get("allow_patterns"),
        ignore_patterns=body.get("ignore_patterns"),
        max_workers=body.get("max_workers"),
        force_download=body.get("force_download", False),
    )
    if result.get("status") == "error":
        code = 507 if "磁盘" in result.get("message", "") else 500
        raise HTTPException(status_code=code, detail=result.get("message"))
    if result.get("status") == "already_exists":
        return {"status": "already_exists", "local_path": result.get("local_path"), "model_name": result.get("model_name")}
    return result


@manage_router.get("/models/download/{task_id}/status")
async def get_download_status(task_id: str):
    result = download_task_manager.get_status(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="任务不存在")
    return result


@manage_router.delete("/models/download/{task_id}")
async def cancel_download(task_id: str):
    result = download_task_manager.cancel_task(task_id)
    if not result.get("cancelled"):
        raise HTTPException(status_code=404, detail=result.get("reason", "取消失败"))
    return result


@manage_router.get("/models/downloads")
async def list_downloads(status_filter: Optional[str] = None):
    return download_task_manager.list_tasks(status_filter)


@manage_router.post("/models/download/{task_id}/retry")
async def retry_download(task_id: str):
    result = download_task_manager.retry_task(task_id)
    if not result.get("success"):
        code = 404 if "not_found" in result.get("reason", "") else 409
        raise HTTPException(status_code=code, detail=result.get("reason", "retry_failed"))
    return result


@manage_router.get("/models/pool")
async def pool_list(filter: str = "all", page: int = 1, page_size: int = 50):
    entries = model_pool_manager.get_pool_list(filter, page, page_size)
    return {
        "models": entries if entries and isinstance(entries[0], dict) else [e.__dict__ if hasattr(e, '__dict__') else e for e in entries],
        "total": len(model_pool_manager._pool),
        "page": page,
        "page_size": page_size,
    }


@manage_router.get("/models/pool/{model_key}")
async def pool_detail(model_key: str):
    entry = model_pool_manager.get_pool_detail(model_key)
    if not entry:
        raise HTTPException(status_code=404, detail="模型不在池中")
    return entry if isinstance(entry, dict) else entry.__dict__


@manage_router.post("/models/pool/{model_key}/load")
async def pool_load(model_key: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    engine = body.get("engine", "vllm")
    result = model_pool_manager.load_model(model_key, engine)
    if not result.get("success"):
        code = 409 if result.get("reason") in ("model_already_running", "insufficient_gpu_memory") else 404
        raise HTTPException(status_code=code, detail=result.get("reason"))
    return result


@manage_router.delete("/models/pool/{model_key}")
async def pool_delete(model_key: str, remove_files: bool = False):
    result = model_pool_manager.delete_model(model_key, remove_files)
    if not result.get("deleted"):
        code = 409 if "running" in result.get("reason", "") else 404
        raise HTTPException(status_code=code, detail=result.get("reason"))
    return result


@manage_router.post("/models/pool/register")
async def pool_register(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    model_name = body.get("model_name")
    source = body.get("source", "search")
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name required")
    entry = model_pool_manager.register_from_search(
        model_name=model_name,
        source=source,
        size_b=body.get("size_b"),
        quant=body.get("quant"),
        required_gb=body.get("required_gb"),
        feasible=body.get("feasible"),
    )
    return entry.to_dict()


@manage_router.post("/models/pool/sync-config")
async def pool_sync_config():
    result = model_pool_manager.sync_to_config()
    if not result:
        raise HTTPException(status_code=500, detail="Failed to sync pool to config")
    return {"status": "success", "message": "Pool synced to config.yaml"}


@manage_router.post("/engines/switch")
async def engine_switch(request: Request):
    from core.deps import model_switch_orchestrator
    if model_switch_orchestrator.is_switching:
        current = model_switch_orchestrator.current_session
        raise HTTPException(
            status_code=409,
            detail={
                "error": "模型切换正在进行中，无法同时切换引擎",
                "session_id": current.session_id if current else None,
                "target_model": current.target_model if current else None,
            }
        )

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    model_name = body.get("model_name") or body.get("target_model")
    engine_type = body.get("engine_type") or body.get("engine") or "vllm"
    port = body.get("port", 8000)
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name required")
    result = model_engine_scheduler.switch_engine(model_name, engine_type, port)
    if not result.get("success"):
        code = 409 if result.get("reason") == "insufficient_gpu_memory" else 500
        raise HTTPException(status_code=code, detail=result.get("reason", "switch_failed"))
    return result


@manage_router.get("/engines/status")
async def engine_status():
    import httpx
    from core.vllm_manager import get_current_model_info
    services = llm_service_manager.list_services()
    if not services:
        current_info = get_current_model_info()
        if current_info and current_info.get("running"):
            try:
                import psutil
                model_name = current_info.get("name", "")
                configured_engine = "vllm"
                config = scheduler.get_model_config(model_name) or {}
                configured_engine = config.get("engine_type", "vllm")
                service_port = config.get("port", 8000)

                engine_patterns = {
                    "vllm": ["VLLM", "vllm"],
                    "sglang": ["SGLANG", "sglang", "python -m sglang"],
                    "llamacpp": ["LLAMACPP", "llama.cpp", "llama-server", "llama-cli"],
                }
                discovered_engine = "vllm"
                vllm_pid = None
                for engine_type, patterns in engine_patterns.items():
                    for pattern in patterns:
                        try:
                            pids = [p.info['pid'] for p in psutil.process_iter(['pid', 'name', 'cmdline'])
                                    if p.info['name'] and pattern.upper() in (p.info['name'] or '').upper()]
                            if not pids:
                                pids = [p.info['pid'] for p in psutil.process_iter(['pid', 'name', 'cmdline'])
                                        if p.info['cmdline'] and any(pattern in (c or '') for c in p.info['cmdline'])]
                            if pids:
                                vllm_pid = pids[0]
                                discovered_engine = engine_type
                                break
                        except Exception:
                            pass
                    if vllm_pid:
                        break
            except Exception:
                vllm_pid = None
                discovered_engine = "vllm"
                model_name = current_info.get("name", "")
                service_port = 8000
            uptime = None
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(f"http://localhost:{service_port}/v1/models")
                    if resp.status_code == 200:
                        health = "healthy"
                    else:
                        health = "unhealthy"
            except Exception:
                health = "unknown"
            services.append({
                "status": "running",
                "service_name": current_info.get("service", "vllm-aiclient"),
                "engine_type": discovered_engine,
                "engine": discovered_engine,
                "pid": vllm_pid,
                "port": service_port,
                "model_name": model_name,
                "model": model_name,
                "health": health,
                "uptime_seconds": None,
            })
    current_engine = "vllm"
    if services:
        running_services = [s for s in services if s.get("status") == "running"]
        if running_services:
            current_engine = running_services[0].get("engine_type", "vllm")
    return {
        "engine_manager_mode": os.environ.get("ENGINE_MANAGER_MODE", "subprocess"),
        "services": services,
        "active_count": len([s for s in services if s.get("status") == "running"]),
        "current_engine": current_engine,
    }


@manage_router.get("/engines/config")
async def get_engines_config():
    current_config = config_watcher.get_config()
    engines_config = {}
    if hasattr(current_config, 'sglang'):
        engines_config["sglang"] = current_config.sglang.__dict__ if hasattr(current_config.sglang, '__dict__') else current_config.sglang
    elif 'sglang' in (current_config if isinstance(current_config, dict) else {}):
        engines_config["sglang"] = current_config['sglang']
    vllm_cfg = {}
    if hasattr(current_config, 'vllm'):
        vllm_cfg = current_config.vllm.__dict__ if hasattr(current_config.vllm, '__dict__') else current_config.vllm
    elif 'vllm' in (current_config if isinstance(current_config, dict) else {}):
        vllm_cfg = current_config['vllm']
    engines_config["vllm"] = vllm_cfg
    engines_config["default_engine"] = os.environ.get("DEFAULT_ENGINE", "vllm")
    engines_config["engine_manager_mode"] = os.environ.get("ENGINE_MANAGER_MODE", "subprocess")
    return engines_config


@manage_router.put("/engines/config")
async def update_engines_config(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    current_config = config_watcher.get_config()
    config_dict = copy.deepcopy(current_config) if isinstance(current_config, dict) else copy.deepcopy(current_config.__dict__) if hasattr(current_config, '__dict__') else {}
    if "default_engine" in body:
        os.environ["DEFAULT_ENGINE"] = body["default_engine"]
    if "engine_manager_mode" in body:
        os.environ["ENGINE_MANAGER_MODE"] = body["engine_manager_mode"]
    if "sglang" in body:
        config_dict["sglang"] = body["sglang"]
    if "vllm" in body:
        if "vllm" not in config_dict:
            config_dict["vllm"] = {}
        config_dict["vllm"].update(body["vllm"])
    success = config_watcher.save_config(config_dict)
    if success:
        persisted = config_watcher.get_config()
        from core.deps import _on_config_changed
        _on_config_changed(persisted)
        return {"status": "success", "engines_config": {
            "default_engine": os.environ.get("DEFAULT_ENGINE", "vllm"),
            "engine_manager_mode": os.environ.get("ENGINE_MANAGER_MODE", "subprocess"),
        }}
    raise HTTPException(status_code=500, detail="Failed to persist engines config")


# ===== Model Benchmark =====

@manage_router.post("/models/{model_name}/benchmark")
async def benchmark_model(model_name: str):
    if not scheduler.is_model_available(model_name):
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not available")
    try:
        report = await model_tester.run_tests(model_name)
        report_dict = _serialize_report(report)
        return {
            "status": "found",
            "model_name": model_name,
            "report": report_dict,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {str(e)}")


@manage_router.get("/models/{model_name}/benchmark")
async def get_benchmark_report(model_name: str):
    report = model_tester.get_previous_report(model_name)
    if not report:
        raise HTTPException(status_code=404, detail=f"No benchmark report for '{model_name}'")
    return {
        "status": "found",
        "model_name": model_name,
        "report": _serialize_report(report),
    }


@manage_router.get("/models/benchmarks/history")
async def get_benchmark_history():
    all_reports = model_tester.get_all_reports()
    history = []
    for model_name, report in all_reports.items():
        history.append({
            "model_name": model_name,
            "timestamp": report.test_timestamp if hasattr(report, 'test_timestamp') else "",
            "status": report.overall_status if hasattr(report, 'overall_status') else "unknown",
            "duration": report.resource_utilization.get("test_duration_seconds", 0) if hasattr(report, 'resource_utilization') else 0,
        })
    return {
        "status": "ok",
        "reports": {k: _serialize_report(v) for k, v in all_reports.items()},
        "history": sorted(history, key=lambda x: x["timestamp"], reverse=True),
    }


def _serialize_report(report: Any) -> Dict[str, Any]:
    if report is None:
        return {}
    try:
        from dataclasses import asdict, is_dataclass
        if is_dataclass(report):
            return _dataclass_to_dict(report)
    except ImportError:
        pass
    if hasattr(report, '__dict__') and not isinstance(report, dict):
        return {k: _safe_value(v) for k, v in vars(report).items()}
    if isinstance(report, dict):
        return {k: _safe_value(v) for k, v in report.items()}
    return _safe_value(report)


def _safe_value(val: Any) -> Any:
    if val is None:
        return None
    if hasattr(val, 'value'):
        return val.value
    if isinstance(val, (int, float, str, bool)):
        return val
    if isinstance(val, list):
        return [_safe_value(item) for item in val]
    if isinstance(val, dict):
        return {k: _safe_value(v) for k, v in val.items()}
    try:
        from dataclasses import is_dataclass
        if is_dataclass(val):
            return _dataclass_to_dict(val)
    except ImportError:
        pass
    if hasattr(val, '__dict__'):
        return {k: _safe_value(v) for k, v in vars(val).items()}
    return str(val)


def _dataclass_to_dict(obj: Any) -> Dict[str, Any]:
    return {k: _safe_value(v) for k, v in vars(obj).items() if not k.startswith('_')}


@manage_router.post("/models/benchmark/comparative")
async def comparative_benchmark(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    model_names = body.get("model_names", [])
    if not model_names or len(model_names) < 2:
        raise HTTPException(status_code=400, detail="At least 2 model names required")
    try:
        analysis = await model_tester.run_comparative_analysis(model_names)
        return {"status": "completed", "analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparative benchmark failed: {str(e)}")


# ===== Scheduler 统一调度器路由 =====

@manage_router.get("/scheduler/status")
async def get_scheduler_status():
    return model_engine_scheduler.get_scheduler_status()


@manage_router.get("/scheduler/pool")
async def get_scheduler_model_pool():
    pool = model_engine_scheduler.get_model_pool()
    return {"pool": pool, "total": len(pool)}


@manage_router.get("/gpu/realtime")
async def get_gpu_realtime(device_id: int = 0):
    info = model_engine_scheduler.get_realtime_gpu_info(device_id)
    if not info.get("available"):
        raise HTTPException(status_code=503, detail=info.get("reason", "GPU不可用"))
    return info


@manage_router.get("/engines/param-schema")
async def get_engine_param_schema():
    from core.engine_param_schema import ENGINE_PARAM_SCHEMA
    return ENGINE_PARAM_SCHEMA


@manage_router.get("/models/{model_name}/engine-params")
async def get_model_engine_params(model_name: str):
    current_config = config_watcher.get_config()
    model_cfg = current_config.models.get(model_name) if hasattr(current_config, 'models') else None
    if not model_cfg:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    engine_type = model_cfg.engine_type if hasattr(model_cfg, 'engine_type') else "vllm"
    params = {}
    if engine_type == "vllm":
        params = model_cfg.vllm_params if hasattr(model_cfg, 'vllm_params') else {}
    elif engine_type == "sglang":
        params = model_cfg.sglang_params if hasattr(model_cfg, 'sglang_params') else {}
    elif engine_type == "llamacpp":
        llamacpp_specific = {}
        if hasattr(model_cfg, 'n_gpu_layers') and model_cfg.n_gpu_layers != -1:
            llamacpp_specific["n_gpu_layers"] = model_cfg.n_gpu_layers
        if hasattr(model_cfg, 'ctx_size') and model_cfg.ctx_size != 4096:
            llamacpp_specific["ctx_size"] = model_cfg.ctx_size
        if hasattr(model_cfg, 'n_threads') and model_cfg.n_threads is not None:
            llamacpp_specific["n_threads"] = model_cfg.n_threads
        llamacpp_from_dict = model_cfg.llamacpp_params if hasattr(model_cfg, 'llamacpp_params') else {}
        params = {**llamacpp_from_dict, **llamacpp_specific}
    return {
        "model_name": model_name,
        "engine_type": engine_type,
        "params": params,
    }


@manage_router.put("/models/{model_name}/engine-params")
async def update_model_engine_params(model_name: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    engine_type = body.get("engine_type")
    params = body.get("params", {})
    if not engine_type or engine_type not in ("vllm", "sglang", "llamacpp"):
        raise HTTPException(status_code=400, detail="engine_type must be vllm, sglang, or llamacpp")
    current_config = config_watcher.get_config()
    model_cfg = current_config.models.get(model_name) if hasattr(current_config, 'models') else None
    if not model_cfg:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    config_dict = copy.deepcopy(current_config.__dict__) if hasattr(current_config, '__dict__') else copy.deepcopy(current_config) if isinstance(current_config, dict) else {}
    models_dict = config_dict.get("models", {})
    if model_name not in models_dict:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not in config")
    model_dict = models_dict[model_name]
    if isinstance(model_dict, dict):
        model_dict["engine_type"] = engine_type
    elif hasattr(model_dict, '__dict__'):
        model_dict.__dict__["engine_type"] = engine_type
    param_key = f"{engine_type}_params"
    if engine_type == "llamacpp":
        for special_key in ("n_gpu_layers", "ctx_size", "n_threads"):
            if special_key in params:
                val = params.pop(special_key)
                if isinstance(model_dict, dict):
                    model_dict[special_key] = val
                elif hasattr(model_dict, '__dict__'):
                    model_dict.__dict__[special_key] = val
    if isinstance(model_dict, dict):
        model_dict[param_key] = params
    elif hasattr(model_dict, '__dict__'):
        model_dict.__dict__[param_key] = params
    success = config_watcher.save_config(config_dict)
    if success:
        return {"status": "success", "model_name": model_name, "engine_type": engine_type, "params": params}
    raise HTTPException(status_code=500, detail="Failed to persist config")


@manage_router.post("/engines/deploy")
async def deploy_model_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    model_name = body.get("model_name")
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name required")
    result = await model_engine_scheduler.auto_deploy_model(
        model_name=model_name,
        engine_type=body.get("engine_type"),
        port=body.get("port"),
        download_if_missing=body.get("download_if_missing", False),
        source=body.get("source"),
    )
    if not result.get("success"):
        stage = result.get("stage", "")
        code_map = {"insufficient_gpu_memory": 409, "download": 502, "service_not_ready": 503}
        code = code_map.get(stage, 500)
        raise HTTPException(status_code=code, detail=result.get("reason", "deploy_failed"))
    return result
