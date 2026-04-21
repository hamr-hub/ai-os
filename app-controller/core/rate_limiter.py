import redis
import os
import json
import uuid
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

class RateLimiter:
    PRIORITIES = {"low": 1, "normal": 2, "high": 3, "critical": 4}
    
    def __init__(self):
        self.redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        self.client = self._connect()
        self.prefix = "ai_controller:"
        self.queue_prefix = f"{self.prefix}queue:"
        self.request_prefix = f"{self.prefix}request:"
        self.max_queue_length = 100
        self.queue_poll_interval = 0.5
    
    def _connect(self) -> redis.Redis:
        try:
            r = redis.from_url(self.redis_url)
            r.ping()
            return r
        except:
            return None
    
    def _get_active_key(self, model_name: str) -> str:
        return f"{self.prefix}active_requests:{model_name}"
    
    def _get_queue_key(self, model_name: str) -> str:
        return f"{self.queue_prefix}{model_name}"
    
    def _get_request_key(self, request_id: str) -> str:
        return f"{self.request_prefix}{request_id}"
    
    def _decode_value(self, value):
        if isinstance(value, bytes):
            return value.decode()
        return value
    
    def _get_priority_queue_key(self, model_name: str, priority: int) -> str:
        return f"{self.queue_prefix}{model_name}:{priority}"
    
    def _get_all_priority_queue_keys(self, model_name: str) -> List[str]:
        return [self._get_priority_queue_key(model_name, level) for level in self.PRIORITIES.values()]
    
    def _extract_model_name_from_queue_key(self, key: str) -> str:
        suffix = key.replace(self.queue_prefix, "", 1)
        if ":" in suffix:
            return suffix.rsplit(":", 1)[0]
        return suffix
    
    def increment_request(self, model_name: str) -> int:
        if not self.client:
            return 0
        key = self._get_active_key(model_name)
        return self.client.incr(key)
    
    def decrement_request(self, model_name: str) -> int:
        if not self.client:
            return 0
        key = self._get_active_key(model_name)
        value = self.client.decr(key)
        if value < 0:
            self.client.set(key, 0)
            return 0
        return value
    
    def acquire_request(self, model_name: str, max_concurrent: int) -> bool:
        """兼容旧接口：获取请求槽位"""
        if not self.client:
            return False
        key = self._get_active_key(model_name)
        while True:
            try:
                with self.client.pipeline() as pipe:
                    pipe.watch(key)
                    current = pipe.get(key)
                    active = int(current) if current else 0
                    if active >= max_concurrent:
                        pipe.unwatch()
                        return False
                    pipe.multi()
                    pipe.incr(key)
                    pipe.execute()
                    return True
            except redis.WatchError:
                continue
    
    def release_request(self, model_name: str):
        """兼容旧接口：释放请求槽位"""
        self.decrement_request(model_name)
    
    def get_active_requests(self, model_name: str) -> int:
        if not self.client:
            return 0
        key = self._get_active_key(model_name)
        value = self.client.get(key)
        return int(value) if value else 0
    
    def is_available(self, model_name: str, max_concurrent: int) -> bool:
        active = self.get_active_requests(model_name)
        return active < max_concurrent
    
    def can_accept_request(self, model_name: str, max_concurrent: int) -> bool:
        """兼容旧接口：检查是否可以接受请求"""
        return self.is_available(model_name, max_concurrent)
    
    def is_queue_available(self, model_name: str) -> bool:
        """检查队列是否还有空间"""
        if not self.client:
            return False
        return self.get_total_queue_length(model_name) < self.max_queue_length
    
    async def wait_for_slot(self, model_name: str, max_concurrent: int, timeout: int = 30) -> bool:
        """等待可用槽位，超时返回False"""
        if not self.client:
            return False
        
        end_time = datetime.now() + timedelta(seconds=timeout)
        
        while datetime.now() < end_time:
            if self.is_available(model_name, max_concurrent):
                return True
            
            if self.get_queue_length(model_name) >= self.max_queue_length:
                return False
            
            await asyncio.sleep(self.queue_poll_interval)
        
        return False
    
    def get_wait_time_estimate(self, model_name: str, max_concurrent: int) -> float:
        """估算等待时间（秒）"""
        queue_length = self.get_queue_length(model_name)
        if queue_length == 0:
            return 0.0
        
        avg_processing_time = 10.0
        return (queue_length / max_concurrent) * avg_processing_time
    
    def reset_counter(self, model_name: str):
        if not self.client:
            return
        key = self._get_active_key(model_name)
        self.client.delete(key)
    
    def enqueue_request(self, model_name: str, request_data: Dict[str, Any], priority: str = "normal") -> str:
        if not self.client:
            return ""
        
        priority_level = self.PRIORITIES.get(priority, 2)
        request_id = str(uuid.uuid4())
        queue_key = self._get_priority_queue_key(model_name, priority_level)
        request_key = self._get_request_key(request_id)
        
        request_info = {
            "id": request_id,
            "model_name": model_name,
            "data": request_data,
            "priority": priority,
            "priority_level": priority_level,
            "enqueued_at": datetime.now().isoformat(),
            "status": "queued"
        }
        
        self.client.set(request_key, json.dumps(request_info), ex=3600)
        self.client.rpush(queue_key, request_id)
        
        return request_id
    
    def dequeue_request(self, model_name: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None
        
        for priority_level in sorted(self.PRIORITIES.values(), reverse=True):
            queue_key = self._get_priority_queue_key(model_name, priority_level)
            request_id = self.client.lpop(queue_key)
            
            if request_id:
                request_id = self._decode_value(request_id)
                request_key = self._get_request_key(request_id)
                request_data = self.client.get(request_key)
                
                if request_data:
                    info = json.loads(self._decode_value(request_data))
                    info["status"] = "processing"
                    self.client.set(request_key, json.dumps(info), ex=3600)
                    return info
        
        return None
    
    def get_queue_length(self, model_name: str) -> int:
        if not self.client:
            return 0
        return self.get_total_queue_length(model_name)
    
    def get_total_queue_length(self, model_name: str) -> int:
        """获取所有优先级队列的总长度"""
        if not self.client:
            return 0
        
        total_length = 0
        for queue_key in self._get_all_priority_queue_keys(model_name):
            total_length += self.client.llen(queue_key)
        
        return total_length
    
    def get_queue_status(self, model_name: str) -> Dict[str, Any]:
        return {
            "active_requests": self.get_active_requests(model_name),
            "queue_length": self.get_queue_length(model_name)
        }
    
    def cancel_request(self, request_id: str) -> bool:
        if not self.client:
            return False
        
        request_key = self._get_request_key(request_id)
        request_data = self.client.get(request_key)
        
        if not request_data:
            return False
        
        info = json.loads(self._decode_value(request_data))
        if info["status"] == "queued":
            model_name = info["model_name"]
            priority_level = info.get("priority_level", self.PRIORITIES.get(info.get("priority", "normal"), 2))
            queue_key = self._get_priority_queue_key(model_name, priority_level)
            self.client.lrem(queue_key, 0, request_id)
        
        info["status"] = "cancelled"
        self.client.set(request_key, json.dumps(info), ex=60)
        
        return True
    
    def set_request_complete(self, request_id: str, result: Optional[Dict[str, Any]] = None):
        if not self.client:
            return
        
        request_key = self._get_request_key(request_id)
        request_data = self.client.get(request_key)
        
        if request_data:
            info = json.loads(self._decode_value(request_data))
            info["status"] = "completed"
            info["completed_at"] = datetime.now().isoformat()
            if result:
                info["result"] = result
            self.client.set(request_key, json.dumps(info), ex=60)
    
    def get_request_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None
        
        request_key = self._get_request_key(request_id)
        request_data = self.client.get(request_key)
        
        if request_data:
            return json.loads(self._decode_value(request_data))
        
        return None
    
    def get_all_queue_status(self) -> Dict[str, Dict[str, int]]:
        if not self.client:
            return {}
        
        pattern = f"{self.queue_prefix}*"
        keys = self.client.keys(pattern)
        
        status = {}
        model_names = set()
        for key in keys:
            key_str = self._decode_value(key)
            model_names.add(self._extract_model_name_from_queue_key(key_str))
        
        for model_name in model_names:
            status[model_name] = {
                "active_requests": self.get_active_requests(model_name),
                "queue_length": self.get_queue_length(model_name)
            }
        
        return status
    
    def clear_queue(self, model_name: str):
        if not self.client:
            return
        
        self.client.delete(*self._get_all_priority_queue_keys(model_name))
    
    def close(self):
        if self.client:
            self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
