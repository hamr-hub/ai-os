from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Union, Tuple
from functools import lru_cache
import asyncio
import httpx
import json
import os
from datetime import datetime
import uuid
import base64
import io
from PIL import Image
import re

from core.scheduler import Scheduler
from core.monitor import GPUMonitor
from core.sys_ctl import SystemController
from core.logger import setup_logger
from core.websocket_manager import WebSocketManager
from core.config_watcher import ConfigWatcher
from core.metrics import MetricsCollector
from core.prometheus_exporter import PrometheusExporter
from core.structured_logger import StructuredLogger, RequestContext
from core.redis_client import redis_client
from core.cache_service import cache_service
from core.cache_updater import CacheUpdater
from core.model_testing import ModelTestingFramework
from core.vllm_manager import (
    get_available_models,
    get_current_model_info,
    start_vllm_service,
    stop_vllm_service,
    restart_vllm_service,
    get_vllm_service_status,
    switch_vllm_model,
    switch_vllm_model_with_test,
    MODEL_BASE_PATH,
    VLLM_SERVICE_NAME,
    VLLM_DEFAULT_PORT
)
from middleware.error_handler import (
    http_exception_handler,
    generic_exception_handler,
    controller_exception_handler,
    ControllerException,
    ModelNotFoundException,
    InsufficientMemoryException,
    TooManyRequestsException,
    ModelServiceUnavailableException
)
from middleware.rate_limit import RateLimitMiddleware
from middleware.timeout_handler import TimeoutHandlerMiddleware

# 先创建配置监控器以读取配置
config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
config_watcher = ConfigWatcher(config_path)

# 加载配置以获取日志路径
config = config_watcher.load_config() or {}
log_dir = config.get('settings', {}).get('logging', {}).get('log_dir', None)

# 初始化日志器
logger = setup_logger(log_dir=log_dir)
structured_logger = StructuredLogger("ai_controller")

# --- Image Validation Constants ---
MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
MAX_WIDTH = 8192
MAX_HEIGHT = 8192
SUPPORTED_FORMATS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}

def validate_image_data(image_data: bytes) -> Dict[str, Any]:
    try:
        image = Image.open(io.BytesIO(image_data))
        width, height = image.size
        format = image.format.lower() if image.format else 'unknown'
        
        if format not in SUPPORTED_FORMATS:
            return {
                'valid': False,
                'error': f"Unsupported image format: {format}. Supported formats: {', '.join(SUPPORTED_FORMATS)}"
            }
        
        if width > MAX_WIDTH or height > MAX_HEIGHT:
            return {
                'valid': False,
                'error': f"Image dimensions exceed maximum allowed size. Max: {MAX_WIDTH}x{MAX_HEIGHT}, Got: {width}x{height}"
            }
        
        return {
            'valid': True,
            'width': width,
            'height': height,
            'format': format,
            'size_bytes': len(image_data)
        }
    except Exception as e:
        return {
            'valid': False,
            'error': f"Invalid image data: {str(e)}"
        }

def decode_base64_image(base64_string: str) -> Optional[bytes]:
    try:
        match = re.match(r'^data:image/([\w-]+);base64,(.+)$', base64_string)
        if match:
            base64_data = match.group(2)
        else:
            base64_data = base64_string
        
        decoded = base64.b64decode(base64_data)
        
        if len(decoded) > MAX_IMAGE_SIZE_BYTES:
            return None
        
        return decoded
    except Exception:
        return None

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

gpu_monitor = GPUMonitor()
sys_controller = SystemController()
scheduler = Scheduler(gpu_monitor, sys_controller)
ws_manager = WebSocketManager()
metrics = MetricsCollector()
prometheus = PrometheusExporter()
model_tester = ModelTestingFramework(scheduler, gpu_monitor)
cache_updater = CacheUpdater(gpu_monitor, scheduler)

VLLM_REQUEST_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
VLLM_STREAM_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=60.0, pool=60.0)
VLLM_CLIENT_LIMITS = httpx.Limits(max_connections=200, max_keepalive_connections=50)


def get_vllm_request_client() -> httpx.AsyncClient:
    client = getattr(app.state, "vllm_request_client", None)
    if client is None:
        raise RuntimeError("vLLM request client not initialized")
    return client


def get_vllm_stream_client() -> httpx.AsyncClient:
    client = getattr(app.state, "vllm_stream_client", None)
    if client is None:
        raise RuntimeError("vLLM stream client not initialized")
    return client

def on_config_changed(new_config: Dict):
    structured_logger.info("Configuration updated", action="config_reload")
    scheduler.config = new_config

config_watcher.register_callback(on_config_changed)
_background_tasks: List[asyncio.Task] = []

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

async def broadcast_status_loop():
    while True:
        try:
            gpu_summary = gpu_monitor.get_gpu_summary()
            model_status = await get_model_status()
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
    _background_tasks.clear()
    _background_tasks.append(asyncio.create_task(gpu_monitor._update_cache_loop()))
    _background_tasks.append(asyncio.create_task(broadcast_status_loop()))
    _background_tasks.append(asyncio.create_task(save_history_loop()))
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

    structured_logger.info("AI Controller service stopped", action="shutdown")

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, Any]]
    stream: Optional[bool] = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    stop: Optional[List[str]] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0

    @field_validator('messages')
    def validate_messages_with_images(cls, v):
        for message in v:
            if 'content' in message:
                content = message['content']
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and 'image_url' in part:
                            image_url = part['image_url']
                            if isinstance(image_url, dict) and 'url' in image_url:
                                url = image_url['url']
                                if url.startswith('data:image/'):
                                    decoded = decode_base64_image(url)
                                    if decoded is None:
                                        raise ValueError("Invalid or oversized base64 image data")
                                    validation = validate_image_data(decoded)
                                    if not validation['valid']:
                                        raise ValueError(validation['error'])
        return v

class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: Dict[str, str]
    finish_reason: Optional[str] = "stop"

class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{os.urandom(12).hex()}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(asyncio.get_event_loop().time()))
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: Optional[Dict[str, int]] = None

class ChatCompletionChunk(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{os.urandom(12).hex()}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(asyncio.get_event_loop().time()))
    model: str
    choices: List[Dict[str, Any]]

class ImageGenerationRequest(BaseModel):
    model: str = Field(default="dall-e-3")
    prompt: str = Field(min_length=1, max_length=4000)
    n: Optional[int] = Field(default=1, ge=1, le=10)
    size: Optional[str] = Field(default="1024x1024", pattern=r'^\d+x\d+$')
    quality: Optional[str] = Field(default="standard", pattern=r'^(standard|hd)$')
    style: Optional[str] = Field(default="vivid", pattern=r'^(vivid|natural)$')
    response_format: Optional[str] = Field(default="url", pattern=r'^(url|b64_json)$')

class ImageData(BaseModel):
    b64_json: Optional[str] = None
    url: Optional[str] = None
    revised_prompt: Optional[str] = None

class ImageGenerationResponse(BaseModel):
    created: int
    data: List[ImageData]

class EmbeddingRequest(BaseModel):
    model: str
    input: Union[str, List[str]]
    encoding_format: Optional[str] = "float"
    dimensions: Optional[int] = None

@app.get("/v1/models")
async def list_models(refresh: Optional[bool] = False):
    cache_key = "api:v1:models"
    
    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached
    
    logger.info("Listing available models")
    models = scheduler.get_available_models()
    result = {"object": "list", "data": [{"id": m, "object": "model", "created": 0, "owned_by": "local"} for m in models]}
    
    cache_service.set(cache_key, result, ttl_seconds=300)
    return result

def count_image_content(request_data: Dict) -> Tuple[bool, int]:
    has_image = False
    total_size = 0
    
    if request_data.get('messages'):
        for message in request_data['messages']:
            content = message.get('content')
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get('image_url'):
                        has_image = True
                        image_url = part['image_url']
                        if isinstance(image_url, dict):
                            url = image_url.get('url', '')
                        else:
                            url = str(image_url)
                        if url.startswith('data:image/'):
                            comma_pos = url.find(',')
                            if comma_pos > 0:
                                base64_data = url[comma_pos+1:]
                                total_size += int((len(base64_data) * 3) / 4)
    return has_image, total_size

def is_multimodal_model(model_name: str) -> bool:
    return scheduler.get_model_supports_images(model_name)

@lru_cache(maxsize=128)
def get_model_capabilities(model_name: str) -> Dict[str, bool]:
    return {
        'multimodal': is_multimodal_model(model_name),
        'tool_calling': True,
        'streaming': True
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    start_time = datetime.now()
    model_name = request.model
    stream = request.stream or False
    status_code = 200
    slot_acquired = False
    
    request_data = request.model_dump(exclude_unset=True)
    has_image, total_image_size = count_image_content(request_data)
    
    if has_image:
        logger.info(f"Received chat completion request with image content for model: {model_name}, stream: {stream}, image_size: {total_image_size} bytes")
    else:
        logger.info(f"Received chat completion request for model: {model_name}, stream: {stream}")
    
    try:
        if not scheduler.is_model_available(model_name):
            logger.warning(f"Model {model_name} not found")
            raise ModelNotFoundException(model_name)
        
        if has_image and not is_multimodal_model(model_name):
            logger.warning(f"Model {model_name} does not support image inputs")
            raise HTTPException(
                status_code=400,
                detail=f"Model {model_name} does not support image inputs. Please use a multimodal model like gemma-2-vision."
            )
        
        if not scheduler.acquire_request(model_name):
            active = scheduler.get_active_requests(model_name)
            limit = scheduler.get_concurrency_limit()
            queue_length = scheduler.get_queue_length(model_name)
            
            if scheduler.is_queue_available(model_name):
                wait_time = scheduler.get_wait_time_estimate(model_name)
                logger.info(f"Request queued for {model_name}, position: {queue_length + 1}, estimated wait: {wait_time:.1f}s")
                
                success = await scheduler.wait_for_slot(model_name, timeout=30)
                if not success:
                    logger.warning(f"Queue timeout for {model_name}")
                    raise TooManyRequestsException(active, limit, queue_length)
                
                slot_acquired = True
            else:
                logger.warning(f"Queue full for {model_name}: {active}/{limit}, queue: {queue_length}")
                raise TooManyRequestsException(active, limit, queue_length)
        else:
            slot_acquired = True
        
        gpu_status = gpu_monitor.get_gpu_status()
        min_memory = scheduler.get_min_available_memory()
        available_mb = gpu_status.get('available_memory', 0) if gpu_status else 0
        min_memory_mb = min_memory // (1024 ** 2)
        if gpu_status and available_mb < min_memory_mb:
            logger.warning(f"Insufficient GPU memory for {model_name}")
            raise InsufficientMemoryException(available_mb, min_memory_mb)
        
        if not scheduler.is_model_running(model_name):
            logger.info(f"Model {model_name} not running, starting...")
            success = await scheduler.start_model(model_name)
            if not success:
                logger.error(f"Failed to start model {model_name}")
                raise ModelServiceUnavailableException(model_name, "Failed to start service")
            await asyncio.sleep(5)
        
        vllm_port = scheduler.get_model_port(model_name)
        vllm_url = f"http://localhost:{vllm_port}/v1/chat/completions"

        model_config = scheduler.get_model_config(model_name)
        vllm_model_name = model_config.get('model_path', model_name) if model_config else model_name

        logger.info(f"Forwarding request to vLLM at {vllm_url} with model: {vllm_model_name}")

        request_data = request.model_dump(exclude_unset=True)
        request_data['model'] = vllm_model_name

        if stream:
            stream_client = get_vllm_stream_client()
            stream_request = stream_client.build_request('POST', vllm_url, json=request_data)
            response = await stream_client.send(stream_request, stream=True)
            response.raise_for_status()

            async def generate():
                try:
                    async for chunk in response.aiter_lines():
                        if chunk.startswith("data: "):
                            chunk_data = chunk[6:]
                            if chunk_data == "[DONE]":
                                yield "data: [DONE]\n\n"
                                break
                            try:
                                json_chunk = json.loads(chunk_data)
                                json_chunk['id'] = f"chatcmpl-{os.urandom(12).hex()}"
                                json_chunk['model'] = model_name
                                yield f"data: {json.dumps(json_chunk)}\n\n"
                            except:
                                yield f"data: {chunk_data}\n\n"
                finally:
                    await response.aclose()

            return StreamingResponse(generate(), media_type="text/event-stream")

        request_client = get_vllm_request_client()
        response = await request_client.post(vllm_url, json=request_data)
        response.raise_for_status()

        result = response.json()
        result['id'] = f"chatcmpl-{os.urandom(12).hex()}"
        result['model'] = model_name
        logger.info(f"Request completed successfully for {model_name}")
        return result
    except (HTTPException, ControllerException) as e:
        status_code = getattr(e, 'status_code', getattr(e, 'code', 500))
        raise
    except httpx.HTTPError as e:
        status_code = 503
        logger.error(f"vLLM service error for {model_name}: {str(e)}")
        raise ModelServiceUnavailableException(model_name, str(e))
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

class ImageUploadResponse(BaseModel):
    success: bool
    message: str
    image_info: Optional[Dict[str, Any]] = None

class ImageValidationRequest(BaseModel):
    image_data: str

@app.post("/v1/images/validate", response_model=ImageUploadResponse)
async def validate_image(request: ImageValidationRequest):
    start_time = datetime.now()
    logger.info("Received image validation request")
    
    try:
        decoded = decode_base64_image(request.image_data)
        if decoded is None:
            return {
                "success": False,
                "message": "Failed to decode base64 image data"
            }
        
        validation = validate_image_data(decoded)
        if validation['valid']:
            metrics.record_request(
                endpoint="/v1/images/validate",
                status_code=200,
                response_time=(datetime.now() - start_time).total_seconds(),
                model_name="image-validation"
            )
            return {
                "success": True,
                "message": "Image validation successful",
                "image_info": validation
            }
        else:
            metrics.record_request(
                endpoint="/v1/images/validate",
                status_code=400,
                response_time=(datetime.now() - start_time).total_seconds(),
                model_name="image-validation"
            )
            return {
                "success": False,
                "message": validation['error'],
                "image_info": validation
            }
    except Exception as e:
        logger.error(f"Image validation error: {str(e)}")
        metrics.record_request(
            endpoint="/v1/images/validate",
            status_code=500,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name="image-validation"
        )
        raise HTTPException(status_code=500, detail=f"Image validation failed: {str(e)}")

@app.post("/v1/images/upload", response_model=ImageUploadResponse)
async def upload_image(file: UploadFile = File(...)):
    start_time = datetime.now()
    logger.info(f"Received image upload request: {file.filename}")
    
    try:
        contents = await file.read()
        
        if len(contents) > MAX_IMAGE_SIZE_BYTES:
            metrics.record_request(
                endpoint="/v1/images/upload",
                status_code=413,
                response_time=(datetime.now() - start_time).total_seconds(),
                model_name="image-upload"
            )
            return {
                "success": False,
                "message": f"Image size exceeds maximum allowed size of {MAX_IMAGE_SIZE_MB}MB"
            }
        
        validation = validate_image_data(contents)
        if validation['valid']:
            metrics.record_request(
                endpoint="/v1/images/upload",
                status_code=200,
                response_time=(datetime.now() - start_time).total_seconds(),
                model_name="image-upload"
            )
            return {
                "success": True,
                "message": "Image uploaded successfully",
                "image_info": {
                    **validation,
                    "filename": file.filename,
                    "content_type": file.content_type
                }
            }
        else:
            metrics.record_request(
                endpoint="/v1/images/upload",
                status_code=400,
                response_time=(datetime.now() - start_time).total_seconds(),
                model_name="image-upload"
            )
            return {
                "success": False,
                "message": validation['error'],
                "image_info": validation
            }
    except Exception as e:
        logger.error(f"Image upload error: {str(e)}")
        metrics.record_request(
            endpoint="/v1/images/upload",
            status_code=500,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name="image-upload"
        )
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")

@app.get("/v1/images/info")
async def get_image_info():
    cache_key = "api:v1:images:info"
    cached = cache_service.get(cache_key)
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
    
    cache_service.set(cache_key, result, ttl_seconds=3600)
    return result

@app.post("/v1/images/generations", response_model=ImageGenerationResponse)
async def generate_image(request: ImageGenerationRequest):
    """OpenAI 兼容的图像生成接口"""
    start_time = datetime.now()
    logger.info(f"Received image generation request: model={request.model}, prompt={request.prompt[:50]}...")
    
    if not scheduler.is_model_available(request.model):
        raise ModelNotFoundException(request.model)
    
    if not scheduler.is_model_running(request.model):
        success = await scheduler.start_model(request.model)
        if not success:
            raise ModelServiceUnavailableException(request.model, "Failed to start model")
        await asyncio.sleep(5)
    
    vllm_port = scheduler.get_model_port(request.model)
    vllm_url = f"http://localhost:{vllm_port}/v1/images/generations"
    
    try:
        request_data = {
            "prompt": request.prompt,
            "n": request.n,
            "size": request.size,
            "response_format": request.response_format
        }
        
        request_client = get_vllm_request_client()
        response = await request_client.post(vllm_url, json=request_data, timeout=120)
        response.raise_for_status()
        result = response.json()
        
        duration = (datetime.now() - start_time).total_seconds()
        metrics.record_request(
            endpoint="/v1/images/generations",
            status_code=200,
            response_time=duration,
            model_name=request.model
        )
        
        return result
    except httpx.HTTPError as e:
        logger.error(f"Image generation failed for {request.model}: {str(e)}")
        metrics.record_request(
            endpoint="/v1/images/generations",
            status_code=503,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name=request.model
        )
        raise ModelServiceUnavailableException(request.model, str(e))

@app.post("/v1/embeddings")
async def create_embeddings(request: EmbeddingRequest):
    """OpenAI 兼容的 Embedding 接口"""
    start_time = datetime.now()
    model_name = request.model
    logger.info(f"Received embedding request for model: {model_name}")
    
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)
    
    if not scheduler.is_model_running(model_name):
        success = await scheduler.start_model(model_name)
        if not success:
            raise ModelServiceUnavailableException(model_name, "Failed to start model")
        await asyncio.sleep(5)
    
    vllm_port = scheduler.get_model_port(model_name)
    vllm_url = f"http://localhost:{vllm_port}/v1/embeddings"
    
    slot_acquired = False
    try:
        if not scheduler.acquire_request(model_name):
            raise TooManyRequestsException(
                scheduler.get_active_requests(model_name),
                scheduler.get_concurrency_limit(),
                scheduler.get_queue_length(model_name)
            )
        slot_acquired = True
        
        request_data = {
            "model": scheduler.get_model_path(model_name) or model_name,
            "input": request.input,
            "encoding_format": request.encoding_format
        }
        if request.dimensions:
            request_data["dimensions"] = request.dimensions
        
        request_client = get_vllm_request_client()
        response = await request_client.post(vllm_url, json=request_data)
        response.raise_for_status()
        result = response.json()
        
        duration = (datetime.now() - start_time).total_seconds()
        metrics.record_request(
            endpoint="/v1/embeddings",
            status_code=200,
            response_time=duration,
            model_name=model_name
        )
        
        return result
    except httpx.HTTPError as e:
        logger.error(f"Embedding failed for {model_name}: {str(e)}")
        metrics.record_request(
            endpoint="/v1/embeddings",
            status_code=503,
            response_time=(datetime.now() - start_time).total_seconds(),
            model_name=model_name
        )
        raise ModelServiceUnavailableException(model_name, str(e))
    finally:
        if slot_acquired:
            scheduler.release_request(model_name)

@app.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    await ws_manager.connect(websocket, channel="monitor")
    logger.info("WebSocket connection established for monitoring")
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, channel="monitor")
        logger.info("WebSocket connection closed")

@app.get("/manage/gpu")
async def get_gpu_status(refresh: Optional[bool] = False):
    cache_key = "api:manage:gpu:status"
    
    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached
    
    logger.info("Getting GPU status")
    status = gpu_monitor.get_gpu_status()
    if not status:
        result = {"status": "unavailable", "message": "No GPU detected", "serverTime": datetime.now().isoformat()}
    else:
        status["serverTime"] = datetime.now().isoformat()
        result = status
    
    cache_service.set(cache_key, result, ttl_seconds=10)
    return result

@app.get("/manage/gpu/summary")
async def get_gpu_summary():
    cache_key = "api:manage:gpu:summary"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached
    
    logger.info("Getting GPU summary")
    summary = gpu_monitor.get_gpu_summary()
    
    cache_service.set(cache_key, summary, ttl_seconds=30)
    return summary

@app.get("/manage/models")
async def get_model_status(refresh: Optional[bool] = False):
    cache_key = "api:manage:models:status"
    
    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached
    
    logger.info("Getting model statuses")
    models = scheduler.get_available_models()
    status = {}
    for model in models:
        status[model] = {
            "running": scheduler.is_model_running(model),
            "port": scheduler.get_model_port(model),
            "service": scheduler.get_model_service(model),
            "active_requests": scheduler.get_active_requests(model),
            "preloaded": scheduler.is_model_preloaded(model),
            "last_used": scheduler.get_model_last_used(model).isoformat() if scheduler.get_model_last_used(model) else None
        }
    
    cache_service.set(cache_key, status, ttl_seconds=5)
    return status

@app.get("/manage/queue")
async def get_queue_status():
    cache_key = "api:manage:queue:status"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached
    
    logger.info("Getting queue status")
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

@app.get("/manage/preload")
async def get_preload():
    cache_key = "api:manage:preload:status"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached
    
    logger.info("Getting preload status")
    result = {
        "preloaded_models": scheduler.get_preloaded_models(),
        "all_models": scheduler.get_available_models()
    }
    
    cache_service.set(cache_key, result, ttl_seconds=60)
    return result

@app.post("/manage/preload/{model_name}")
async def preload_model(model_name: str):
    logger.info(f"Preloading model {model_name}")
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    success = await scheduler.start_model(model_name)
    if success:
        # 清除相关缓存
        cache_service.delete("api:manage:models:status")
        cache_service.delete("api:manage:models:summary")
        cache_service.delete("api:manage:preload:status")
        cache_service.delete("api:manage:preload:detailed")
        cache_service.delete("api:v1:status")
        return {"status": "preloaded", "model": model_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to preload model {model_name}")

@app.post("/manage/models/{model_name}/start")
async def start_model(model_name: str):
    logger.info(f"Starting model {model_name}")
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    if scheduler.is_model_running(model_name):
        return {"status": "already_running", "model": model_name}

    success = await scheduler.start_model(model_name)
    if success:
        # 清除相关缓存
        cache_service.delete("api:manage:models:status")
        cache_service.delete("api:manage:models:summary")
        cache_service.delete("api:manage:preload:status")
        cache_service.delete("api:manage:preload:detailed")
        cache_service.delete("api:v1:status")
        return {"status": "starting", "model": model_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to start model {model_name}")

@app.post("/manage/models/{model_name}/stop")
async def stop_model(model_name: str):
    logger.info(f"Stopping model {model_name}")
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    if not scheduler.is_model_running(model_name):
        return {"status": "already_stopped", "model": model_name}

    success = await scheduler.stop_model(model_name)
    if success:
        # 清除相关缓存
        cache_service.delete("api:manage:models:status")
        cache_service.delete("api:manage:models:summary")
        cache_service.delete("api:manage:preload:status")
        cache_service.delete("api:manage:preload:detailed")
        cache_service.delete("api:v1:status")
        return {"status": "stopped", "model": model_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to stop model {model_name}")

@app.post("/manage/models/{model_name}/switch")
async def switch_to_model(model_name: str, test_enabled: Optional[bool] = True):
    logger.info(f"Switching to model {model_name} (test_enabled: {test_enabled})")
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)

    success = await scheduler.switch_model(model_name)
    if not success:
        raise HTTPException(status_code=503, detail=f"Failed to switch to model {model_name}, insufficient memory")

    scheduler.mark_model_selected(model_name)
    # 清除相关缓存
    cache_service.delete("api:manage:models:status")
    cache_service.delete("api:manage:models:summary")
    cache_service.delete("api:manage:preload:status")
    cache_service.delete("api:manage:preload:detailed")
    cache_service.delete("api:v1:status")

    if test_enabled:
        logger.info(f"Running self-test for model {model_name}")
        
        model_config = scheduler.get_model_config(model_name)
        model_path = model_config.get('model_path', model_name) if model_config else model_name
        
        test_result = await switch_vllm_model_with_test(model_name, test_enabled=True, model_path=model_path)
        
        if not test_result.get("success", False):
            error_msg = test_result.get("error", "Unknown error during model test")
            logger.error(f"Model {model_name} self-test failed: {error_msg}")
            raise HTTPException(status_code=503, detail=f"Model switch successful but self-test failed: {error_msg}")
        
        logger.info(f"Model {model_name} self-test passed")
        return {
            "status": "switched_and_tested",
            "model": model_name,
            "test_result": test_result.get("test_result")
        }

    return {"status": "switched", "model": model_name}

@app.get("/manage/metrics")
async def get_metrics():
    cache_key = "api:manage:metrics"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached
    
    logger.info("Getting metrics")
    result = metrics.get_metrics()
    
    cache_service.set(cache_key, result, ttl_seconds=10)
    return result

@app.post("/manage/metrics/reset")
async def reset_metrics():
    logger.info("Resetting metrics")
    metrics.reset()
    cache_service.delete("api:manage:metrics")
    return {"status": "reset"}

@app.get("/health")
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

@app.get("/health/detailed")
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

@app.get("/manage/health/alert")
async def check_alert_status():
    cache_key = "api:manage:health:alert"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached
    
    gpu_status = gpu_monitor.get_gpu_status()
    health_info = metrics.get_comprehensive_health_score(gpu_status)
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

@app.get("/metrics")
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

@app.get("/manage/cache/status")
async def get_cache_status():
    """获取缓存服务状态和统计信息"""
    return {
        "cache_updater": cache_updater.get_status(),
        "cache_service": cache_service.get_stats(),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/manage/cache/refresh")
async def refresh_cache(endpoint: Optional[str] = None):
    """刷新指定或所有缓存"""
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

@app.get("/manage/cache/stats")
async def get_cache_stats():
    """获取缓存统计信息"""
    return cache_service.get_stats()

@app.get("/metrics/metadata")
async def get_metrics_metadata():
    return prometheus.get_metrics_dict()

@app.get("/manage/logs/test")
async def test_structured_logging():
    structured_logger.info("Test message", test=True, value=42)
    structured_logger.warning("Warning test", level="high")
    structured_logger.log_request("/test", "GET", 200, 0.123)
    structured_logger.log_model_event("test-model", "started", duration=10.5)
    return {"status": "logging_test_completed"}

@app.get("/manage/redis/health")
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

@app.get("/manage/redis/keys")
async def get_redis_keys(pattern: str = "*"):
    try:
        if not redis_client.is_connected():
            return {"error": "Redis not connected"}

        keys = redis_client.keys(pattern)
        return {"keys": keys, "count": len(keys)}
    except Exception as e:
        return {"error": str(e)}

@app.delete("/manage/redis/flush")
async def flush_redis():
    try:
        if not redis_client.is_connected():
            return {"error": "Redis not connected"}

        success = redis_client.flush_db()
        return {"status": "success" if success else "failed"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/manage/gpu/history")
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
        return {"error": str(e)}

@app.post("/manage/gpu/history/config")
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
        return {"error": str(e)}

@app.get("/manage/websocket/connections")
async def get_websocket_connections():
    return ws_manager.get_connection_stats()

@app.get("/manage/config")
async def get_config():
    logger.info("Getting current configuration")
    return config_watcher.get_config()

@app.put("/manage/config")
async def update_config(request: Request):
    logger.info("Updating configuration")
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
            on_config_changed(current_config)
            logger.info("Configuration updated and saved successfully")
            return {"status": "success", "message": "Configuration updated and persisted", "config": current_config}
        else:
            logger.error("Failed to persist configuration")
            raise HTTPException(status_code=500, detail="Failed to persist configuration")
    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in config update: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid YAML format: {e}")
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/manage/config/reload")
async def reload_config():
    logger.info("Manual configuration reload requested")
    new_config = config_watcher.load_config()
    on_config_changed(new_config)
    return {"status": "reloaded", "config": new_config}

class ServiceControlRequest(BaseModel):
    service_name: Optional[str] = None

@app.get("/manage/service/status")
async def get_python_service_status(refresh: Optional[bool] = False):
    """获取 Python 控制器服务状态"""
    cache_key = "api:manage:service:status"

    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached

    logger.info("Getting Python service status")

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

@app.post("/manage/service/start")
async def start_python_service(request: ServiceControlRequest = None):
    """启动 Python 控制器服务"""
    service_name = request.service_name if request and request.service_name else "aiclient-python"
    logger.info(f"Starting service: {service_name}")
    
    success = sys_controller.start_service(service_name)
    if success:
        return {"status": "started", "service": service_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to start service: {service_name}")

@app.post("/manage/service/stop")
async def stop_python_service(request: ServiceControlRequest = None):
    """停止 Python 控制器服务"""
    service_name = request.service_name if request and request.service_name else "aiclient-python"
    logger.info(f"Stopping service: {service_name}")
    
    success = sys_controller.stop_service(service_name)
    if success:
        return {"status": "stopped", "service": service_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to stop service: {service_name}")

@app.post("/manage/service/restart")
async def restart_python_service(request: ServiceControlRequest = None):
    """重启 Python 控制器服务"""
    service_name = request.service_name if request and request.service_name else "aiclient-python"
    logger.info(f"Restarting service: {service_name}")
    
    success = sys_controller.restart_service(service_name)
    if success:
        return {"status": "restarted", "service": service_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to restart service: {service_name}")

@app.get("/manage/preload/status")
async def get_preload_status():
    cache_key = "api:manage:preload:detailed"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached
    
    logger.info("Getting preload status")
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

@app.post("/manage/preload/{model_name}/enable")
async def enable_preload(model_name: str):
    logger.info(f"Enabling preload for model {model_name}")
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)
    
    success = scheduler.schedule_preload(model_name)
    if success:
        return {"status": "preload_enabled", "model": model_name}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to enable preload for model {model_name}")

@app.post("/manage/preload/{model_name}/disable")
async def disable_preload(model_name: str):
    logger.info(f"Disabling preload for model {model_name}")
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)
    
    success = scheduler.cancel_preload(model_name)
    if success:
        return {"status": "preload_disabled", "model": model_name}
    else:
        return {"status": "already_disabled", "model": model_name}

@app.get("/manage/preload/all")
async def preload_all_models():
    logger.info("Preloading all models")
    results = {}
    for model_name in scheduler.get_available_models():
        success = scheduler.schedule_preload(model_name)
        results[model_name] = {"status": "preloading" if success else "failed"}
    return results

@app.get("/api/v1/status")
async def node_integration_status():
    """Node.js 集成状态检查接口，供 AIClient-2-API 调用"""
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

@app.get("/api/v1/models/{model_name}/info")
async def model_info(model_name: str, refresh: Optional[bool] = False):
    """获取单个模型详细信息"""
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
        "description": config.get("description", "") if config else "",
        "required_memory": config.get("required_memory", "") if config else "",
        "active_requests": scheduler.get_active_requests(model_name),
        "can_accept": scheduler.can_accept_request(model_name),
        "last_used": scheduler.get_model_last_used(model_name).isoformat() if scheduler.get_model_last_used(model_name) else None
    }
    
    cache_service.set(cache_key, result, ttl_seconds=10)
    return result

@app.get("/manage/system/status")
async def system_status():
    """获取系统级状态（CPU、内存、磁盘）"""
    cache_key = "api:manage:system:status"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached
    
    import psutil
    
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
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
        "timestamp": datetime.now().isoformat()
    }
    
    cache_service.set(cache_key, result, ttl_seconds=10)
    return result

@app.get("/manage/models/summary")
async def models_summary(refresh: Optional[bool] = False):
    """获取模型汇总信息（适合前端列表展示）"""
    cache_key = "api:manage:models:summary"
    
    if not refresh:
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached
    
    logger.info("Getting models summary")
    models = scheduler.get_available_models()
    summary = []
    for model in models:
        config = scheduler.get_model_config(model)
        summary.append({
            "name": model,
            "running": scheduler.is_model_running(model),
            "preloaded": scheduler.is_model_preloaded(model),
            "supports_images": scheduler.get_model_supports_images(model),
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

class TestRequest(BaseModel):
    model_name: str

class TestResponse(BaseModel):
    status: str
    message: str
    report: Optional[Dict[str, Any]] = None

class ComparativeAnalysisRequest(BaseModel):
    model_names: Optional[List[str]] = None

@app.post("/v1/test/model/{model_name}", response_model=TestResponse)
async def test_model(model_name: str):
    """测试单个模型的功能和性能"""
    logger.info(f"Starting model test for: {model_name}")
    
    if not scheduler.is_model_available(model_name):
        raise ModelNotFoundException(model_name)
    
    try:
        report = await model_tester.run_tests(model_name)
        
        report_dict = {
            "model_name": report.model_name,
            "test_timestamp": report.test_timestamp,
            "overall_status": report.overall_status,
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
        
        return {
            "status": "completed",
            "message": f"Tests completed for {model_name}",
            "report": report_dict
        }
    except Exception as e:
        logger.error(f"Error testing model {model_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

@app.get("/v1/test/report/{model_name}")
async def get_model_test_report(model_name: str):
    """获取指定模型的测试报告"""
    report = model_tester.get_previous_report(model_name)
    
    if not report:
        return {"status": "not_found", "message": f"No test report found for {model_name}"}
    
    return {
        "status": "found",
        "report": {
            "model_name": report.model_name,
            "test_timestamp": report.test_timestamp,
            "overall_status": report.overall_status,
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
    }

@app.get("/v1/test/reports")
async def get_all_test_reports():
    """获取所有模型的测试报告"""
    reports = model_tester.get_all_reports()
    
    if not reports:
        return {"status": "no_reports", "message": "No test reports available"}
    
    result = {}
    for model_name, report in reports.items():
        result[model_name] = {
            "model_name": report.model_name,
            "test_timestamp": report.test_timestamp,
            "overall_status": report.overall_status,
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
    
    return {"status": "success", "reports": result}

@app.post("/v1/test/comparative")
async def run_comparative_analysis(request: ComparativeAnalysisRequest):
    """运行多模型对比分析测试"""
    logger.info(f"Starting comparative analysis for models: {request.model_names}")
    
    try:
        analysis = await model_tester.run_comparative_analysis(request.model_names)
        return {
            "status": "completed",
            "message": "Comparative analysis completed",
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Error running comparative analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Comparative analysis failed: {str(e)}")

@app.delete("/v1/test/reports")
async def clear_test_reports():
    """清除所有测试报告"""
    model_tester.clear_reports()
    return {"status": "success", "message": "All test reports cleared"}

@app.get("/v1/test/status")
async def get_test_status():
    """获取测试框架状态"""
    reports = model_tester.get_all_reports()
    return {
        "status": "ready",
        "models_tested_count": len(reports),
        "models_tested": list(reports.keys()),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/v1/test/model/{model_name}/switch-and-test")
async def switch_and_test_model(model_name: str):
    """切换到指定模型并自动运行测试"""
    logger.info(f"Switching to model {model_name} and running tests")
    
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
        
        await asyncio.sleep(5)
        
        report = await model_tester.run_tests(model_name)
        
        report_dict = {
            "model_name": report.model_name,
            "test_timestamp": report.test_timestamp,
            "overall_status": report.overall_status,
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
        
        return {
            "status": "completed",
            "message": f"Successfully switched to {model_name} and completed tests",
            "report": report_dict
        }
    except Exception as e:
        logger.error(f"Error switching and testing model {model_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Switch and test failed: {str(e)}")

@app.get("/manage/monitor/all")
async def get_monitor_all():
    """获取所有监控数据的合并接口，减少HTTP往返"""
    logger.info("Getting all monitor data")
    
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
            "description": config.get("description", "") if config else "",
            "required_memory": config.get("required_memory", "") if config else "",
            "port": scheduler.get_model_port(model)
        })
    
    gpu_status = gpu_monitor.get_gpu_status()
    health_info = metrics.get_comprehensive_health_score(gpu_status)
    
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
        "service": service_info,
        "controllerUrl": CONFIG.CONTROLLER_BASE_URL if 'CONFIG' in dir() else 'http://localhost:5000'
    }

if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Controller Service")
    parser.add_argument("--log-dir", type=str, default=None, help="Custom log directory path")
    parser.add_argument("--port", type=int, default=5000, help="Server port")
    
    args = parser.parse_args()
    
    # Reinitialize logger with custom log directory if provided
    if args.log_dir:
        logger = setup_logger(log_dir=args.log_dir)
    
    logger.info(f"Starting AI Controller service on port {args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
