import yaml
import os
import asyncio
import httpx
import threading
from typing import Dict, Optional, List, Set
from datetime import datetime, timedelta
from .rate_limiter import RateLimiter
from core.cache_service import cache_service

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
        self._init_preloaded_models()
    
    def _load_config(self) -> Dict:
        cached_config = cache_service.get("ai_controller:cache:config")
        if cached_config is not None:
            return cached_config
        
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
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
        for model_name, model_config in self.config.get('models', {}).items():
            if model_config.get('preload', False):
                self.preloaded_models.add(model_name)
    
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
        cache_key = f"ai_controller:cache:model_config:{model_name}"
        cached_config = cache_service.get(cache_key)
        if cached_config is not None:
            return cached_config
        
        matched_name = self._find_matching_model(model_name)
        if matched_name:
            config = self.config.get('models', {}).get(matched_name)
            if config:
                cache_service.set(cache_key, config, ttl=300)
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
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached
        
        with self._model_lock:
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
                return response.status_code == 200
        except Exception:
            return False
    
    async def _adjust_gpu_utilization(self, model_name: str, target_utilization: float = 0.9):
        """调整 GPU 显存利用率"""
        port = self.get_model_port(model_name)
        url = f"http://localhost:{port}/v1/control"
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    url,
                    json={"gpu_memory_utilization": target_utilization},
                    timeout=10
                )
        except Exception:
            pass
    
    async def start_model(self, model_name: str) -> bool:
        config = self.get_model_config(model_name)
        if not config:
            return False
        
        service_name = config.get('service')
        if not service_name:
            return False
        
        if self.sys_controller.is_service_running(service_name):
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
        
        success = self.sys_controller.start_service(service_name)
        if success:
            with self._model_lock:
                self.running_models[model_name] = datetime.now()
            
            preload_timeout = self.config.get('settings', {}).get('preload_timeout', 120)
            await asyncio.sleep(min(30, preload_timeout))
            
            await self._send_warmup_request(model_name)
            
            gpu_util = self.config.get('settings', {}).get('gpu_memory_utilization', 0.9)
            await self._adjust_gpu_utilization(model_name, gpu_util)
        
        return success
    
    async def stop_model(self, model_name: str) -> bool:
        config = self.get_model_config(model_name)
        if not config:
            return False
        
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
    
    async def _free_up_memory(self, target_model_name: str) -> bool:
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
        
        models_to_stop = []
        with self._model_lock:
            for model_name in list(self.running_models.keys()):
                if model_name == target_model_name:
                    continue
                
                config = self.get_model_config(model_name)
                if config and config.get('keep_alive', False):
                    continue
                
                models_to_stop.append((model_name, config.get('required_memory', 0)))
        
        models_to_stop.sort(key=lambda x: x[1], reverse=True)
        
        for model_name, _ in models_to_stop:
            await self.stop_model(model_name)
            
            gpu_status = self.gpu_monitor.get_gpu_status()
            if gpu_status and gpu_status.get('available_memory', 0) >= needed_memory:
                return True
        
        return False
    
    async def switch_model(self, target_model_name: str) -> bool:
        """智能切换到目标模型，自动处理显存管理"""
        if not self.is_model_available(target_model_name):
            return False
        
        if self.is_model_running(target_model_name):
            self.mark_model_selected(target_model_name)
            return True
        
        success = await self._free_up_memory(target_model_name)
        if not success:
            return False

        success = await self.start_model(target_model_name)
        if success:
            self.mark_model_selected(target_model_name)
        return success
    
    async def preload_models(self):
        """预热所有配置为预加载的模型"""
        for model_name in self.preloaded_models:
            if not self.is_model_running(model_name):
                await self.start_model(model_name)
