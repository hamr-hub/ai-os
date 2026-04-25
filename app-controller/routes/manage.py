from fastapi import APIRouter, HTTPException, Request
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio

from schemas.service import ServiceControlRequest
from core.deps import (
    scheduler as _scheduler, gpu_monitor as _gpu_monitor, sys_controller as _sys_controller,
    ws_manager as _ws_manager, metrics as _metrics, prometheus as _prometheus,
    cache_service as _cache_service, cache_updater as _cache_updater,
    structured_logger as _structured_logger, config_watcher as _config_watcher,
    logger as _logger, redis_client as _redis_client
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
from core.vllm_manager import switch_vllm_model_with_test
from core.llama_cpp_manager import llama_cpp_manager, test_llama_cpp_model
from middleware.error_handler import ModelNotFoundException

manage_router = APIRouter(prefix="/manage")
integration_router = APIRouter(prefix="/api/v1")


def _clear_model_caches():
    for key in [
        "api:manage:models:status", "api:manage:models:summary",
        "api:manage:preload:status", "api:manage:preload:detailed",
        "api:v1:status"
    ]:
        cache_service.delete(key)


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


@manage_router.post("/models/{model_name}/start")
async def start_model(model_name: str):
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    if scheduler.is_model_running(model_name):
        return {"status": "already_running", "model": model_name}

    success = await scheduler.start_model(model_name)
    if success:
        _clear_model_caches()
        return {"status": "starting", "model": model_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to start model {model_name}")


@manage_router.post("/models/{model_name}/stop")
async def stop_model(model_name: str):
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    if not scheduler.is_model_running(model_name):
        return {"status": "already_stopped", "model": model_name}

    success = await scheduler.stop_model(model_name)
    if success:
        _clear_model_caches()
        return {"status": "stopped", "model": model_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to stop model {model_name}")


@manage_router.post("/models/{model_name}/switch")
async def switch_to_model(model_name: str, test_enabled: Optional[bool] = True):
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    success = await scheduler.switch_model(model_name)
    if not success:
        raise HTTPException(status_code=503, detail=f"Failed to switch to model {model_name}, insufficient memory")

    scheduler.mark_model_selected(model_name)
    _clear_model_caches()

    if test_enabled:
        backend_type = scheduler.get_model_backend_type(model_name)

        if backend_type == 'llama_cpp':
            port = scheduler.get_model_port(model_name)
            test_result = await test_llama_cpp_model(model_name, port)

            if not test_result.get("success", False):
                error_msg = test_result.get("message", "Unknown error during model test")
                raise HTTPException(status_code=503, detail=f"Model switch successful but self-test failed: {error_msg}")

            return {
                "status": "switched_and_tested",
                "model": model_name,
                "backend_type": "llama_cpp",
                "test_result": test_result
            }

        model_config = scheduler.get_model_config(model_name)
        model_path = model_config.get('model_path', model_name) if model_config else model_name

        test_result = await switch_vllm_model_with_test(model_name, test_enabled=True, model_path=model_path)

        if not test_result.get("success", False):
            error_msg = test_result.get("error", "Unknown error during model test")
            raise HTTPException(status_code=503, detail=f"Model switch successful but self-test failed: {error_msg}")

        return {
            "status": "switched_and_tested",
            "model": model_name,
            "backend_type": "vllm",
            "test_result": test_result.get("test_result")
        }

    return {"status": "switched", "model": model_name}


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
    gpu_alerts = metrics.check_gpu_alerts(gpu_status or {}, vllm_metrics)
    return {
        "health_scores": health_scores,
        "gpu_alerts": gpu_alerts,
        "gpu_status_summary": gpu_status,
        "vllm_metrics_summary": vllm_metrics,
        "timestamp": datetime.now().isoformat()
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


@manage_router.get("/cache/stats")
async def get_cache_stats():
    return cache_service.get_stats()


@manage_router.get("/config")
async def get_config():
    return config_watcher.get_config()


@manage_router.put("/config")
async def update_config(request: Request):
    import yaml
    try:
        body = await request.json()

        current_config = config_watcher.get_config()

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

        success = config_watcher.save_config(current_config)

        if success:
            from core.deps import _on_config_changed
            _on_config_changed(current_config)
            return {"status": "success", "message": "Configuration updated and persisted", "config": current_config}
        else:
            raise HTTPException(status_code=500, detail="Failed to persist configuration")
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@manage_router.post("/config/reload")
async def reload_config():
    new_config = config_watcher.load_config()
    from core.deps import _on_config_changed
    _on_config_changed(new_config)
    return {"status": "reloaded", "config": new_config}


@manage_router.get("/service/status")
async def get_python_service_status(refresh: Optional[bool] = False):
    cache_key = "api:manage:service:status"

    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached

    service_name = "aiclient-python"
    status = sys_controller.get_service_status(service_name)
    service_info = sys_controller.get_service_info(service_name)
    current_config = config_watcher.get_config()

    result = {
        "service": service_name,
        "status": status,
        "running": status == "active",
        "info": service_info,
        "config": current_config,
        "config_file": config_watcher.config_path,
        "timestamp": datetime.now().isoformat()
    }

    cache_service.set(cache_key, result, ttl_seconds=5)
    return result


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

    cpu_percent = psutil.cpu_percent(interval=0.1)
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
    return {
        "history": system_monitor.get_system_history(count),
        "count": count
    }

@manage_router.get("/token/history")
async def get_token_history(count: int = 60):
    return {
        "history": metrics.get_token_history(count),
        "count": count
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


@manage_router.get("/llama_cpp/models")
async def list_llama_cpp_models():
    return {"models": scan_gguf_models(), "running": llama_cpp_manager.get_all_running_models()}


@manage_router.get("/llama_cpp/status")
async def llama_cpp_status():
    models = scheduler.get_available_models()
    llama_models = [m for m in models if scheduler.get_model_backend_type(m) == 'llama_cpp']
    status = {}
    for model_name in llama_models:
        status[model_name] = llama_cpp_manager.get_server_status(model_name)
    return {"models": status, "total": len(llama_models)}
