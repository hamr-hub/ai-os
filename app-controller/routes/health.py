from fastapi import APIRouter
from typing import Optional
from datetime import datetime

from core.deps import gpu_monitor, metrics, cache_service, prometheus, scheduler
from core.logger import setup_logger

health_router = APIRouter()
logger = setup_logger()


def _build_fallback_health(reason: str):
    return {
        "status": "critical",
        "timestamp": datetime.now().isoformat(),
        "health_score": 0,
        "details": {
            "overall": 0,
            "status": "critical",
            "service": 0,
            "gpu_overall": 0,
            "vllm_inference": 0,
            "response_time": 0,
            "alerts": [f"health check fallback: {reason}"],
        },
    }


@health_router.get("/health")
async def health_check(refresh: Optional[bool] = False):
    cache_key = "api:health"

    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached

    try:
        gpu_status = gpu_monitor.get_gpu_status()
        vllm_metrics = gpu_monitor.get_vllm_metrics()
        health_info = metrics.get_comprehensive_health_score(gpu_status, vllm_metrics)
        result = {
            "status": health_info["status"],
            "timestamp": datetime.now().isoformat(),
            "health_score": health_info["overall"],
            "details": health_info
        }
        cache_service.set(cache_key, result, ttl_seconds=5)
    except Exception as exc:
        logger.error(f"health_check failed: {exc}")
        result = _build_fallback_health(str(exc))
    return result


@health_router.get("/health/detailed")
async def health_check_detailed():
    cache_key = "api:health:detailed"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    try:
        gpu_status = gpu_monitor.get_gpu_status()
        vllm_metrics = gpu_monitor.get_vllm_metrics()
        health_info = metrics.get_comprehensive_health_score(gpu_status, vllm_metrics)
        result = {
            "status": health_info["status"],
            "timestamp": datetime.now().isoformat(),
            "scores": health_info,
            "gpu": gpu_status,
            "metrics": metrics.get_detailed_metrics()
        }
        cache_service.set(cache_key, result, ttl_seconds=5)
    except Exception as exc:
        logger.error(f"health_check_detailed failed: {exc}")
        fallback = _build_fallback_health(str(exc))
        result = {
            "status": fallback["status"],
            "timestamp": fallback["timestamp"],
            "scores": fallback["details"],
            "gpu": None,
            "metrics": {},
        }
    return result


@health_router.get("/metrics")
async def get_prometheus_metrics():
    try:
        gpu_status = gpu_monitor.get_gpu_status()
        vllm_metrics = gpu_monitor.get_vllm_metrics()
        prometheus.update_gpu_metrics(gpu_status)

        health_info = metrics.get_comprehensive_health_score(gpu_status, vllm_metrics)
        prometheus.set_health_score(health_info["overall"])

        for model_name in scheduler.get_available_models():
            prometheus.set_model_status(
                model_name,
                scheduler.get_model_service(model_name) or "",
                scheduler.is_model_running(model_name)
            )
            prometheus.set_active_requests(model_name, scheduler.get_active_requests(model_name))
    except Exception as exc:
        logger.error(f"get_prometheus_metrics failed: {exc}")

    return prometheus.generate_metrics()


@health_router.get("/metrics/metadata")
async def get_metrics_metadata():
    return prometheus.get_metrics_dict()


@health_router.get("/health/history")
async def get_health_history(count: int = 60):
    history = []
    try:
        gpu_history = gpu_monitor.get_gpu_history(count)
        for entry in gpu_history:
            ts = entry.get("timestamp", "")
            score = entry.get("health_score", 0)
            if isinstance(score, (int, float)):
                history.append({
                    "timestamp": ts,
                    "health_score": score,
                    "status": "healthy" if score >= 90 else "degraded" if score >= 70 else "critical",
                    "alert_count": len(entry.get("alert_reasons") or []),
                    "source": "gpu_history",
                })
    except Exception as exc:
        logger.error(f"get_health_history failed: {exc}")

    if not history:
        try:
            gpu_status = gpu_monitor.get_gpu_status()
            vllm_metrics = gpu_monitor.get_vllm_metrics()
            health_info = metrics.get_comprehensive_health_score(gpu_status, vllm_metrics)
            history.append({
                "timestamp": datetime.now().isoformat(),
                "health_score": health_info.get("overall", 0),
                "status": health_info.get("status", "unknown"),
                "alert_count": len(health_info.get("alerts") or []),
                "source": "current",
            })
        except Exception as exc:
            logger.error(f"get_health_history fallback failed: {exc}")

    return history
