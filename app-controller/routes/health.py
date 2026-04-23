from fastapi import APIRouter
from typing import Optional
from datetime import datetime

from core.deps import gpu_monitor, metrics, cache_service, prometheus, scheduler

health_router = APIRouter()


@health_router.get("/health")
async def health_check(refresh: Optional[bool] = False):
    cache_key = "api:health"

    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached

    gpu_status = gpu_monitor.get_gpu_status()
    health_info = metrics.get_comprehensive_health_score(gpu_status)
    result = {
        "status": health_info["status"],
        "timestamp": datetime.now().isoformat(),
        "health_score": health_info["overall"],
        "details": health_info
    }

    cache_service.set(cache_key, result, ttl_seconds=5)
    return result


@health_router.get("/health/detailed")
async def health_check_detailed():
    cache_key = "api:health:detailed"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    gpu_status = gpu_monitor.get_gpu_status()
    health_info = metrics.get_comprehensive_health_score(gpu_status)
    result = {
        "status": health_info["status"],
        "timestamp": datetime.now().isoformat(),
        "scores": health_info,
        "gpu": gpu_status,
        "metrics": metrics.get_detailed_metrics()
    }

    cache_service.set(cache_key, result, ttl_seconds=5)
    return result


@health_router.get("/metrics")
async def get_prometheus_metrics():
    gpu_status = gpu_monitor.get_gpu_status()
    prometheus.update_gpu_metrics(gpu_status)

    health_info = metrics.get_comprehensive_health_score(gpu_status)
    prometheus.set_health_score(health_info["overall"])

    for model_name in scheduler.get_available_models():
        prometheus.set_model_status(
            model_name,
            scheduler.get_model_service(model_name) or "",
            scheduler.is_model_running(model_name)
        )
        prometheus.set_active_requests(model_name, scheduler.get_active_requests(model_name))

    return prometheus.generate_metrics()


@health_router.get("/metrics/metadata")
async def get_metrics_metadata():
    return prometheus.get_metrics_dict()
