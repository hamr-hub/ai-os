import yaml
import os
import asyncio
import httpx
import threading
import logging
import time
from typing import Dict, Optional, List, Set
from datetime import datetime, timedelta
from .rate_limiter import RateLimiter
from core.cache_service import cache_service
from core.llama_cpp_manager import llama_cpp_manager

logger = logging.getLogger("ai_controller.scheduler")

def _parse_memory_size(size_str: str) -> int:
    if not size_str:
        return 0
    
    size_str = str(size_str).strip().upper()
    multipliers = {
        'TB': 1024 ** 4,
        'GB': 1024 ** 3,
        'MB': 1024 ** 2,
        'KB': 1024,
        'B': 1
    }
    
    for suffix, multiplier in multipliers.items():
        if size_str.endswith(suffix):
            num_str = size_str[:-len(suffix)].strip()
            if num_str:
                try:
                    num = float(num_str)
                    return int(num * multiplier)
                except ValueError:
                    pass
            break
    
    try:
        return int(size_str)
    except ValueError:
        return 0

class Scheduler:
    def __init__(self, gpu_monitor, sys_controller):
        self.gpu_monitor = gpu_monitor
        self.sys_controller = sys_controller
        self.config = self._load_config()
        self.running_models = {}
        self.rate_limiter = RateLimiter()
        self.preloaded_models: Set[str] = set()
        self.model_last_used: Dict[str, datetime] = {}
        self._model_lock = threading.Lock()
        self._switching_in_progress = False
        self._init_preloaded_models()
        self._default_model = None
        self._register_llama_cpp_models()
    
    def _load_config(self) -> Dict:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                if isinstance(config, dict):
                    cache_service.set("ai_controller:cache:config", config, ttl=60)
                    return config
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        return {
            "models": {
                "gemma-2-9b": {
                    "service": "vllm-gemma",
                    "port": 8000,
                    "required_memory": 12 * 1024 ** 3,
                    "preload": False,
                    "keep_alive": True
                },
                "llama-3-8b": {
                    "service": "vllm-llama",
                    "port": 8001,
                    "required_memory": 10 * 1024 ** 3,
                    "preload": False,
                    "keep_alive": True
                }
            },
            "settings": {
                "concurrency_limit": 4,
                "min_available_memory": 2 * 1024 ** 3,
                "preload_timeout": 120,
                "idle_timeout": 300,
                "memory_cleanup_delay": 3,
                "gpu_memory_utilization": 0.9
            }
        }
    
    def _init_preloaded_models(self):
        self.preloaded_models.clear()
        for model_name, model_config in self.config.get('models', {}).items():
            if model_config.get('preload', False):
                self.preloaded_models.add(model_name)

    def _register_llama_cpp_models(self):
        for model_name in list(llama_cpp_manager._configs.keys()):
            llama_cpp_manager.unregister_model(model_name)
        for model_name, model_config in self.config.get('models', {}).items():
            service = model_config.get('service', '')
            if service == 'llama_cpp':
                llama_cpp_manager.register_model(model_name, model_config)

    def set_config(self, new_config: Dict):
        self.config = new_config if isinstance(new_config, dict) else {}
        self._init_preloaded_models()
        self._register_llama_cpp_models()

    def get_model_backend_type(self, model_name: str) -> str:
        config = self.get_model_config(model_name)
        if not config:
            return 'unknown'
        service = config.get('service', '')
        if service == 'llama_cpp':
            return 'llama_cpp'
        return 'vllm'
    
    def get_available_models(self) -> List[str]:
        return list(self.config.get('models', {}).keys())
    
    def _find_matching_model(self, model_name: str) -> Optional[str]:
        """
        根据输入的模型名称查找匹配的配置模型
        支持模糊匹配：忽略大小写，支持简写名称匹配
        """
        models = self.config.get('models', {})
        
        # 精确匹配
        if model_name in models:
            return model_name
        
        # 大小写不敏感匹配
        lower_input = model_name.lower()
        for config_name in models:
            if config_name.lower() == lower_input:
                return config_name
        
        # 简写匹配：输入的简写名称是否是配置名称的一部分（忽略大小写）
        for config_name in models:
            if lower_input in config_name.lower() or config_name.lower() in lower_input:
                return config_name
        
        # 尝试用输入名称查找最接近的匹配
        for config_name in models:
            config_lower = config_name.lower()
            if lower_input.replace('-', '') in config_lower.replace('-', ''):
                return config_name
        
        return None

    def is_model_available(self, model_name: str) -> bool:
        return self._find_matching_model(model_name) is not None
    
    def get_model_config(self, model_name: str) -> Optional[Dict]:
        matched_name = self._find_matching_model(model_name)
        if matched_name:
            config = self.config.get('models', {}).get(matched_name)
            return config
        return None
    
    def get_model_path(self, model_name: str) -> Optional[str]:
        config = self.get_model_config(model_name)
        if config:
            return config.get('model_path', model_name)
        return None
    
    def get_model_port(self, model_name: str) -> Optional[int]:
        config = self.get_model_config(model_name)
        return config.get('port') if config else None
    
    def get_model_service(self, model_name: str) -> Optional[str]:
        config = self.get_model_config(model_name)
        return config.get('service') if config else None

    def get_model_supports_images(self, model_name: str) -> bool:
        config = self.get_model_config(model_name)
        return config.get('supports_images', False) if config else False

    def get_model_supports_tool_calling(self, model_name: str) -> bool:
        config = self.get_model_config(model_name)
        return config.get('supports_tool_calling', False) if config else False

    def get_model_supports_image_generation(self, model_name: str) -> bool:
        config = self.get_model_config(model_name)
        return config.get('supports_image_generation', False) if config else False
    
    def get_model_name(self, model_name: str) -> Optional[str]:
        """获取配置中的实际模型名称"""
        return self._find_matching_model(model_name)

    def get_min_available_memory(self) -> int:
        value = self.config.get('settings', {}).get('min_available_memory', '2GB')
        return _parse_memory_size(value)
    
    def get_concurrency_limit(self) -> int:
        return self.config.get('settings', {}).get('concurrency_limit', 4)
    
    def is_model_running(self, model_name: str) -> bool:
        cache_key = f"ai_controller:cache:model_running:{model_name}"
        # Only cache positive results (True), skip cache for False to allow re-checking
        cached = cache_service.get(cache_key)
        if cached is True:
            return True

        with self._model_lock:
            backend_type = self.get_model_backend_type(model_name)
            logger.info(f"is_model_running({model_name}): checking, backend_type={backend_type}")

            if backend_type == 'llama_cpp':
                running = llama_cpp_manager.is_server_running(model_name)
                if running:
                    if model_name not in self.running_models:
                        self.running_models[model_name] = datetime.now()
                    cache_service.set(cache_key, True, ttl=3)
                    return True

                if model_name in self.running_models:
                    del self.running_models[model_name]
                cache_service.set(cache_key, False, ttl=3)
                return False

            if backend_type == 'vllm':
                from core.vllm_manager import get_current_model_info
                current_info = get_current_model_info()
                logger.info(f"is_model_running({model_name}): backend_type={backend_type}, current_info={current_info}")
                if current_info and current_info.get('running'):
                    current_name = current_info.get('name')
                    logger.info(f"is_model_running: current_name={current_name}, requested={model_name}, match={current_name == model_name}")
                    if current_name == model_name:
                        if model_name not in self.running_models:
                            self.running_models[model_name] = datetime.now()
                        cache_service.set(cache_key, True, ttl=3)
                        return True
                    else:
                        logger.info(f"is_model_running: name mismatch, current={current_name}, requested={model_name}")
                
                if model_name in self.running_models:
                    del self.running_models[model_name]
                cache_service.set(cache_key, False, ttl=3)
                return False

            port = self.get_model_port(model_name)
            if port:
                process_info = self.sys_controller.get_process_info(port)
                if process_info:
                    if model_name not in self.running_models:
                        self.running_models[model_name] = datetime.now()
                    cache_service.set(cache_key, True, ttl=3)
                    return True

            if model_name in self.running_models:
                del self.running_models[model_name]

            cache_service.set(cache_key, False, ttl=3)
            return False
    
    def is_model_preloaded(self, model_name: str) -> bool:
        return model_name in self.preloaded_models
    
    def get_model_last_used(self, model_name: str) -> Optional[datetime]:
        return self.model_last_used.get(model_name)

    def mark_model_selected(self, model_name: str):
        """Record the model most recently selected by an explicit switch action."""
        self.model_last_used[model_name] = datetime.now()

    def get_current_model_name(self) -> Optional[str]:
        """Return the most recently selected running model, if any."""
        running_models = [model for model in self.get_available_models() if self.is_model_running(model)]
        if not running_models:
            return None

        used_running_models = [
            model for model in running_models
            if self.model_last_used.get(model)
        ]
        if used_running_models:
            return max(used_running_models, key=lambda model: self.model_last_used.get(model))

        with self._model_lock:
            tracked_running_models = [
                model for model in running_models
                if self.running_models.get(model)
            ]
            if tracked_running_models:
                return max(tracked_running_models, key=lambda model: self.running_models.get(model))

        return running_models[0]

    def get_default_model(self) -> Optional[str]:
        """Return the default model, if set."""
        if self._default_model and self.is_model_available(self._default_model):
            return self._default_model
        return None

    def set_default_model(self, model_name: str) -> bool:
        """Set the default model for inference requests."""
        if not self.is_model_available(model_name):
            return False
        self._default_model = model_name
        return True

    def clear_default_model(self):
        """Clear the default model setting."""
        self._default_model = None
    
    def get_preloaded_models(self) -> List[str]:
        return list(self.preloaded_models)
    
    def get_active_requests(self, model_name: str) -> int:
        return self.rate_limiter.get_active_requests(model_name)
    
    def acquire_request(self, model_name: str) -> bool:
        return self.rate_limiter.acquire_request(model_name, self.get_concurrency_limit())
    
    def release_request(self, model_name: str):
        self.rate_limiter.release_request(model_name)
        self.model_last_used[model_name] = datetime.now()
    
    def can_accept_request(self, model_name: str) -> bool:
        if not self.is_model_available(model_name):
            return False
        
        mem_info = self.gpu_monitor.get_memory_usage()
        if not mem_info:
            return False
        
        if mem_info.get('available', 0) < self.get_min_available_memory():
            return False
        
        return self.rate_limiter.can_accept_request(model_name, self.get_concurrency_limit())
    
    def is_queue_available(self, model_name: str) -> bool:
        """检查队列是否可用"""
        return self.rate_limiter.get_total_queue_length(model_name) < 100
    
    def get_queue_length(self, model_name: str) -> int:
        """获取队列长度"""
        return self.rate_limiter.get_queue_length(model_name)
    
    def get_wait_time_estimate(self, model_name: str) -> float:
        """估算等待时间"""
        return self.rate_limiter.get_wait_time_estimate(model_name, self.get_concurrency_limit())
    
    async def wait_for_slot(self, model_name: str, timeout: int = 30) -> bool:
        """等待可用槽位，支持优雅降级"""
        return await self.rate_limiter.wait_for_slot(model_name, self.get_concurrency_limit(), timeout)
    
    def enqueue_request(self, model_name: str, request_data: Dict, priority: str = "normal") -> str:
        """将请求加入队列（支持优先级）"""
        return self.rate_limiter.enqueue_request(model_name, request_data, priority)
    
    def get_supported_priorities(self) -> List[str]:
        """获取支持的优先级列表"""
        return list(self.rate_limiter.PRIORITIES.keys())
    
    def schedule_preload(self, model_name: str) -> bool:
        """调度预加载模型"""
        if not self.is_model_available(model_name):
            return False
        
        self.preloaded_models.add(model_name)
        
        model_config = self.get_model_config(model_name)
        if model_config:
            model_config['preload'] = True
        
        return True
    
    def cancel_preload(self, model_name: str) -> bool:
        """取消预加载模型"""
        if model_name not in self.preloaded_models:
            return False
        
        self.preloaded_models.discard(model_name)
        
        model_config = self.get_model_config(model_name)
        if model_config:
            model_config['preload'] = False
        
        return True
    
    def get_preload_status(self) -> Dict:
        """获取预加载状态"""
        preloaded = list(self.preloaded_models)
        all_models = self.get_available_models()
        status = {}
        for model in all_models:
            config = self.get_model_config(model)
            status[model] = {
                "preloaded": model in preloaded,
                "running": self.is_model_running(model),
                "preload_config": config.get("preload", False) if config else False
            }
        return {
            "preloaded_models": preloaded,
            "all_models": all_models,
            "status": status
        }
    
    async def _cleanup_memory_fragmentation(self) -> bool:
        """尝试清理显存碎片"""
        cleanup_delay = self.config.get('settings', {}).get('memory_cleanup_delay', 3)
        await asyncio.sleep(cleanup_delay)
        return True

    def _mark_model_stopped(self, model_name: str):
        with self._model_lock:
            self.running_models.pop(model_name, None)
    
    async def _send_warmup_request(self, model_name: str) -> bool:
        """发送预热请求到 vLLM"""
        port = self.get_model_port(model_name)
        url = f"http://localhost:{port}/v1/chat/completions"
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": "Hello"}],
                        "max_tokens": 1
                    },
                    timeout=30
                )
                if response.status_code != 200:
                    logger.warning("Warmup request for model %s returned status %s", model_name, response.status_code)
                    return False
                return True
        except Exception as exc:
            logger.warning("Warmup request for model %s failed: %s", model_name, exc)
            return False
    
    async def _adjust_gpu_utilization(self, model_name: str, target_utilization: float = 0.9) -> bool:
        """调整 GPU 显存利用率"""
        port = self.get_model_port(model_name)
        url = f"http://localhost:{port}/v1/control"
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    url,
                    json={"gpu_memory_utilization": target_utilization},
                    timeout=10
                )
                if response.status_code >= 400:
                    logger.warning(
                        "GPU utilization adjustment for model %s returned status %s",
                        model_name,
                        response.status_code,
                    )
                    return False
                return True
        except Exception as exc:
            logger.warning("Failed to adjust GPU utilization for model %s: %s", model_name, exc)
            return False
    
    async def start_model(self, model_name: str) -> bool:
        config = self.get_model_config(model_name)
        if not config:
            return False

        service_name = config.get('service')
        if not service_name:
            return False

        backend_type = self.get_model_backend_type(model_name)
        model_path = config.get('model_path')
        replaced_model_name = None

        if backend_type == 'llama_cpp':
            if llama_cpp_manager.is_server_running(model_name):
                with self._model_lock:
                    self.running_models[model_name] = datetime.now()
                return True

            mem_info = self.gpu_monitor.get_memory_usage()
            if mem_info:
                required_memory = _parse_memory_size(config.get('required_memory', 0))
                if mem_info.get('available', 0) < required_memory + self.get_min_available_memory():
                    success = await self._free_up_memory(model_name)
                    if not success:
                        return False

            success = llama_cpp_manager.start_server(model_name)
            if success:
                with self._model_lock:
                    self.running_models[model_name] = datetime.now()

                preload_timeout = self.config.get('settings', {}).get('preload_timeout', 120)
                port = self.get_model_port(model_name)
                ready = await self._wait_for_model_ready(model_name, port, timeout=preload_timeout)
                if not ready:
                    logger.error(f"llama.cpp model {model_name} failed to become ready within {preload_timeout}s")
                    llama_cpp_manager.stop_server(model_name)
                    self._mark_model_stopped(model_name)
                    return False

                warmup_ok = await self._send_warmup_request(model_name)
                if not warmup_ok:
                    logger.warning("Warmup request did not succeed for llama.cpp model %s", model_name)

            return success

        # For vLLM, we need to check if the correct model is already loaded
        if backend_type == 'vllm':
            from core.vllm_manager import get_current_model_info, _update_vllm_script
            
            current_info = get_current_model_info()
            # matched_name is from get_current_model_info which tries to match path to config name
            if current_info and current_info.get('running') and current_info.get('name') == model_name:
                logger.info(f"Model {model_name} is already running in vLLM service")
                with self._model_lock:
                    self.running_models[model_name] = datetime.now()
                return True
            
            # Apply the new model target before touching the currently running service.
            if model_path:
                logger.info(f"Updating vLLM script to model path: {model_path}")
                if not _update_vllm_script(model_path):
                    logger.error(f"Failed to update vLLM script for {model_name}")
                    return False

            # If service is running with wrong model, stop it first
            if self.sys_controller.is_service_running(service_name):
                logger.info(f"vLLM service running with different model, stopping it first")
                replaced_model_name = current_info.get('name') if current_info else None
                if not self.sys_controller.stop_service(service_name):
                    logger.error("Failed to stop vLLM service %s before starting %s", service_name, model_name)
                    return False
                if replaced_model_name:
                    self._mark_model_stopped(replaced_model_name)
                # Give the driver/monitor cache a chance to observe released VRAM before re-checking memory.
                await self._cleanup_memory_fragmentation()
                await self.gpu_monitor.refresh_cache()

        # General service start logic
        mem_info = self.gpu_monitor.get_memory_usage()
        if mem_info:
            required_memory = _parse_memory_size(config.get('required_memory', 0))
            required_with_headroom = required_memory + self.get_min_available_memory()

            if backend_type == 'vllm' and replaced_model_name and mem_info.get('available', 0) < required_with_headroom:
                # The immediate reading after a vLLM stop can be stale; refresh once before failing memory checks.
                gpu_status = await self.gpu_monitor.refresh_cache()
                if gpu_status:
                    mem_info = {
                        "total": gpu_status.get("total_memory", mem_info.get("total", 0)),
                        "used": gpu_status.get("used_memory", mem_info.get("used", 0)),
                        "available": gpu_status.get("available_memory", mem_info.get("available", 0)),
                    }

            if mem_info.get('available', 0) < required_with_headroom:
                success = await self._free_up_memory(model_name)
                if not success:
                    logger.error(f"Failed to free up enough memory for {model_name}")
                    return False

        success = self.sys_controller.start_service(service_name)
        if success:
            with self._model_lock:
                self.running_models[model_name] = datetime.now()

            if backend_type == 'vllm':
                # vLLM 大模型加载时间长，接口层返回“starting”后由前端/状态轮询继续观察。
                return True

            # Poll for readiness instead of arbitrary sleep
            preload_timeout = self.config.get('settings', {}).get('preload_timeout', 120)
            port = self.get_model_port(model_name)
            ready = await self._wait_for_model_ready(model_name, port, timeout=preload_timeout)
            
            if ready:
                warmup_ok = await self._send_warmup_request(model_name)
                if not warmup_ok:
                    logger.warning("Warmup request did not succeed for model %s", model_name)
                gpu_util = self.config.get('settings', {}).get('gpu_memory_utilization', 0.9)
                adjust_ok = await self._adjust_gpu_utilization(model_name, gpu_util)
                if not adjust_ok:
                    logger.warning("GPU utilization adjustment did not succeed for model %s", model_name)
                return True
            else:
                logger.error(f"Model {model_name} failed to become ready within {preload_timeout}s")
                self.sys_controller.stop_service(service_name)
                self._mark_model_stopped(model_name)
                return False

        return success

    async def _wait_for_model_ready(self, model_name: str, port: int, timeout: int) -> bool:
        """Poll the model's health endpoint until it is ready."""
        start_time = time.time()
        url = f"http://localhost:{port}/v1/models"
        last_status_code = None
        last_error = None
        
        while time.time() - start_time < timeout:
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        if last_status_code not in (None, 200):
                            logger.info(
                                "Model %s became ready on port %s after transient status %s",
                                model_name,
                                port,
                                last_status_code,
                            )
                        return True
                    last_status_code = response.status_code
                    logger.debug(
                        "Model %s readiness probe returned status %s on port %s",
                        model_name,
                        response.status_code,
                        port,
                    )
            except Exception as exc:
                last_error = str(exc)
            await asyncio.sleep(2)
        if last_status_code is not None:
            logger.error(
                "Model %s readiness probe timed out on port %s after last status %s",
                model_name,
                port,
                last_status_code,
            )
        elif last_error:
            logger.error(
                "Model %s readiness probe timed out on port %s after last error: %s",
                model_name,
                port,
                last_error,
            )
        return False
    
    async def stop_model(self, model_name: str) -> bool:
        config = self.get_model_config(model_name)
        if not config:
            return False

        backend_type = self.get_model_backend_type(model_name)

        if backend_type == 'llama_cpp':
            success = llama_cpp_manager.stop_server(model_name)
            if success:
                await self._cleanup_memory_fragmentation()
                with self._model_lock:
                    if model_name in self.running_models:
                        del self.running_models[model_name]
            return success

        service_name = config.get('service')
        if not service_name:
            return False

        success = self.sys_controller.stop_service(service_name)
        if success:
            await self._cleanup_memory_fragmentation()
            with self._model_lock:
                if model_name in self.running_models:
                    del self.running_models[model_name]

        return success
    
    async def _free_up_memory(self, target_model_name: str, priority: str = "normal") -> bool:
        """智能释放显存，考虑模型优先级和最后使用时间"""
        target_config = self.get_model_config(target_model_name)
        if not target_config:
            return False
        
        target_required = _parse_memory_size(target_config.get('required_memory', 0))
        mem_info = self.gpu_monitor.get_memory_usage()
        
        if not mem_info:
            return False
        
        available_memory = mem_info.get('available', 0)
        needed_memory = target_required + self.get_min_available_memory()
        
        if available_memory >= needed_memory:
            return True
        
        # Try to optimize memory first if we are close
        if available_memory >= target_required:
            logger.info("Memory tight, trying to optimize memory before stopping models")
            await self.gpu_monitor.optimize_memory()
            gpu_status = await self.gpu_monitor.refresh_cache()
            if gpu_status and gpu_status.get('available_memory', 0) >= needed_memory:
                return True

        models_to_stop = []
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        target_priority = priority_order.get(priority, 2)
        
        with self._model_lock:
            for model_name in list(self.running_models.keys()):
                if model_name == target_model_name:
                    continue
                
                config = self.get_model_config(model_name)
                last_used = self.model_last_used.get(model_name, datetime.min)
                model_priority_val = priority_order.get(config.get('priority', 'normal'), 2) if config else 2
                models_to_stop.append({
                    "name": model_name,
                    "priority": model_priority_val,
                    "last_used": last_used,
                    "memory": _parse_memory_size(config.get('required_memory', 0)) if config else 0,
                    "keep_alive": config.get('keep_alive', False) if config else False
                })
        
        # Sort by: 1. Priority (lower first) 2. Last used (older first) 3. Memory size (larger first)
        models_to_stop.sort(key=lambda x: (x["priority"], x["last_used"], -x["memory"]), reverse=True)
        
        for m in models_to_stop:
            logger.info(f"Stopping model {m['name']} to free up memory (priority={m['priority']}, last_used={m['last_used']})")
            await self.stop_model(m["name"])
            
            # Refresh GPU status to get accurate memory info
            gpu_status = await self.gpu_monitor.refresh_cache()
            if gpu_status and gpu_status.get('available_memory', 0) >= needed_memory:
                return True
        
        return False

    async def switch_model(self, target_model_name: str, priority: str = "normal") -> bool:
        """智能切换到目标模型，自动处理显存管理"""
        if not self.is_model_available(target_model_name):
            logger.error(f"Cannot switch to unavailable model: {target_model_name}")
            return False

        if self.is_model_running(target_model_name):
            logger.info(f"Model {target_model_name} is already running, selecting it")
            self.mark_model_selected(target_model_name)
            return True

        logger.info(f"Switching to model {target_model_name} (priority={priority})")
        own_switching_flag = not self._switching_in_progress
        if own_switching_flag:
            self._switching_in_progress = True
        try:
            success = await self._free_up_memory(target_model_name, priority)
            if not success:
                logger.warning(f"Standard memory freeing failed, trying forced cleanup")
                await self.gpu_monitor.force_memory_cleanup()
                gpu_status = await self.gpu_monitor.refresh_cache()
                
                target_config = self.get_model_config(target_model_name)
                target_required = _parse_memory_size(target_config.get('required_memory', 0)) if target_config else 0
                if not gpu_status or gpu_status.get('available_memory', 0) < target_required:
                    logger.error(f"Insufficient memory to start {target_model_name} even after forced cleanup")
                    return False

            success = await self.start_model(target_model_name)
            if success:
                self.mark_model_selected(target_model_name)
            return success
        finally:
            if own_switching_flag:
                self._switching_in_progress = False

    async def switch_model_with_fallback(self, target_model_name: str, fallback_model: str = None) -> bool:
        """带降级策略的模型切换"""
        try:
            success = await self.switch_model(target_model_name)
            if success:
                return True

            if fallback_model and fallback_model != target_model_name:
                logger.info(f"Primary switch to {target_model_name} failed, trying fallback {fallback_model}")
                return await self.switch_model(fallback_model)

            return False
        except Exception as e:
            logger.exception(f"Error switching model to {target_model_name}: {str(e)}")
            if fallback_model and fallback_model != target_model_name:
                return await self.switch_model(fallback_model)
            return False

    async def preload_models(self):
        """预热所有配置为预加载的模型"""
        preload_order = self._get_preload_order()
        for model_name in preload_order:
            if not self.is_model_running(model_name):
                logger.info(f"Preloading model: {model_name}")
                success = await self.start_model(model_name)
                if success:
                    logger.info(f"Successfully preloaded model: {model_name}")
                else:
                    logger.warning(f"Failed to preload model: {model_name}")
                await asyncio.sleep(2)

    def _get_preload_order(self) -> List[str]:
        """根据配置获取预加载顺序，优先加载keep_alive的模型"""
        ordered_models = []
        keep_alive_models = []
        normal_models = []
        
        for model_name in self.preloaded_models:
            config = self.get_model_config(model_name)
            if config and config.get('keep_alive', False):
                keep_alive_models.append(model_name)
            else:
                normal_models.append(model_name)
        
        ordered_models.extend(keep_alive_models)
        ordered_models.extend(normal_models)
        return ordered_models

    async def _health_watcher_loop(self):
        """后台监控模型状态，自动重启异常退出的预加载模型，并清理已停止模型的追踪状态"""
        while True:
            try:
                # Skip health checks during model switch to avoid race conditions
                if self._switching_in_progress:
                    await asyncio.sleep(30)
                    continue

                # 1. Check preloaded models that should be kept alive
                for model_name in self.preloaded_models:
                    config = self.get_model_config(model_name)
                    if config and config.get('keep_alive', False):
                        if self.get_model_backend_type(model_name) == 'vllm':
                            from core.vllm_manager import get_current_model_info

                            current_info = get_current_model_info()
                            current_target = current_info.get('name') if current_info else None
                            if current_target and current_target != model_name:
                                # vLLM 是单实例服务，切换到其他模型后不能让 keep_alive 抢回服务。
                                continue
                        if not self.is_model_running(model_name):
                            logger.warning(f"Preloaded model {model_name} is not running, restarting...")
                            restarted = await self.start_model(model_name)
                            if not restarted:
                                logger.error("Failed to restart keep-alive model %s", model_name)
                
                # 2. Check all models that we think are running
                with self._model_lock:
                    currently_tracked = list(self.running_models.keys())
                
                for model_name in currently_tracked:
                    if not self.is_model_running(model_name):
                        logger.error(f"Model {model_name} crashed or was stopped externally")
                        with self._model_lock:
                            if model_name in self.running_models:
                                del self.running_models[model_name]
                        
                        # Auto-restart if it was the default model or a high priority one
                        if model_name == self._default_model:
                            logger.info(f"Restarting default model: {model_name}")
                            restarted = await self.start_model(model_name)
                            if not restarted:
                                logger.error("Failed to restart default model %s", model_name)
                            
            except Exception as e:
                logger.exception(f"Error in health watcher: {str(e)}")
            await asyncio.sleep(30)
