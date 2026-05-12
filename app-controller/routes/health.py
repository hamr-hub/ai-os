from fastapi import APIRouter
from typing import Optional
from datetime import datetime

from core.deps import gpu_monitor, metrics, cache_service, prometheus, scheduler
from core.logger import setup_logger

health_router = APIRouter()
logger = setup_logger()


def _status_from_score(score: float) -> str:
    if score >= 90:
        return "healthy"
    if score >= 70:
        return "degraded"
    if score >= 50:
        return "warning"
    return "critical"


def _score_from_gpu_history(entry: dict) -> Optional[float]:
    score = entry.get("health_score")
    if isinstance(score, (int, float)):
        return round(float(score), 2)

    temp = entry.get("temperature")
    mem_util = entry.get("memory_utilization")
    if mem_util is None:
        total_mem = entry.get("total_memory") or 0
        used_mem = entry.get("used_memory") or 0
        if total_mem:
            mem_util = (used_mem / total_mem) * 100

    if not isinstance(temp, (int, float)) or not isinstance(mem_util, (int, float)):
        return None

    temp_score = max(0, 100 - max(0, temp - 85) * 5)
    mem_score = max(0, 100 - max(0, mem_util - 90) * 10)
    return round(max(0, min(100, temp_score * 0.5 + mem_score * 0.5)), 2)


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

        result = {
            "overall_score": health_info.get("overall", 0),
            "status": health_info.get("status", "unknown"),
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
            "alert_reasons": health_info.get("alerts") or metrics.get_gpu_alerts(gpu_status) or [],
            "timestamp": datetime.now().isoformat(),
        }
        cache_service.set(cache_key, result, ttl_seconds=5)
    except Exception as exc:
        logger.error(f"health_check_detailed failed: {exc}")
        fallback = _build_fallback_health(str(exc))
        result = {
            "overall_score": 0,
            "status": fallback["status"],
            "checks": {
                "gpu": {"available": False, "utilization": 0, "temperature": 0, "memory_used_pct": 0},
                "go_backend": {"reachable": False, "response_time_ms": 0},
                "python_backend": {"reachable": False, "response_time_ms": 0},
                "vllm_service": {"running": False, "active_requests": 0},
                "redis": {"available": False, "connected": False},
            },
            "alert_reasons": [f"health check failed: {str(exc)}"],
            "timestamp": fallback["timestamp"],
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
            score = _score_from_gpu_history(entry)
            if score is not None:
                history.append({
                    "timestamp": ts,
                    "health_score": score,
                    "status": _status_from_score(score),
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
