import subprocess
import json
import re
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from core.cache_service import cache_service

class GPUMonitor:
    def __init__(self):
        self._last_flush_time = datetime.now()
        self._flush_interval = 300
        self._memory_strategy = "balanced"
        self._fragmentation_history: List[float] = []
        self._nvidia_smi_available = self._check_nvidia_smi()
        self._redis_client = None
        self._history_enabled = True
        self._max_history_days = 30
        self._status_cache: Optional[Dict] = None
        self._status_cache_time: Optional[datetime] = None
        self._last_history_cleanup = datetime.min
        self._history_cleanup_interval = timedelta(minutes=5)
        self._cache_update_task: Optional[asyncio.Task] = None
        self._cache_update_interval = 2.0  # 缓存更新间隔，单位秒
    
    def _check_nvidia_smi(self) -> bool:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--version"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def _cache_valid(self) -> bool:
        return (
            self._status_cache is not None
            and self._status_cache_time is not None
        )
    
    async def _update_cache_loop(self):
        """后台任务：定期更新GPU状态缓存"""
        while True:
            try:
                await self._refresh_cache()
            except Exception:
                pass
            await asyncio.sleep(self._cache_update_interval)
    
    async def _refresh_cache(self):
        """刷新GPU状态缓存"""
        if not self._nvidia_smi_available:
            self._status_cache = None
            self._status_cache_time = None
            return
        
        try:
            process = await asyncio.create_subprocess_exec(
                "nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu,power.draw,power.limit,fan.speed,clocks.sm,clocks.mem", "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Decode bytes to string
            stdout_str = stdout.decode('utf-8').strip() if stdout else ''
            stderr_str = stderr.decode('utf-8').strip() if stderr else ''
            
            if process.returncode != 0:
                self._status_cache = None
                self._status_cache_time = None
                return
            
            output = stdout_str
            if not output:
                self._status_cache = None
                self._status_cache_time = None
                return
            
            gpus = []
            for line in output.split('\n'):
                gpu_info = self._parse_gpu_line(line)
                if gpu_info:
                    gpus.append(gpu_info)
            
            if gpus:
                primary_gpu = gpus[0]
                status = {
                    "status": "available",
                    "gpu_count": len(gpus),
                    "name": primary_gpu["name"],
                    "total_memory": primary_gpu["total_memory"],
                    "used_memory": primary_gpu["used_memory"],
                    "available_memory": primary_gpu["available_memory"],
                    "temperature": primary_gpu["temperature"],
                    "utilization": primary_gpu["utilization"],
                    "power_draw": primary_gpu["power_draw"],
                    "power_limit": primary_gpu["power_limit"],
                    "power_percent": primary_gpu["power_percent"],
                    "fan_speed": primary_gpu["fan_speed"],
                    "clock_sm": primary_gpu["clock_sm"],
                    "clock_mem": primary_gpu["clock_mem"],
                    "memory_utilization": primary_gpu["memory_utilization"],
                    "primary": primary_gpu,
                    "all_gpus": gpus
                }
                self._status_cache = status
                self._status_cache_time = datetime.now()
            else:
                self._status_cache = None
                self._status_cache_time = None
        except Exception:
            self._status_cache = None
            self._status_cache_time = None
    
    def start_cache_updater(self):
        """启动缓存更新任务"""
        if self._cache_update_task is None or self._cache_update_task.done():
            self._cache_update_task = asyncio.create_task(self._update_cache_loop())
    
    def stop_cache_updater(self):
        """停止缓存更新任务"""
        if self._cache_update_task and not self._cache_update_task.done():
            self._cache_update_task.cancel()
    
    def _parse_gpu_line(self, line: str) -> Optional[Dict]:
        parts = [part.strip() for part in line.split(',')]
        if len(parts) < 6:
            return None
        total_mb = int(parts[1])
        used_mb = int(parts[2])
        free_mb = int(parts[3])
        temperature = int(parts[4])
        utilization = int(parts[5])
        power_draw = float(parts[6]) if len(parts) > 6 and parts[6] else 0
        power_limit = float(parts[7]) if len(parts) > 7 and parts[7] else 0
        fan_speed = int(parts[8]) if len(parts) > 8 and parts[8].isdigit() else 0
        clock_sm = int(parts[9]) if len(parts) > 9 and parts[9].isdigit() else 0
        clock_mem = int(parts[10]) if len(parts) > 10 and parts[10].isdigit() else 0
        return {
            "name": parts[0],
            "total_memory": total_mb * 1024 ** 2,
            "used_memory": used_mb * 1024 ** 2,
            "available_memory": free_mb * 1024 ** 2,
            "temperature": temperature,
            "utilization": utilization,
            "power_draw": int(power_draw),
            "power_limit": int(power_limit),
            "power_percent": int(power_draw / power_limit * 100) if power_limit > 0 else 0,
            "fan_speed": fan_speed,
            "clock_sm": clock_sm,
            "clock_mem": clock_mem,
            "memory_utilization": int(used_mb / total_mb * 100) if total_mb > 0 else 0
        }

    def _get_gpu_status_sync(self) -> Optional[Dict]:
        """同步获取GPU状态（用于定时保存历史数据）"""
        if not self._nvidia_smi_available:
            return None

        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu,power.draw,power.limit,fan.speed,clocks.sm,clocks.mem", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0 or not result.stdout.strip():
                return None

            gpus = []
            for line in result.stdout.strip().split('\n'):
                gpu_info = self._parse_gpu_line(line)
                if gpu_info:
                    gpus.append(gpu_info)

            if gpus:
                primary_gpu = gpus[0]
                return {
                    "status": "available",
                    "gpu_count": len(gpus),
                    "name": primary_gpu["name"],
                    "total_memory": primary_gpu["total_memory"],
                    "used_memory": primary_gpu["used_memory"],
                    "available_memory": primary_gpu["available_memory"],
                    "temperature": primary_gpu["temperature"],
                    "utilization": primary_gpu["utilization"],
                    "power_draw": primary_gpu["power_draw"],
                    "power_limit": primary_gpu["power_limit"],
                    "power_percent": primary_gpu["power_percent"],
                    "fan_speed": primary_gpu["fan_speed"],
                    "clock_sm": primary_gpu["clock_sm"],
                    "clock_mem": primary_gpu["clock_mem"],
                    "memory_utilization": primary_gpu["memory_utilization"],
                    "primary": primary_gpu,
                    "all_gpus": gpus
                }
            return None
        except Exception:
            return None
    
    def get_gpu_status(self) -> Optional[Dict]:
        """直接从缓存返回GPU状态"""
        if self._cache_valid():
            return self._status_cache
        return None
    
    def get_memory_usage(self) -> Optional[Dict[str, int]]:
        status = self.get_gpu_status()
        if status:
            return {
                "total": status["total_memory"],
                "used": status["used_memory"],
                "available": status["available_memory"]
            }
        return None
    
    def is_memory_available(self, required_bytes: int) -> bool:
        mem_info = self.get_memory_usage()
        if mem_info and mem_info.get("available", 0) >= required_bytes:
            return True
        return False
    
    def detect_fragmentation(self) -> float:
        status = self.get_gpu_status()
        if not status:
            return 0.0
        
        total = status["primary"]["total_memory"]
        used = status["primary"]["used_memory"]
        available = status["primary"]["available_memory"]
        
        fragmentation = (total - used - available) / total if total > 0 else 0.0
        self._fragmentation_history.append(fragmentation)
        if len(self._fragmentation_history) > 60:
            self._fragmentation_history = self._fragmentation_history[-60:]
        
        return fragmentation
    
    def get_average_fragmentation(self) -> float:
        if not self._fragmentation_history:
            return 0.0
        return sum(self._fragmentation_history) / len(self._fragmentation_history)
    
    def set_memory_strategy(self, strategy: str):
        valid_strategies = ["conservative", "balanced", "aggressive"]
        if strategy in valid_strategies:
            self._memory_strategy = strategy
    
    def get_memory_strategy(self) -> str:
        return self._memory_strategy
    
    def get_recommended_utilization(self) -> float:
        strategies = {
            "conservative": 0.80,
            "balanced": 0.90,
            "aggressive": 0.95
        }
        return strategies.get(self._memory_strategy, 0.90)
    
    async def optimize_memory(self, vllm_port: int = 8000) -> bool:
        if (datetime.now() - self._last_flush_time).total_seconds() < self._flush_interval:
            return False
        
        fragmentation = self.detect_fragmentation()
        avg_fragmentation = self.get_average_fragmentation()
        
        if fragmentation > 0.1 or avg_fragmentation > 0.05:
            await self._flush_vllm_cache(vllm_port)
            self._last_flush_time = datetime.now()
            return True
        
        return False
    
    async def _flush_vllm_cache(self, port: int):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"http://localhost:{port}/v1/cache/flush")
        except Exception:
            pass
    
    async def optimize_memory_for_model(self, required_memory: int, vllm_port: int = 8000) -> bool:
        mem_info = self.get_memory_usage()
        if not mem_info:
            return False
        
        available = mem_info.get("available", 0)
        if available >= required_memory:
            return True
        
        await self._flush_vllm_cache(vllm_port)
        await asyncio.sleep(2)
        
        self._status_cache = None
        self._status_cache_time = None
        mem_info = self.get_memory_usage()
        return mem_info and mem_info.get("available", 0) >= required_memory
    
    def get_memory_optimization_status(self) -> Dict:
        return {
            "strategy": self._memory_strategy,
            "fragmentation": self.detect_fragmentation(),
            "avg_fragmentation": self.get_average_fragmentation(),
            "recommended_utilization": self.get_recommended_utilization(),
            "last_flush": self._last_flush_time.isoformat(),
            "flush_interval": self._flush_interval
        }
    
    def set_redis_client(self, redis_client):
        self._redis_client = redis_client
    
    def _calculate_max_history_points(self, interval_seconds: int = 5) -> int:
        seconds_per_day = 24 * 60 * 60
        total_seconds = self._max_history_days * seconds_per_day
        return int(total_seconds / interval_seconds)
    
    def save_gpu_history(self, max_points: Optional[int] = None):
        if not self._history_enabled:
            return False

        if self._redis_client is None:
            return False

        try:
            status = self._get_gpu_status_sync()
            if not status:
                return False

            if max_points is None:
                max_points = self._calculate_max_history_points()
            
            timestamp = datetime.now().isoformat()
            history_entry = {
                "timestamp": timestamp,
                "utilization": status.get("utilization", 0),
                "temperature": status.get("temperature", 0),
                "power_draw": status.get("power_draw", 0),
                "power_percent": status.get("power_percent", 0),
                "memory_utilization": status.get("memory_utilization", 0),
                "used_memory": status.get("used_memory", 0),
                "available_memory": status.get("available_memory", 0),
                "total_memory": status.get("total_memory", 0)
            }
            
            self._redis_client.lpush("gpu:history", json.dumps(history_entry))
            self._redis_client.ltrim("gpu:history", 0, max_points - 1)
            
            ttl_30_days = 30 * 24 * 60 * 60
            self._redis_client.expire("gpu:history", ttl_30_days)
            
            summary_data = {
                "status": "available",
                "current": {
                    "name": status.get("name"),
                    "gpu_count": status.get("gpu_count"),
                    "utilization": status.get("utilization"),
                    "temperature": status.get("temperature"),
                    "power_draw": status.get("power_draw"),
                    "power_limit": status.get("power_limit"),
                    "power_percent": status.get("power_percent"),
                    "memory_utilization": status.get("memory_utilization"),
                    "used_memory": status.get("used_memory"),
                    "available_memory": status.get("available_memory"),
                    "total_memory": status.get("total_memory")
                }
            }
            ttl_1_hour = 60 * 60
            self._redis_client.set("gpu:summary", json.dumps(summary_data), ex=ttl_1_hour)
            
            if datetime.now() - self._last_history_cleanup >= self._history_cleanup_interval:
                self._clean_old_history()
                self._last_history_cleanup = datetime.now()
            
            return True
        except Exception:
            return False
    
    def _clean_old_history(self):
        try:
            history_data = self._redis_client.lrange("gpu:history", 0, -1)
            if not history_data:
                return
            
            cutoff_time = datetime.now() - timedelta(days=self._max_history_days)
            valid_entries = []
            
            for item in history_data:
                try:
                    entry = json.loads(item)
                    entry_time = datetime.fromisoformat(entry.get("timestamp", ""))
                    if entry_time >= cutoff_time:
                        valid_entries.append(item)
                except:
                    valid_entries.append(item)
            
            if len(valid_entries) < len(history_data):
                self._redis_client.delete("gpu:history")
                for entry in reversed(valid_entries):
                    self._redis_client.rpush("gpu:history", entry)
        except Exception:
            pass
    
    def set_history_enabled(self, enabled: bool):
        self._history_enabled = enabled
    
    def get_history_enabled(self) -> bool:
        return self._history_enabled
    
    def set_max_history_days(self, days: int):
        if days > 0:
            self._max_history_days = days
    
    def get_max_history_days(self) -> int:
        return self._max_history_days
    
    def get_gpu_history(self, count: int = 60, time_range: str = None) -> List[Dict]:
        if self._redis_client is None:
            return []
        
        try:
            max_counts = {
                'hour': 720,
                'day': 1000,
                'week': 1000,
                None: count
            }
            actual_count = min(count, max_counts.get(time_range, count))
            history_data = self._redis_client.lrange("gpu:history", 0, actual_count - 1)
            
            history = []
            for item in history_data:
                try:
                    history.append(json.loads(item))
                except:
                    pass
            return history[::-1]
        except Exception:
            return []
    
    def get_gpu_summary(self) -> Dict:
        if self._redis_client is not None:
            try:
                cached_summary = self._redis_client.get("gpu:summary")
                if cached_summary:
                    summary = json.loads(cached_summary)
                    summary["history"] = self.get_gpu_history(60)
                    return summary
            except Exception:
                pass
        
        status = self.get_gpu_status()
        history = self.get_gpu_history(60)
        
        if not status:
            return {
                "status": "unavailable",
                "current": None,
                "history": history
            }
        
        return {
            "status": "available",
            "current": {
                "name": status.get("name"),
                "gpu_count": status.get("gpu_count"),
                "utilization": status.get("utilization"),
                "temperature": status.get("temperature"),
                "power_draw": status.get("power_draw"),
                "power_limit": status.get("power_limit"),
                "power_percent": status.get("power_percent"),
                "memory_utilization": status.get("memory_utilization"),
                "used_memory": status.get("used_memory"),
                "available_memory": status.get("available_memory"),
                "total_memory": status.get("total_memory")
            },
            "history": history
        }
