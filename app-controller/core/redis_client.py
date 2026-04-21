import redis
import asyncio
from typing import Optional, Any, Dict, List, Callable, TypeVar
import json
import os
import hashlib
from datetime import datetime, timedelta
from functools import wraps

T = TypeVar('T')

def redis_cache(key_prefix: str, expire: int = 60, key_builder: Optional[Callable[..., str]] = None):
    """
    Redis缓存装饰器
    :param key_prefix: 缓存键前缀
    :param expire: 过期时间（秒），默认60秒
    :param key_builder: 自定义键生成函数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            client = RedisClient()
            if not client.is_connected():
                return func(*args, **kwargs)
            
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                args_hash = hashlib.md5(str(args).encode() + str(kwargs).encode()).hexdigest()[:16]
                cache_key = f"{key_prefix}:{args_hash}"
            
            cached = client.get_json(cache_key)
            if cached is not None:
                return cached
            
            result = func(*args, **kwargs)
            if result is not None:
                client.set_json(cache_key, result, expire=expire)
            
            return result
        return wrapper
    return decorator

def async_redis_cache(key_prefix: str, expire: int = 60, key_builder: Optional[Callable[..., str]] = None):
    """
    异步Redis缓存装饰器
    :param key_prefix: 缓存键前缀
    :param expire: 过期时间（秒），默认60秒
    :param key_builder: 自定义键生成函数
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            client = RedisClient()
            if not client.is_connected():
                return await func(*args, **kwargs)
            
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                args_hash = hashlib.md5(str(args).encode() + str(kwargs).encode()).hexdigest()[:16]
                cache_key = f"{key_prefix}:{args_hash}"
            
            cached = client.get_json(cache_key)
            if cached is not None:
                return cached
            
            result = await func(*args, **kwargs)
            if result is not None:
                client.set_json(cache_key, result, expire=expire)
            
            return result
        return wrapper
    return decorator

class RedisClient:
    _instance = None
    _default_expire = 300
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.host = host
        self.port = port
        self.db = db
        self._client = None
        self._initialized = True
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
    
    def connect(self):
        if self._client is not None:
            try:
                self._client.ping()
                return True
            except:
                pass
        
        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            self._client.ping()
            return True
        except Exception as e:
            self._client = None
            return False
    
    def is_connected(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.ping()
            return True
        except:
            return False
    
    def get_client(self) -> Optional[redis.Redis]:
        if not self.is_connected():
            self.connect()
        return self._client
    
    def get(self, key: str) -> Optional[str]:
        client = self.get_client()
        if client is None:
            return None
        return client.get(key)
    
    def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            if expire:
                client.set(key, value, ex=expire)
            else:
                client.set(key, value)
            return True
        except:
            return False
    
    def set_json(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        try:
            json_str = json.dumps(value)
            return self.set(key, json_str, expire)
        except:
            return False
    
    def get_json(self, key: str) -> Optional[Any]:
        value = self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except:
            return None
    
    def delete(self, key: str) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            client.delete(key)
            return True
        except:
            return False
    
    def exists(self, key: str) -> bool:
        client = self.get_client()
        if client is None:
            return False
        return client.exists(key) > 0
    
    def keys(self, pattern: str = "*") -> List[str]:
        client = self.get_client()
        if client is None:
            return []
        return client.keys(pattern)
    
    def flush_db(self) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            client.flushdb()
            return True
        except:
            return False
    
    def hset(self, key: str, mapping: Dict[str, str]) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            client.hset(key, mapping=mapping)
            return True
        except:
            return False
    
    def hget(self, key: str, field: str) -> Optional[str]:
        client = self.get_client()
        if client is None:
            return None
        return client.hget(key, field)
    
    def hgetall(self, key: str) -> Dict[str, str]:
        client = self.get_client()
        if client is None:
            return {}
        return client.hgetall(key)
    
    def lpush(self, key: str, *values: str) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            client.lpush(key, *values)
            return True
        except:
            return False
    
    def rpush(self, key: str, *values: str) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            client.rpush(key, *values)
            return True
        except:
            return False
    
    def lrange(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        client = self.get_client()
        if client is None:
            return []
        return client.lrange(key, start, end)
    
    def incr(self, key: str) -> Optional[int]:
        client = self.get_client()
        if client is None:
            return None
        try:
            return client.incr(key)
        except:
            return None
    
    def decr(self, key: str) -> Optional[int]:
        client = self.get_client()
        if client is None:
            return None
        try:
            return client.decr(key)
        except:
            return None
    
    def _record_hit(self):
        self._cache_stats['hits'] += 1
    
    def _record_miss(self):
        self._cache_stats['misses'] += 1
    
    def _record_set(self):
        self._cache_stats['sets'] += 1
    
    def _record_delete(self):
        self._cache_stats['deletes'] += 1
    
    def get_cache_stats(self) -> Dict[str, int]:
        return {**self._cache_stats}
    
    def reset_cache_stats(self):
        self._cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
    
    def get_with_stats(self, key: str) -> Optional[Any]:
        value = self.get_json(key)
        if value is not None:
            self._record_hit()
        else:
            self._record_miss()
        return value
    
    def set_with_stats(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        success = self.set_json(key, value, expire)
        if success:
            self._record_set()
        return success
    
    def delete_with_stats(self, key: str) -> bool:
        success = self.delete(key)
        if success:
            self._record_delete()
        return success
    
    def delete_pattern(self, pattern: str) -> int:
        client = self.get_client()
        if client is None:
            return 0
        try:
            keys = client.keys(pattern)
            if keys:
                client.delete(*keys)
                self._cache_stats['deletes'] += len(keys)
                return len(keys)
            return 0
        except:
            return 0
    
    def set_with_tag(self, key: str, value: Any, tag: str, expire: Optional[int] = None) -> bool:
        success = self.set_json(key, value, expire)
        if success:
            self._record_set()
            tag_key = f"tag:{tag}"
            client = self.get_client()
            if client:
                client.sadd(tag_key, key)
                if expire:
                    client.expire(tag_key, expire)
        return success
    
    def delete_by_tag(self, tag: str) -> int:
        tag_key = f"tag:{tag}"
        client = self.get_client()
        if client is None:
            return 0
        try:
            keys = client.smembers(tag_key)
            if keys:
                keys = list(keys)
                client.delete(*keys)
                client.delete(tag_key)
                self._cache_stats['deletes'] += len(keys)
                return len(keys)
            return 0
        except:
            return 0
    
    def get_keys_by_tag(self, tag: str) -> List[str]:
        tag_key = f"tag:{tag}"
        client = self.get_client()
        if client is None:
            return []
        try:
            return list(client.smembers(tag_key))
        except:
            return []
    
    def mget_json(self, keys: List[str]) -> Dict[str, Any]:
        client = self.get_client()
        if client is None:
            return {}
        try:
            values = client.mget(keys)
            result = {}
            for i, key in enumerate(keys):
                if values[i] is not None:
                    try:
                        result[key] = json.loads(values[i])
                        self._record_hit()
                    except:
                        result[key] = None
                else:
                    self._record_miss()
            return result
        except:
            return {}
    
    def mset_json(self, items: Dict[str, Any], expire: Optional[int] = None) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            pipeline = client.pipeline()
            for key, value in items.items():
                json_str = json.dumps(value)
                if expire:
                    pipeline.set(key, json_str, ex=expire)
                else:
                    pipeline.set(key, json_str)
            pipeline.execute()
            self._cache_stats['sets'] += len(items)
            return True
        except:
            return False
    
    def setnx_json(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            json_str = json.dumps(value)
            result = client.set(key, json_str, ex=expire, nx=True)
            if result:
                self._record_set()
            return result is not None
        except:
            return False
    
    def ttl(self, key: str) -> Optional[int]:
        client = self.get_client()
        if client is None:
            return None
        try:
            return client.ttl(key)
        except:
            return None
    
    def persist(self, key: str) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            return client.persist(key)
        except:
            return False
    
    def get_memory_usage(self) -> Dict[str, int]:
        client = self.get_client()
        if client is None:
            return {}
        try:
            info = client.info('memory')
            return {
                'used': info.get('used_memory', 0),
                'used_human': info.get('used_memory_human', ''),
                'peak': info.get('used_memory_peak', 0),
                'peak_human': info.get('used_memory_peak_human', ''),
                'fragmentation': info.get('mem_fragmentation_ratio', 0)
            }
        except:
            return {}

redis_client = RedisClient()