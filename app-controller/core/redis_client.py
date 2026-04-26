import redis
import asyncio
from typing import Optional, Any, Dict, List, Callable, TypeVar
import json
import os
import hashlib
import time
from datetime import datetime, timedelta
from functools import wraps
import logging

from .config import load_config, AppConfig

logger = logging.getLogger(__name__)

T = TypeVar('T')

def redis_cache(key_prefix: str, expire: int = 60, key_builder: Optional[Callable[..., str]] = None):
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
    _config_loaded = False
    _ping_cache_ttl = 5

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, host: str = None, port: int = None, db: int = None, config_path: str = None):
        if hasattr(self, '_initialized') and self._initialized:
            return

        config_source = "default"

        if host is not None and port is not None:
            self.host = host
            self.port = port
            self.db = db if db is not None else 0
            config_source = "parameter"
        else:
            try:
                config = load_config(config_path or "app-controller/config.yaml")
                if config.settings and config.settings.redis:
                    self.host = config.settings.redis.host
                    self.port = config.settings.redis.port
                    self.db = config.settings.redis.db
                    config_source = "config"
                else:
                    self.host = "localhost"
                    self.port = 6379
                    self.db = 0
            except Exception:
                self.host = os.getenv("REDIS_HOST", "localhost")
                try:
                    self.port = int(os.getenv("REDIS_PORT", "6379"))
                except ValueError:
                    self.port = 6379
                try:
                    self.db = int(os.getenv("REDIS_DB", "0"))
                except ValueError:
                    self.db = 0
                config_source = "env"

        logger.info(f"[Redis] 连接配置: {self.host}:{self.port} (来源: {config_source})")

        self._client = None
        self._initialized = True
        self._last_ping_time = None
        self._last_ping_result = False
        self._reconnect_cooldown = 0
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
            except Exception:
                pass
        
        now = time.time()
        if now < self._reconnect_cooldown:
            return False

        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                max_connections=50,
            )
            self._client.ping()
            self._last_ping_time = now
            self._last_ping_result = True
            return True
        except Exception as e:
            self._client = None
            self._reconnect_cooldown = now + 5
            logger.warning(f"[Redis] 连接失败: {e}")
            return False
    
    def is_connected(self) -> bool:
        if self._client is None:
            return False
        now = time.time()
        if self._last_ping_time and (now - self._last_ping_time) < self._ping_cache_ttl:
            return self._last_ping_result
        try:
            self._client.ping()
            self._last_ping_time = now
            self._last_ping_result = True
            return True
        except Exception as e:
            self._last_ping_time = now
            self._last_ping_result = False
            logger.debug(f"[Redis] PING 失败: {e}")
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
        except Exception as e:
            logger.warning(f"[Redis] SET 失败 key={key}: {e}")
            return False
    
    def set_json(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        try:
            json_str = json.dumps(value)
            return self.set(key, json_str, expire)
        except (TypeError, ValueError) as e:
            logger.warning(f"[Redis] JSON序列化失败 key={key}: {e}")
            return False
    
    def get_json(self, key: str) -> Optional[Any]:
        value = self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"[Redis] JSON反序列化失败 key={key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"[Redis] DELETE 失败 key={key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            return client.exists(key) > 0
        except Exception as e:
            logger.warning(f"[Redis] EXISTS 失败 key={key}: {e}")
            return False
    
    def keys(self, pattern: str = "*") -> List[str]:
        client = self.get_client()
        if client is None:
            return []
        try:
            result = []
            cursor = 0
            while True:
                cursor, batch = client.scan(cursor=cursor, match=pattern, count=100)
                result.extend(batch)
                if cursor == 0:
                    break
            return result
        except Exception as e:
            logger.warning(f"[Redis] SCAN 失败 pattern={pattern}: {e}")
            return []
    
    def flush_db(self) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            client.flushdb()
            return True
        except Exception as e:
            logger.warning(f"[Redis] FLUSHDB 失败: {e}")
            return False
    
    def hset(self, key: str, mapping: Dict[str, str]) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            client.hset(key, mapping=mapping)
            return True
        except Exception as e:
            logger.warning(f"[Redis] HSET 失败 key={key}: {e}")
            return False
    
    def hget(self, key: str, field: str) -> Optional[str]:
        client = self.get_client()
        if client is None:
            return None
        try:
            return client.hget(key, field)
        except Exception as e:
            logger.warning(f"[Redis] HGET 失败 key={key}: {e}")
            return None
    
    def hgetall(self, key: str) -> Dict[str, str]:
        client = self.get_client()
        if client is None:
            return {}
        try:
            return client.hgetall(key)
        except Exception as e:
            logger.warning(f"[Redis] HGETALL 失败 key={key}: {e}")
            return {}
    
    def lpush(self, key: str, *values: str) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            client.lpush(key, *values)
            return True
        except Exception as e:
            logger.warning(f"[Redis] LPUSH 失败 key={key}: {e}")
            return False
    
    def rpush(self, key: str, *values: str) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            client.rpush(key, *values)
            return True
        except Exception as e:
            logger.warning(f"[Redis] RPUSH 失败 key={key}: {e}")
            return False
    
    def lrange(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        client = self.get_client()
        if client is None:
            return []
        try:
            return client.lrange(key, start, end)
        except Exception as e:
            logger.warning(f"[Redis] LRANGE 失败 key={key}: {e}")
            return []
    
    def incr(self, key: str) -> Optional[int]:
        client = self.get_client()
        if client is None:
            return None
        try:
            return client.incr(key)
        except Exception as e:
            logger.warning(f"[Redis] INCR 失败 key={key}: {e}")
            return None
    
    def decr(self, key: str) -> Optional[int]:
        client = self.get_client()
        if client is None:
            return None
        try:
            return client.decr(key)
        except Exception as e:
            logger.warning(f"[Redis] DECR 失败 key={key}: {e}")
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
            keys = self.keys(pattern)
            if keys:
                client.delete(*keys)
                self._cache_stats['deletes'] += len(keys)
                return len(keys)
            return 0
        except Exception as e:
            logger.warning(f"[Redis] DELETE_PATTERN 失败 pattern={pattern}: {e}")
            return 0
    
    def set_with_tag(self, key: str, value: Any, tag: str, expire: Optional[int] = None) -> bool:
        success = self.set_json(key, value, expire)
        if success:
            self._record_set()
            tag_key = f"tag:{tag}"
            client = self.get_client()
            if client:
                try:
                    client.sadd(tag_key, key)
                    if expire:
                        client.expire(tag_key, expire)
                except Exception as e:
                    logger.warning(f"[Redis] SADD 失败 tag_key={tag_key}: {e}")
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
        except Exception as e:
            logger.warning(f"[Redis] DELETE_BY_TAG 失败 tag={tag}: {e}")
            return 0
    
    def get_keys_by_tag(self, tag: str) -> List[str]:
        tag_key = f"tag:{tag}"
        client = self.get_client()
        if client is None:
            return []
        try:
            return list(client.smembers(tag_key))
        except Exception as e:
            logger.warning(f"[Redis] GET_KEYS_BY_TAG 失败 tag={tag}: {e}")
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
                    except (json.JSONDecodeError, ValueError):
                        result[key] = None
                else:
                    self._record_miss()
            return result
        except Exception as e:
            logger.warning(f"[Redis] MGET 失败: {e}")
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
        except Exception as e:
            logger.warning(f"[Redis] MSET 失败: {e}")
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
        except Exception as e:
            logger.warning(f"[Redis] SETNX 失败 key={key}: {e}")
            return False
    
    def ttl(self, key: str) -> Optional[int]:
        client = self.get_client()
        if client is None:
            return None
        try:
            return client.ttl(key)
        except Exception as e:
            logger.warning(f"[Redis] TTL 失败 key={key}: {e}")
            return None
    
    def persist(self, key: str) -> bool:
        client = self.get_client()
        if client is None:
            return False
        try:
            return client.persist(key)
        except Exception as e:
            logger.warning(f"[Redis] PERSIST 失败 key={key}: {e}")
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
        except Exception as e:
            logger.warning(f"[Redis] INFO MEMORY 失败: {e}")
            return {}

redis_client = RedisClient()
