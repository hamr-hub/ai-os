from fastapi import APIRouter, HTTPException, Request
from starlette.responses import StreamingResponse
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from functools import lru_cache
import asyncio
import httpx
import json
import logging
import os

from schemas.chat import (
    ChatCompletionRequest,
    count_image_content, is_multimodal_model, decode_base64_image,
    validate_image_data
)
from schemas.image import (
    ImageGenerationRequest,
    MAX_IMAGE_SIZE_MB, MAX_WIDTH, MAX_HEIGHT, SUPPORTED_FORMATS,
)
from schemas.embedding import EmbeddingRequest
from schemas.test import TestResponse, ComparativeAnalysisRequest
from middleware.error_handler import (
    ModelNotFoundException,
    InsufficientMemoryException,
    TooManyRequestsException,
    ModelServiceUnavailableException
)

v1_router = APIRouter(prefix="/v1")
logger = logging.getLogger("ai_controller.routes.v1")


def _scheduler():
    import main as m
    return m.scheduler


def _gpu_monitor():
    import main as m
    return m.gpu_monitor


def _metrics():
    import main as m
    return m.metrics


def _model_tester():
    import main as m
    return m.model_tester


def _cache_service():
    import main as m
    return m.cache_service


def _prometheus():
    import main as m
    return m.prometheus


def _ws_manager():
    import main as m
    return m.ws_manager


def get_backend_url(model_name: str, scheduler) -> str:
    port = scheduler.get_model_port(model_name)
    return f"http://localhost:{port}"

def get_backend_model_name(model_name: str, scheduler) -> str:
    backend_type = scheduler.get_model_backend_type(model_name)
    model_config = scheduler.get_model_config(model_name)
    if backend_type == 'llama_cpp':
        return model_config.get('model_path', model_name) if model_config else model_name
    return model_config.get('model_path', model_name) if model_config else model_name


def get_vllm_request_client(request: Request) -> httpx.AsyncClient:
    client = getattr(request.app.state, "vllm_request_client", None)
    if client is None:
        raise RuntimeError("vLLM request client not initialized")
    return client


def get_vllm_stream_client(request: Request) -> httpx.AsyncClient:
    client = getattr(request.app.state, "vllm_stream_client", None)
    if client is None:
        raise RuntimeError("vLLM stream client not initialized")
    return client


async def ensure_model_ready(scheduler, model_name: str) -> None:
    if scheduler.is_model_running(model_name):
        return

    success = await scheduler.start_model(model_name)
    if not success:
        raise ModelServiceUnavailableException(model_name, "Failed to start service")


@v1_router.get("/models")
async def list_models(refresh: Optional[bool] = False):
    scheduler = _scheduler()
    cache = _cache_service()
    cache_key = "api:v1:models"

    if not refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    models = scheduler.get_available_models()
    model_list = []
    for model_name in models:
        config = scheduler.get_model_config(model_name)
        model_info = {
            "id": model_name,
            "object": "model",
            "created": 0,
            "owned_by": "local",
            "running": scheduler.is_model_running(model_name),
            "supports_images": scheduler.get_model_supports_images(model_name),
            "description": config.get("description", "") if config else "",
            "service": config.get("service", "") if config else "",
            "backend_type": scheduler.get_model_backend_type(model_name),
            "port": config.get("port", 8000) if config else 8000
        }
        model_list.append(model_info)

    result = {"object": "list", "data": model_list}
    cache.set(cache_key, result, ttl_seconds=300)
    return result


@v1_router.get("/models/{model_name}")
async def get_model_info(model_name: str):
    scheduler = _scheduler()
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    config = scheduler.get_model_config(model_name)
    return {
        "id": model_name,
        "object": "model",
        "created": 0,
        "owned_by": "local",
        "running": scheduler.is_model_running(model_name),
        "active_requests": scheduler.get_active_requests(model_name),
        "supports_images": scheduler.get_model_supports_images(model_name),
        "description": config.get("description", "") if config else " ",
        "service": config.get("service", "") if config else "",
        "port": config.get("port", 8000) if config else 8000,
        "required_memory": config.get("required_memory", "") if config else "",
        "preload": config.get("preload", False) if config else False,
        "keep_alive": config.get("keep_alive", False) if config else False
    }


@lru_cache(maxsize=128)
def get_model_capabilities(model_name: str) -> Dict[str, bool]:
    return {
        'multimodal': is_multimodal_model(model_name),
        'tool_calling': True,
        'streaming': True
    }


@v1_router.post("/chat/completions")
async def chat_completions(request: Request, body: ChatCompletionRequest):
    scheduler = _scheduler()
    gpu_monitor = _gpu_monitor()
    metrics = _metrics()
    cache = _cache_service()

    start_time = datetime.now()
    model_name = body.model
    stream = body.stream or False
    status_code = 200
    slot_acquired = False

    request_data = body.model_dump(exclude_unset=True)
    has_image, total_image_size = count_image_content(request_data)

    if not model_name or model_name.lower() == "default":
        model_name = scheduler.get_default_model() or scheduler.get_current_model_name()
        if not model_name:
            raise HTTPException(status_code=400, detail="No default model set and no model specified")

    try:
        if not scheduler.is_model_available(model_name):
            raise ModelNotFoundException(model_name)

        if has_image and not is_multimodal_model(model_name):
            raise HTTPException(
                status_code=400,
                detail=f"Model {model_name} does not support image inputs. Please use a multimodal model."
            )

        if not scheduler.acquire_request(model_name):
            active = scheduler.get_active_requests(model_name)
            limit = scheduler.get_concurrency_limit()
            queue_length = scheduler.get_queue_length(model_name)

            if scheduler.is_queue_available(model_name):
                success = await scheduler.wait_for_slot(model_name, timeout=30)
                if not success:
                    raise TooManyRequestsException(active, limit, queue_length)
                slot_acquired = True
            else:
                raise TooManyRequestsException(active, limit, queue_length)
        else:
            slot_acquired = True

        gpu_status = gpu_monitor.get_gpu_status()
        min_memory = scheduler.get_min_available_memory()
        available_mb = gpu_status.get('available_memory', 0) if gpu_status else 0
        min_memory_mb = min_memory // (1024 ** 2)
        if gpu_status and available_mb < min_memory_mb:
            raise InsufficientMemoryException(available_mb, min_memory_mb)

        await ensure_model_ready(scheduler, model_name)

        backend_url = get_backend_url(model_name, scheduler)
        vllm_url = f"{backend_url}/v1/chat/completions"

        model_config = scheduler.get_model_config(model_name)
        backend_type = scheduler.get_model_backend_type(model_name)
        vllm_model_name = get_backend_model_name(model_name, scheduler)

        request_data = body.model_dump(exclude_unset=True)
        request_data['model'] = vllm_model_name

        if stream:
            if 'stream_options' not in request_data:
                request_data['stream_options'] = {"include_usage": True}
            
            stream_client = get_vllm_stream_client(request)
            stream_request = stream_client.build_request('POST', vllm_url, json=request_data)

            try:
                response = await stream_client.send(stream_request, stream=True)
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise ModelServiceUnavailableException(model_name, str(e))

            chat_completion_id = f"chatcmpl-{os.urandom(12).hex()}"

            async def generate():
                last_activity = datetime.now()
                heartbeat_interval = 10
                sent_heartbeat = False

                try:
                    async for chunk in response.aiter_lines():
                        current_time = datetime.now()

                        if (current_time - last_activity).total_seconds() > heartbeat_interval:
                            if not sent_heartbeat:
                                yield ": heartbeat\n\n"
                                sent_heartbeat = True
                        else:
                            sent_heartbeat = False

                        if chunk.startswith("data: "):
                            chunk_data = chunk[6:]
                            last_activity = datetime.now()

                            if chunk_data == "[DONE]":
                                yield f"data: {json.dumps({
                                    'id': chat_completion_id,
                                    'object': 'chat.completion.chunk',
                                    'created': int(current_time.timestamp()),
                                    'model': model_name,
                                    'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]
                                })}\n\n"
                                yield "data: [DONE]\n\n"
                                break

                            try:
                                json_chunk = json.loads(chunk_data)
                                json_chunk['id'] = chat_completion_id
                                json_chunk['model'] = model_name
                                
                                # Record usage if present in chunk (OpenAI compatible stream usage)
                                usage = json_chunk.get('usage')
                                if usage:
                                    metrics.record_token_usage(
                                        model_name,
                                        prompt_tokens=usage.get('prompt_tokens', 0),
                                        completion_tokens=usage.get('completion_tokens', 0)
                                    )
                                
                                yield f"data: {json.dumps(json_chunk)}\n\n"
                            except json.JSONDecodeError:
                                yield f"data: {chunk_data}\n\n"
                        elif chunk.strip():
                            pass

                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({
                        'id': chat_completion_id,
                        'object': 'chat.completion.chunk',
                        'created': int(datetime.now().timestamp()),
                        'model': model_name,
                        'choices': [{'index': 0, 'delta': {'content': '[Stream timeout]'}, 'finish_reason': 'error'}]
                    })}\n\n"
                    yield "data: [DONE]\n\n"
                except httpx.HTTPError as exc:
                    logger.warning("Streaming proxy error for model %s: %s", model_name, exc)
                    yield f"data: {json.dumps({
                        'id': chat_completion_id,
                        'object': 'chat.completion.chunk',
                        'created': int(datetime.now().timestamp()),
                        'model': model_name,
                        'choices': [{'index': 0, 'delta': {'content': '[Stream error]'}, 'finish_reason': 'error'}]
                    })}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception:
                    logger.exception("Unexpected streaming error for model %s", model_name)
                    yield f"data: {json.dumps({
                        'id': chat_completion_id,
                        'object': 'chat.completion.chunk',
                        'created': int(datetime.now().timestamp()),
                        'model': model_name,
                        'choices': [{'index': 0, 'delta': {'content': '[Internal stream error]'}, 'finish_reason': 'error'}]
                    })}\n\n"
                    yield "data: [DONE]\n\n"
                finally:
                    try:
                        await response.aclose()
                    except Exception as exc:
                        logger.debug("Failed to close streaming response for model %s: %s", model_name, exc)

            return StreamingResponse(generate(), media_type="text/event-stream", headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Transfer-Encoding": "chunked"
            })

        request_client = get_vllm_request_client(request)
        response = await request_client.post(vllm_url, json=request_data)
        response.raise_for_status()

        result = response.json()
        result['id'] = f"chatcmpl-{os.urandom(12).hex()}"
        result['model'] = model_name

        # Record token usage
        usage = result.get('usage')
        if usage:
            metrics.record_token_usage(
                model_name,
                prompt_tokens=usage.get('prompt_tokens', 0),
                completion_tokens=usage.get('completion_tokens', 0)
            )

        return result
    except httpx.HTTPError as e:
        status_code = 503
        logger.warning("Chat completion proxy error for model %s: %s", model_name, e)
        raise ModelServiceUnavailableException(model_name, str(e))
    except HTTPException as e:
        status_code = e.status_code
        raise
    except Exception as e:
        status_code = 500
        logger.exception("Chat completion failed for model %s", model_name)
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {str(e)}")
    finally:
        if slot_acquired:
            scheduler.release_request(model_name)
        metrics.record_request(
            endpoint="/v1/chat/completions",
            status_code=status_code,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name=model_name,
            is_image_request=has_image,
            image_size_bytes=total_image_size
        )


@v1_router.post("/images/validate")
async def validate_image(request: Request):
    from schemas.image import ImageValidationRequest
    body = await request.json()
    image_data = body.get("image_data", "")
    metrics = _metrics()
    start_time = datetime.now()

    try:
        decoded = decode_base64_image(image_data)
        if decoded is None:
            return {"success": False, "message": "Failed to decode base64 image data"}

        validation = validate_image_data(decoded)
        if validation['valid']:
            metrics.record_request(
                endpoint="/v1/images/validate", status_code=200,
                response_time=(datetime.now() - start_time).total_seconds(),
                model_name="image-validation"
            )
            return {"success": True, "message": "Image validation successful", "image_info": validation}
        else:
            metrics.record_request(
                endpoint="/v1/images/validate", status_code=400,
                response_time=(datetime.now() - start_time).total_seconds(),
                model_name="image-validation"
            )
            return {"success": False, "message": validation['error'], "image_info": validation}
    except Exception as e:
        metrics.record_request(
            endpoint="/v1/images/validate", status_code=500,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name="image-validation"
        )
        raise HTTPException(status_code=500, detail=f"Image validation failed: {str(e)}")


@v1_router.post("/images/upload")
async def upload_image(request: Request):
    from schemas.chat import MAX_IMAGE_SIZE_BYTES
    metrics = _metrics()
    start_time = datetime.now()

    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    filename = getattr(file, 'filename', 'unknown')
    content_type = getattr(file, 'content_type', 'application/octet-stream')
    contents = await file.read()

    if len(contents) > MAX_IMAGE_SIZE_BYTES:
        metrics.record_request(
            endpoint="/v1/images/upload", status_code=413,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name="image-upload"
        )
        return {"success": False, "message": f"Image size exceeds maximum allowed size of {MAX_IMAGE_SIZE_MB}MB"}

    validation = validate_image_data(contents)
    if validation['valid']:
        metrics.record_request(
            endpoint="/v1/images/upload", status_code=200,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name="image-upload"
        )
        return {
            "success": True, "message": "Image uploaded successfully",
            "image_info": {**validation, "filename": filename, "content_type": content_type}
        }
    else:
        metrics.record_request(
            endpoint="/v1/images/upload", status_code=400,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name="image-upload"
        )
        return {"success": False, "message": validation['error'], "image_info": validation}


@v1_router.get("/images/info")
async def get_image_info():
    cache = _cache_service()
    cache_key = "api:v1:images:info"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = {
        "max_size_mb": MAX_IMAGE_SIZE_MB,
        "max_dimensions": f"{MAX_WIDTH}x{MAX_HEIGHT}",
        "supported_formats": list(SUPPORTED_FORMATS),
        "endpoints": {
            "validate": "POST /v1/images/validate - Validate base64 encoded image",
            "upload": "POST /v1/images/upload - Upload image file",
            "info": "GET /v1/images/info - Get image service information"
        }
    }

    cache.set(cache_key, result, ttl_seconds=3600)
    return result


@v1_router.post("/images/generations")
async def generate_image(request: Request, body: ImageGenerationRequest):
    scheduler = _scheduler()
    metrics = _metrics()
    start_time = datetime.now()

    if not scheduler.is_model_available(body.model):
        raise ModelNotFoundException(body.model)

    try:
        await ensure_model_ready(scheduler, body.model)

        backend_url = get_backend_url(body.model, scheduler)
        vllm_url = f"{backend_url}/v1/images/generations"

        req_data = {
            "prompt": body.prompt,
            "n": body.n,
            "size": body.size,
            "response_format": body.response_format
        }

        request_client = get_vllm_request_client(request)
        response = await request_client.post(vllm_url, json=req_data, timeout=120)
        response.raise_for_status()
        result = response.json()

        duration = (datetime.now() - start_time).total_seconds()
        metrics.record_request(
            endpoint="/v1/images/generations", status_code=200,
            response_time=duration, model_name=body.model
        )
        return result
    except httpx.HTTPError as e:
        logger.warning("Image generation proxy error for model %s: %s", body.model, e)
        metrics.record_request(
            endpoint="/v1/images/generations", status_code=503,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name=body.model
        )
        raise ModelServiceUnavailableException(body.model, str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Image generation failed for model %s", body.model)
        metrics.record_request(
            endpoint="/v1/images/generations", status_code=500,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name=body.model
        )
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")


@v1_router.post("/embeddings")
async def create_embeddings(request: Request, body: EmbeddingRequest):
    scheduler = _scheduler()
    metrics = _metrics()
    start_time = datetime.now()
    model_name = body.model

    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    await ensure_model_ready(scheduler, model_name)

    backend_url = get_backend_url(model_name, scheduler)
    vllm_url = f"{backend_url}/v1/embeddings"

    slot_acquired = False
    try:
        if not scheduler.acquire_request(model_name):
            raise TooManyRequestsException(
                scheduler.get_active_requests(model_name),
                scheduler.get_concurrency_limit(),
                scheduler.get_queue_length(model_name)
            )
        slot_acquired = True

        req_data = {
            "model": get_backend_model_name(model_name, scheduler),
            "input": body.input,
            "encoding_format": body.encoding_format
        }
        if body.dimensions:
            req_data["dimensions"] = body.dimensions

        request_client = get_vllm_request_client(request)
        response = await request_client.post(vllm_url, json=req_data)
        response.raise_for_status()
        result = response.json()

        duration = (datetime.now() - start_time).total_seconds()
        metrics.record_request(
            endpoint="/v1/embeddings", status_code=200,
            response_time=duration, model_name=model_name
        )
        return result
    except httpx.HTTPError as e:
        logger.warning("Embeddings proxy error for model %s: %s", model_name, e)
        metrics.record_request(
            endpoint="/v1/embeddings", status_code=503,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name=model_name
        )
        raise ModelServiceUnavailableException(model_name, str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Embeddings request failed for model %s", model_name)
        metrics.record_request(
            endpoint="/v1/embeddings", status_code=500,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name=model_name
        )
        raise HTTPException(status_code=500, detail=f"Embeddings request failed: {str(e)}")
    finally:
        if slot_acquired:
            scheduler.release_request(model_name)


@v1_router.get("/status")
async def get_api_status():
    scheduler = _scheduler()
    gpu_monitor = _gpu_monitor()
    gpu_status = gpu_monitor.get_gpu_status()
    models = scheduler.get_available_models()
    running_models = [m for m in models if scheduler.is_model_running(m)]

    return {
        "status": "healthy" if gpu_status else "degraded",
        "timestamp": datetime.now().isoformat(),
        "gpu_available": gpu_status is not None,
        "available_models": len(models),
        "running_models": len(running_models),
        "models": [{"name": m, "running": scheduler.is_model_running(m)} for m in models]
    }


def _serialize_report(report):
    return {
        "model_name": report.model_name,
        "test_timestamp": report.test_timestamp,
        "overall_status": report.overall_status,
        "runtime_status": report.runtime_status,
        "feature_support": report.feature_support,
        "performance_metrics": report.performance_metrics,
        "resource_utilization": report.resource_utilization,
        "test_results": [
            {
                "test_name": r.test_name,
                "feature_type": r.feature_type.value,
                "status": r.status.value,
                "duration": r.duration,
                "metrics": r.metrics,
                "error": r.error,
                "details": r.details
            } for r in report.test_results
        ],
        "errors": report.errors,
        "warnings": report.warnings
    }


@v1_router.post("/test/model/{model_name}")
async def test_model(model_name: str):
    scheduler = _scheduler()
    model_tester = _model_tester()
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    try:
        report = await model_tester.run_tests(model_name)
        return {
            "status": "completed",
            "message": f"Tests completed for {model_name}",
            "report": _serialize_report(report)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


@v1_router.get("/test/report/{model_name}")
async def get_model_test_report(model_name: str):
    model_tester = _model_tester()
    report = model_tester.get_previous_report(model_name)

    if not report:
        return {"status": "not_found", "message": f"No test report found for {model_name}"}

    return {"status": "found", "report": _serialize_report(report)}


@v1_router.get("/test/reports")
async def get_all_test_reports():
    model_tester = _model_tester()
    reports = model_tester.get_all_reports()

    if not reports:
        return {"status": "no_reports", "message": "No test reports available"}

    result = {}
    for model_name, report in reports.items():
        result[model_name] = _serialize_report(report)

    return {"status": "success", "reports": result}


@v1_router.post("/test/comparative")
async def run_comparative_analysis(request: ComparativeAnalysisRequest):
    model_tester = _model_tester()
    try:
        analysis = await model_tester.run_comparative_analysis(request.model_names)
        return {
            "status": "completed",
            "message": "Comparative analysis completed",
            "analysis": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparative analysis failed: {str(e)}")


@v1_router.delete("/test/reports")
async def clear_test_reports():
    model_tester = _model_tester()
    model_tester.clear_reports()
    return {"status": "success", "message": "All test reports cleared"}


@v1_router.get("/test/status")
async def get_test_status():
    model_tester = _model_tester()
    reports = model_tester.get_all_reports()
    return {
        "status": "ready",
        "models_tested_count": len(reports),
        "models_tested": list(reports.keys()),
        "timestamp": datetime.now().isoformat()
    }


@v1_router.post("/test/model/{model_name}/switch-and-test")
async def switch_and_test_model(model_name: str):
    scheduler = _scheduler()
    model_tester = _model_tester()
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    try:
        switch_result = await scheduler.switch_model(model_name)
        if not switch_result:
            return {
                "status": "failed",
                "message": f"Failed to switch to model {model_name}",
                "report": None
            }

        scheduler.mark_model_selected(model_name)
        report = await model_tester.run_tests(model_name)
        return {
            "status": "completed",
            "message": f"Successfully switched to {model_name} and completed tests",
            "report": _serialize_report(report)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Switch and test failed: {str(e)}")
