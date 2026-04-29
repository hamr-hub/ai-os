import httpx
import json
import os
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from core.scheduler import Scheduler
from core.monitor import GPUMonitor
from core.websocket_manager import WebSocketManager
from core.metrics import MetricsCollector

def _build_backend_url(scheduler: Scheduler, model_name: str) -> str:
    port = scheduler.get_model_port(model_name)
    return f"http://localhost:{port}"

def _build_backend_model_name(scheduler: Scheduler, model_name: str) -> str:
    model_config = scheduler.get_model_config(model_name)
    return model_config.get('model_path', model_name) if model_config else model_name

class AIClientInterface:
    def __init__(self, scheduler: Scheduler, gpu_monitor: GPUMonitor, ws_manager: WebSocketManager, metrics: MetricsCollector):
        self.scheduler = scheduler
        self.gpu_monitor = gpu_monitor
        self.ws_manager = ws_manager
        self.metrics = metrics
        self._client_cache = {}
        
    def _get_client(self, base_url: str) -> httpx.AsyncClient:
        if base_url not in self._client_cache:
            self._client_cache[base_url] = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_connections=200, max_keepalive_connections=50)
            )
        return self._client_cache[base_url]
    
    async def _forward_request(self, base_url: str, endpoint: str, method: str, **kwargs) -> httpx.Response:
        client = self._get_client(base_url)
        url = f"{base_url}{endpoint}"
        
        if method.upper() == "POST":
            response = await client.post(url, **kwargs)
        elif method.upper() == "GET":
            response = await client.get(url, **kwargs)
        elif method.upper() == "PUT":
            response = await client.put(url, **kwargs)
        elif method.upper() == "DELETE":
            response = await client.delete(url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response
    
    async def chat_completion(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        model_name = request_data.get("model", "")
        stream = request_data.get("stream", False)
        start_time = datetime.now()
        status_code = 200
        
        if not self.scheduler.is_model_available(model_name):
            return {
                "error": {
                    "code": "model_not_found",
                    "message": f"Model {model_name} not found or unavailable"
                }
            }
        
        if not self.scheduler.acquire_request(model_name):
            active = self.scheduler.get_active_requests(model_name)
            limit = self.scheduler.get_concurrency_limit()
            queue_length = self.scheduler.get_queue_length(model_name)
            
            if self.scheduler.is_queue_available(model_name):
                success = await self.scheduler.wait_for_slot(model_name, timeout=30)
                if not success:
                    return {
                        "error": {
                            "code": "rate_limit_exceeded",
                            "message": "Request queue timeout"
                        }
                    }
            else:
                return {
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": f"Too many requests. Active: {active}/{limit}, Queue: {queue_length}"
                    }
                }
        
        try:
            if not self.scheduler.is_model_running(model_name):
                success = await self.scheduler.start_model(model_name)
                if not success:
                    return {
                        "error": {
                            "code": "service_unavailable",
                            "message": f"Failed to start model {model_name}"
                        }
                    }
                await asyncio.sleep(5)

            self.scheduler.mark_model_selected(model_name)

            vllm_url = _build_backend_url(self.scheduler, model_name)

            model_config = self.scheduler.get_model_config(model_name)
            vllm_model_name = _build_backend_model_name(self.scheduler, model_name)

            payload = request_data.copy()
            payload['model'] = vllm_model_name

            client = self._get_client(vllm_url)
            response = await client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()
            
            result = response.json()
            result['model'] = model_name
            
            self.metrics.record_request(
                endpoint="/v1/chat/completions",
                status_code=200,
                response_time=(datetime.now() - start_time).total_seconds(),
                model_name=model_name
            )
            
            return result
            
        except httpx.HTTPError as e:
            status_code = 503
            return {
                "error": {
                    "code": "service_unavailable",
                    "message": f"vLLM service error: {str(e)}"
                }
            }
        finally:
            self.scheduler.release_request(model_name)
    
    async def chat_completion_stream(self, request_data: Dict[str, Any]):
        model_name = request_data.get("model", "")
        start_time = datetime.now()
        
        if not self.scheduler.is_model_available(model_name):
            yield json.dumps({
                "error": {
                    "code": "model_not_found",
                    "message": f"Model {model_name} not found or unavailable"
                }
            })
            return
        
        if not self.scheduler.acquire_request(model_name):
            active = self.scheduler.get_active_requests(model_name)
            limit = self.scheduler.get_concurrency_limit()
            yield json.dumps({
                "error": {
                    "code": "rate_limit_exceeded",
                    "message": f"Too many requests. Active: {active}/{limit}"
                }
            })
            return
        
        try:
            if not self.scheduler.is_model_running(model_name):
                success = await self.scheduler.start_model(model_name)
                if not success:
                    yield json.dumps({
                        "error": {
                            "code": "service_unavailable",
                            "message": f"Failed to start model {model_name}"
                        }
                    })
                    return
                await asyncio.sleep(5)

            self.scheduler.mark_model_selected(model_name)

            vllm_url = _build_backend_url(self.scheduler, model_name)

            model_config = self.scheduler.get_model_config(model_name)
            vllm_model_name = _build_backend_model_name(self.scheduler, model_name)

            payload = request_data.copy()
            payload['model'] = vllm_model_name

            timeout = httpx.Timeout(connect=10.0, read=120.0, write=60.0, pool=60.0)
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream('POST', f"{vllm_url}/v1/chat/completions", json=payload) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_lines():
                        if chunk.startswith("data: "):
                            chunk_data = chunk[6:]
                            if chunk_data == "[DONE]":
                                yield f"data: {json.dumps({
                                    'id': f'chatcmpl-{os.urandom(12).hex()}',
                                    'object': 'chat.completion.chunk',
                                    'created': int(asyncio.get_event_loop().time()),
                                    'model': model_name,
                                    'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]
                                })}\n\n"
                                break
                            try:
                                json_chunk = json.loads(chunk_data)
                                json_chunk['model'] = model_name
                                yield f"data: {json.dumps(json_chunk)}\n\n"
                            except json.JSONDecodeError:
                                yield f"data: {chunk_data}\n\n"
            
            self.metrics.record_request(
                endpoint="/v1/chat/completions",
                status_code=200,
                response_time=(datetime.now() - start_time).total_seconds(),
                model_name=model_name
            )
            
        except httpx.HTTPError as e:
            yield json.dumps({
                "error": {
                    "code": "service_unavailable",
                    "message": f"vLLM service error: {str(e)}"
                }
            })
        finally:
            self.scheduler.release_request(model_name)
    
    async def list_models(self, refresh: bool = False) -> Dict[str, Any]:
        cache_key = "aiclient:models"
        
        if not refresh:
            cached = self.metrics._cache.get(cache_key)
            if cached is not None:
                return cached
        
        models = self.scheduler.get_available_models()
        result = {
            "object": "list",
            "data": [
                {
                    "id": model_name,
                    "object": "model",
                    "created": 0,
                    "owned_by": "local",
                    "running": self.scheduler.is_model_running(model_name),
                    "supported": self.scheduler.get_model_supports_images(model_name)
                }
                for model_name in models
            ]
        }
        
        self.metrics._cache.set(cache_key, result, ttl_seconds=300)
        return result
    
    async def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        config = self.scheduler.get_model_config(model_name)
        if not config:
            return None

        return {
            "id": model_name,
            "object": "model",
            "created": 0,
            "owned_by": "local",
            "running": self.scheduler.is_model_running(model_name),
            "port": config.get("port"),
            "service": config.get("service"),
            "backend_type": self.scheduler.get_model_backend_type(model_name),
            "required_memory": config.get("required_memory"),
            "supports_images": config.get("supports_images", False),
            "description": config.get("description", "")
        }
    
    async def embedding(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        model_name = request_data.get("model", "")
        start_time = datetime.now()
        
        if not self.scheduler.is_model_available(model_name):
            return {
                "error": {
                    "code": "model_not_found",
                    "message": f"Model {model_name} not found or unavailable"
                }
            }
        
        if not self.scheduler.acquire_request(model_name):
            return {
                "error": {
                    "code": "rate_limit_exceeded",
                    "message": "Too many requests"
                }
            }
        
        try:
            if not self.scheduler.is_model_running(model_name):
                success = await self.scheduler.start_model(model_name)
                if not success:
                    return {
                        "error": {
                            "code": "service_unavailable",
                            "message": f"Failed to start model {model_name}"
                        }
                    }
                await asyncio.sleep(5)

            self.scheduler.mark_model_selected(model_name)

            vllm_url = _build_backend_url(self.scheduler, model_name)

            model_path = _build_backend_model_name(self.scheduler, model_name)
            
            payload = {
                "model": model_path,
                "input": request_data.get("input", ""),
                "encoding_format": request_data.get("encoding_format", "float")
            }
            if "dimensions" in request_data:
                payload["dimensions"] = request_data["dimensions"]
            
            client = self._get_client(vllm_url)
            response = await client.post("/v1/embeddings", json=payload)
            response.raise_for_status()
            
            result = response.json()
            self.metrics.record_request(
                endpoint="/v1/embeddings",
                status_code=200,
                response_time=(datetime.now() - start_time).total_seconds(),
                model_name=model_name
            )
            
            return result
            
        except httpx.HTTPError as e:
            return {
                "error": {
                    "code": "service_unavailable",
                    "message": f"vLLM service error: {str(e)}"
                }
            }
        finally:
            self.scheduler.release_request(model_name)
    
    async def health_check(self) -> Dict[str, Any]:
        gpu_status = self.gpu_monitor.get_gpu_status()
        health_score = self.metrics.get_comprehensive_health_score(gpu_status)
        
        return {
            "status": health_score["status"],
            "timestamp": datetime.now().isoformat(),
            "health_score": health_score["overall"],
            "details": health_score,
            "gpu_available": gpu_status is not None,
            "models": {
                model_name: {
                    "running": self.scheduler.is_model_running(model_name),
                    "active_requests": self.scheduler.get_active_requests(model_name)
                }
                for model_name in self.scheduler.get_available_models()
            }
        }
    
    async def get_gpu_status(self) -> Dict[str, Any]:
        status = self.gpu_monitor.get_gpu_status()
        if not status:
            return {
                "status": "unavailable",
                "message": "No GPU detected"
            }
        return status
    
    async def get_queue_status(self) -> Dict[str, Any]:
        models = self.scheduler.get_available_models()
        queue_info = {}
        
        for model in models:
            queue_info[model] = {
                "active_requests": self.scheduler.get_active_requests(model),
                "concurrency_limit": self.scheduler.get_concurrency_limit(),
                "queue_length": self.scheduler.get_queue_length(model),
                "can_accept": self.scheduler.can_accept_request(model)
            }
        
        return queue_info
    
    async def start_model(self, model_name: str) -> Dict[str, Any]:
        if not self.scheduler.is_model_available(model_name):
            return {"status": "error", "message": f"Model {model_name} not found"}
        
        if self.scheduler.is_model_running(model_name):
            return {"status": "already_running", "model": model_name}
        
        success = await self.scheduler.start_model(model_name)
        if success:
            return {"status": "starting", "model": model_name}
        else:
            return {"status": "error", "message": f"Failed to start model {model_name}"}
    
    async def stop_model(self, model_name: str) -> Dict[str, Any]:
        if not self.scheduler.is_model_available(model_name):
            return {"status": "error", "message": f"Model {model_name} not found"}
        
        if not self.scheduler.is_model_running(model_name):
            return {"status": "already_stopped", "model": model_name}
        
        success = await self.scheduler.stop_model(model_name)
        if success:
            return {"status": "stopped", "model": model_name}
        else:
            return {"status": "error", "message": f"Failed to stop model {model_name}"}
    
    async def switch_model(self, model_name: str) -> Dict[str, Any]:
        if not self.scheduler.is_model_available(model_name):
            return {"status": "error", "message": f"Model {model_name} not found"}
        
        success = await self.scheduler.switch_model(model_name)
        if success:
            return {"status": "switched", "model": model_name}
        else:
            return {"status": "error", "message": f"Failed to switch to model {model_name}, insufficient memory"}
    
    async def get_metrics(self) -> Dict[str, Any]:
        return self.metrics.get_metrics()
    
    async def close(self):
        for client in self._client_cache.values():
            await client.aclose()
        self._client_cache.clear()