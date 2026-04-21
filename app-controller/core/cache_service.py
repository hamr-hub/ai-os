from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from .redis_client import RedisClient, redis_cache, async_redis_cache

CACHE_TTL = {
    'short': 60,
    'medium': 300,
    'long': 3600,
    'very_long': 86400
}

class CacheService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheService, cls).__new__(cls)
            cls._instance._redis = RedisClient()
            cls._instance._local_cache = {}
            cls._instance._local_cache_expiry = {}
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        self._initialized = True
    
    def _is_local_cache_valid(self, key: str) -> bool:
        expiry = self._local_cache_expiry.get(key)
        if expiry is None:
            return False
        return datetime.now() < expiry
    
    def _set_local_cache(self, key: str, value: Any, ttl_seconds: int):
        self._local_cache[key] = value
        self._local_cache_expiry[key] = datetime.now() + timedelta(seconds=ttl_seconds)
    
    def _get_local_cache(self, key: str) -> Optional[Any]:
        if self._is_local_cache_valid(key):
            return self._local_cache.get(key)
        return None
    
    def _clear_local_cache(self, key: str = None):
        if key:
            self._local_cache.pop(key, None)
            self._local_cache_expiry.pop(key, None)
        else:
            self._local_cache.clear()
            self._local_cache_expiry.clear()
    
    def get(self, key: str, ttl_seconds: int = 300) -> Optional[Any]:
        local_value = self._get_local_cache(key)
        if local_value is not None:
            return local_value
        
        if self._redis.is_connected():
            value = self._redis.get_with_stats(key)
            if value is not None:
                self._set_local_cache(key, value, min(ttl_seconds, 60))
                return value
        
        return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300, ttl: int = None) -> bool:
        effective_ttl = ttl if ttl is not None else ttl_seconds
        self._set_local_cache(key, value, min(effective_ttl, 60))
        
        if self._redis.is_connected():
            return self._redis.set_with_stats(key, value, expire=effective_ttl)
        
        return True
    
    def delete(self, key: str) -> bool:
        self._clear_local_cache(key)
        
        if self._redis.is_connected():
            return self._redis.delete_with_stats(key)
        
        return True
    
    def delete_pattern(self, pattern: str) -> int:
        keys_to_clear = [k for k in self._local_cache.keys() if pattern.replace('*', '') in k]
        for key in keys_to_clear:
            self._clear_local_cache(key)
        
        if self._redis.is_connected():
            return self._redis.delete_pattern(pattern)
        
        return len(keys_to_clear)
    
    def exists(self, key: str) -> bool:
        if self._is_local_cache_valid(key):
            return True
        
        if self._redis.is_connected():
            return self._redis.exists(key)
        
        return False
    
    def get_with_fallback(self, key: str, fallback_func: Callable[[], Any], 
                          ttl_seconds: int = 300, force_refresh: bool = False) -> Any:
        if not force_refresh:
            value = self.get(key, ttl_seconds)
            if value is not None:
                return value
        
        value = fallback_func()
        if value is not None:
            self.set(key, value, ttl_seconds)
        
        return value
    
    async def async_get_with_fallback(self, key: str, fallback_func: Callable[[], Any],
                                      ttl_seconds: int = 300, force_refresh: bool = False) -> Any:
        if not force_refresh:
            value = self.get(key, ttl_seconds)
            if value is not None:
                return value
        
        value = await fallback_func()
        if value is not None:
            self.set(key, value, ttl_seconds)
        
        return value
    
    def get_multi(self, keys: List[str]) -> Dict[str, Any]:
        result = {}
        missing_keys = []
        
        for key in keys:
            local_value = self._get_local_cache(key)
            if local_value is not None:
                result[key] = local_value
            else:
                missing_keys.append(key)
        
        if missing_keys and self._redis.is_connected():
            redis_result = self._redis.mget_json(missing_keys)
            result.update(redis_result)
            
            for key, value in redis_result.items():
                if value is not None:
                    self._set_local_cache(key, value, 60)
        
        return result
    
    def set_multi(self, items: Dict[str, Any], ttl_seconds: int = 300) -> bool:
        for key, value in items.items():
            self._set_local_cache(key, value, min(ttl_seconds, 60))
        
        if self._redis.is_connected():
            return self._redis.mset_json(items, expire=ttl_seconds)
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        stats = {
            'local_cache_size': len(self._local_cache),
            'redis_connected': self._redis.is_connected()
        }
        
        if self._redis.is_connected():
            stats.update(self._redis.get_cache_stats())
            stats['memory_usage'] = self._redis.get_memory_usage()
        
        return stats
    
    def reset_stats(self):
        if self._redis.is_connected():
            self._redis.reset_cache_stats()
    
    def flush_all(self):
        self._clear_local_cache()
        
        if self._redis.is_connected():
            self._redis.flush_db()

cache_service = CacheService()