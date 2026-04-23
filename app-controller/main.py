from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
from datetime import datetime
import asyncio
import httpx
import uuid

from routes.v1 import v1_router
from routes.manage import manage_router, integration_router
from routes.health import health_router
from routes.websocket import websocket_router
from core.deps import (
    scheduler, gpu_monitor, ws_manager, metrics, prometheus,
    cache_service, cache_updater, redis_client,
    structured_logger, config_watcher, logger, model_tester, sys_controller,
    VLLM_REQUEST_TIMEOUT, VLLM_STREAM_TIMEOUT, VLLM_CLIENT_LIMITS,
    _background_tasks, _on_config_changed
)
from core.vllm_manager import switch_vllm_model_with_test
from core.llama_cpp_manager import llama_cpp_manager
from middleware.error_handler import (
    http_exception_handler,
    generic_exception_handler,
    controller_exception_handler,
    ControllerException
)
from middleware.rate_limit import RateLimitMiddleware
from middleware.timeout_handler import TimeoutHandlerMiddleware

app = FastAPI(title="AI Controller API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(RateLimitMiddleware(max_requests=100, window_seconds=60))
app.middleware("http")(TimeoutHandlerMiddleware(timeout_seconds=60))

app.include_router(v1_router)
app.include_router(manage_router)
app.include_router(integration_router)
app.include_router(health_router)
app.include_router(websocket_router)


@app.middleware("http")
async def request_tracking_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = datetime.now()

    response = await call_next(request)

    duration = (datetime.now() - start_time).total_seconds()

    structured_logger.log_request(
        endpoint=str(request.url.path),
        method=request.method,
        status_code=response.status_code,
        duration=duration,
        request_id=request_id
    )

    prometheus.record_request(
        endpoint=str(request.url.path),
        method=request.method,
        status_code=response.status_code,
        duration=duration
    )

    metrics.record_request(
        endpoint=str(request.url.path),
        status_code=response.status_code,
        response_time=duration
    )

    return response

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
app.add_exception_handler(ControllerException, controller_exception_handler)

config_watcher.register_callback(_on_config_changed)

model_tester = model_tester
switch_vllm_model_with_test = switch_vllm_model_with_test
gpu_monitor = gpu_monitor
scheduler = scheduler
sys_controller = sys_controller
ws_manager = ws_manager
metrics = metrics
prometheus = prometheus
cache_service = cache_service
cache_updater = cache_updater
redis_client = redis_client
structured_logger = structured_logger


async def broadcast_status_loop():
    while True:
        try:
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
                    "last_used": scheduler.get_model_last_used(model).isoformat() if scheduler.get_model_last_used(model) else None
                }
            await ws_manager.broadcast_status(gpu_summary, model_status)
        except Exception as e:
            logger.error(f"Error broadcasting status: {str(e)}")
        await asyncio.sleep(2)


async def save_history_loop():
    while True:
        try:
            gpu_monitor.save_gpu_history()
        except Exception as e:
            logger.error(f"Error saving GPU history: {str(e)}")
        await asyncio.sleep(2)


@app.on_event("startup")
async def startup_event():
    app.state.vllm_request_client = httpx.AsyncClient(
        timeout=VLLM_REQUEST_TIMEOUT,
        limits=VLLM_CLIENT_LIMITS,
        http2=False
    )
    app.state.vllm_stream_client = httpx.AsyncClient(
        timeout=VLLM_STREAM_TIMEOUT,
        limits=VLLM_CLIENT_LIMITS,
        http2=False
    )

    redis_client.connect()
    if redis_client.is_connected():
        logger.info("Redis connection established successfully")
        gpu_monitor.set_redis_client(redis_client)
        await cache_updater.start(metrics)
        logger.info("Cache updater service started")
    else:
        logger.warning("Failed to connect to Redis, cache updater will not start")

    config_watcher.start_watching()

    await scheduler.preload_models()

    _background_tasks.clear()
    _background_tasks.append(asyncio.create_task(gpu_monitor._update_cache_loop()))
    _background_tasks.append(asyncio.create_task(broadcast_status_loop()))
    _background_tasks.append(asyncio.create_task(save_history_loop()))
    _background_tasks.append(asyncio.create_task(scheduler._preload_watcher_loop()))
    structured_logger.info("AI Controller service started", action="startup")


@app.on_event("shutdown")
async def shutdown_event():
    config_watcher.stop_watching()
    await cache_updater.stop()
    for task in _background_tasks:
        task.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)
    _background_tasks.clear()

    request_client = getattr(app.state, "vllm_request_client", None)
    if request_client is not None:
        await request_client.aclose()
        app.state.vllm_request_client = None

    stream_client = getattr(app.state, "vllm_stream_client", None)
    if stream_client is not None:
        await stream_client.aclose()
        app.state.vllm_stream_client = None

    llama_cpp_manager.cleanup_all()
    sys_controller.cleanup_all_managed_processes()

    structured_logger.info("AI Controller service stopped", action="shutdown")


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="AI Controller Service")
    parser.add_argument("--log-dir", type=str, default=None, help="Custom log directory path")
    parser.add_argument("--port", type=int, default=35000, help="Server port")

    args = parser.parse_args()

    if args.log_dir:
        from core.logger import setup_logger
        logger = setup_logger(log_dir=args.log_dir)

    logger.info(f"Starting AI Controller service on port {args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
