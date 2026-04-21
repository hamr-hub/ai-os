import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from .cache_service import cache_service
from .redis_client import redis_client

logger = logging.getLogger(__name__)

class CacheUpdater:
    def __init__(self, gpu_monitor=None, scheduler=None):
        self.gpu_monitor = gpu_monitor
        self.scheduler = scheduler
        self._tasks = []
        self._running = False
        self._update_intervals = {
            'gpu_status': 3,
            'gpu_summary': 10,
            'model_status': 5,
            'queue_status': 3,
            'system_status': 10,
            'health': 5,
            'metrics': 10,
            'preload_status': 30,
            'models_list': 300,
            'images_info': 3600,
            'models_summary': 3
        }
    
    async def _update_gpu_status(self):
        try:
            if self.gpu_monitor:
                status = self.gpu_monitor.get_gpu_status()
                if status:
                    status["serverTime"] = datetime.now().isoformat()
                    cache_service.set("api:manage:gpu:status", status, ttl_seconds=10)
                    logger.debug("Updated GPU status cache")
        except Exception as e:
            logger.error(f"Error updating GPU status cache: {str(e)}")
    
    async def _update_gpu_summary(self):
        try:
            if self.gpu_monitor:
                summary = self.gpu_monitor.get_gpu_summary()
                cache_service.set("api:manage:gpu:summary", summary, ttl_seconds=30)
                logger.debug("Updated GPU summary cache")
        except Exception as e:
            logger.error(f"Error updating GPU summary cache: {str(e)}")
    
    async def _update_model_status(self):
        try:
            if self.scheduler:
                models = self.scheduler.get_available_models()
                status = {}
                for model in models:
                    status[model] = {
                        "running": self.scheduler.is_model_running(model),
                        "port": self.scheduler.get_model_port(model),
                        "service": self.scheduler.get_model_service(model),
                        "active_requests": self.scheduler.get_active_requests(model),
                        "preloaded": self.scheduler.is_model_preloaded(model),
                        "last_used": self.scheduler.get_model_last_used(model).isoformat() if self.scheduler.get_model_last_used(model) else None
                    }
                cache_service.set("api:manage:models:status", status, ttl_seconds=10)
                cache_service.set("api:v1:status", await self._build_v1_status(), ttl_seconds=10)
                logger.debug("Updated model status cache")
        except Exception as e:
            logger.error(f"Error updating model status cache: {str(e)}")
    
    async def _update_queue_status(self):
        try:
            if self.scheduler:
                models = self.scheduler.get_available_models()
                queue_info = {}
                for model in models:
                    queue_info[model] = {
                        "active_requests": self.scheduler.get_active_requests(model),
                        "concurrency_limit": self.scheduler.get_concurrency_limit(),
                        "can_accept": self.scheduler.can_accept_request(model)
                    }
                cache_service.set("api:manage:queue:status", queue_info, ttl_seconds=5)
                logger.debug("Updated queue status cache")
        except Exception as e:
            logger.error(f"Error updating queue status cache: {str(e)}")
    
    async def _update_system_status(self):
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=0.5)
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
            
            cache_service.set("api:manage:system:status", result, ttl_seconds=15)
            logger.debug("Updated system status cache")
        except Exception as e:
            logger.error(f"Error updating system status cache: {str(e)}")
    
    async def _update_health(self, metrics_collector):
        try:
            if self.gpu_monitor and metrics_collector:
                gpu_status = self.gpu_monitor.get_gpu_status()
                health_info = metrics_collector.get_comprehensive_health_score(gpu_status)
                
                result = {
                    "status": health_info["status"],
                    "timestamp": datetime.now().isoformat(),
                    "health_score": health_info["overall"],
                    "details": health_info
                }
                cache_service.set("api:health", result, ttl_seconds=10)
                
                detailed_result = {
                    "status": health_info["status"],
                    "timestamp": datetime.now().isoformat(),
                    "scores": health_info,
                    "gpu": gpu_status,
                    "metrics": metrics_collector.get_detailed_metrics()
                }
                cache_service.set("api:health:detailed", detailed_result, ttl_seconds=10)
                
                alert_reasons = metrics_collector.get_alert_reasons()
                alert_result = {
                    "should_alert": health_info["overall"] < 70,
                    "health_score": health_info["overall"],
                    "status": health_info["status"],
                    "alert_reasons": alert_reasons,
                    "timestamp": datetime.now().isoformat()
                }
                cache_service.set("api:manage:health:alert", alert_result, ttl_seconds=15)
                
                logger.debug("Updated health cache")
        except Exception as e:
            logger.error(f"Error updating health cache: {str(e)}")
    
    async def _update_metrics(self, metrics_collector):
        try:
            if metrics_collector:
                result = metrics_collector.get_metrics()
                cache_service.set("api:manage:metrics", result, ttl_seconds=15)
                logger.debug("Updated metrics cache")
        except Exception as e:
            logger.error(f"Error updating metrics cache: {str(e)}")
    
    async def _update_preload_status(self):
        try:
            if self.scheduler:
                preloaded = self.scheduler.get_preloaded_models()
                all_models = self.scheduler.get_available_models()
                preload_status = {}
                for model in all_models:
                    config = self.scheduler.get_model_config(model)
                    preload_status[model] = {
                        "preloaded": model in preloaded,
                        "running": self.scheduler.is_model_running(model),
                        "preload_config": config.get("preload", False) if config else False
                    }
                result = {"preloaded_models": preloaded, "all_models": all_models, "status": preload_status}
                cache_service.set("api:manage:preload:detailed", result, ttl_seconds=60)
                cache_service.set("api:manage:preload:status", {"preloaded_models": preloaded, "all_models": all_models}, ttl_seconds=60)
                logger.debug("Updated preload status cache")
        except Exception as e:
            logger.error(f"Error updating preload status cache: {str(e)}")
    
    async def _update_models_list(self):
        try:
            if self.scheduler:
                models = self.scheduler.get_available_models()
                result = {"object": "list", "data": [{"id": m, "object": "model", "created": 0, "owned_by": "local"} for m in models]}
                cache_service.set("api:v1:models", result, ttl_seconds=300)
                logger.debug("Updated models list cache")
        except Exception as e:
            logger.error(f"Error updating models list cache: {str(e)}")
    
    async def _update_models_summary(self):
        try:
            if self.scheduler:
                models = self.scheduler.get_available_models()
                summary = []
                for model in models:
                    config = self.scheduler.get_model_config(model)
                    summary.append({
                        "name": model,
                        "running": self.scheduler.is_model_running(model),
                        "preloaded": self.scheduler.is_model_preloaded(model),
                        "supports_images": self.scheduler.get_model_supports_images(model),
                        "description": config.get("description", "") if config else "",
                        "required_memory": config.get("required_memory", "") if config else "",
                        "port": self.scheduler.get_model_port(model)
                    })
                result = {
                    "models": summary,
                    "total": len(summary),
                    "running_model": self.scheduler.get_current_model_name()
                }
                cache_service.set("api:manage:models:summary", result, ttl_seconds=5)
                logger.debug("Updated models summary cache")
        except Exception as e:
            logger.error(f"Error updating models summary cache: {str(e)}")
    
    async def _build_v1_status(self) -> Dict[str, Any]:
        if not self.gpu_monitor or not self.scheduler:
            return {}
        
        gpu_status = self.gpu_monitor.get_gpu_status()
        models = self.scheduler.get_available_models()
        model_statuses = {}
        
        for model in models:
            model_statuses[model] = {
                "available": self.scheduler.is_model_available(model),
                "running": self.scheduler.is_model_running(model),
                "preloaded": self.scheduler.is_model_preloaded(model),
                "port": self.scheduler.get_model_port(model),
                "supports_images": self.scheduler.get_model_supports_images(model),
                "active_requests": self.scheduler.get_active_requests(model),
                "can_accept": self.scheduler.can_accept_request(model)
            }
        
        return {
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
                "concurrency_limit": self.scheduler.get_concurrency_limit()
            }
        }
    
    async def _run_periodic_task(self, task_func, interval_seconds: int, task_name: str):
        while self._running:
            try:
                await task_func()
            except Exception as e:
                logger.error(f"Error in periodic task {task_name}: {str(e)}")
            
            await asyncio.sleep(interval_seconds)
    
    async def _warmup_cache(self, metrics_collector=None):
        """缓存预热：启动时立即更新所有缓存"""
        logger.info("Warming up cache...")
        warmup_tasks = [
            self._update_gpu_status(),
            self._update_gpu_summary(),
            self._update_model_status(),
            self._update_queue_status(),
            self._update_system_status(),
            self._update_health(metrics_collector) if metrics_collector else asyncio.sleep(0),
            self._update_metrics(metrics_collector) if metrics_collector else asyncio.sleep(0),
            self._update_preload_status(),
            self._update_models_list(),
            self._update_models_summary(),
        ]
        await asyncio.gather(*warmup_tasks, return_exceptions=True)
        logger.info("Cache warmup completed")
    
    async def start(self, metrics_collector=None):
        if self._running:
            return
        
        self._running = True
        logger.info("Starting cache updater service")
        
        # 缓存预热
        await self._warmup_cache(metrics_collector)
        
        tasks = [
            ("gpu_status", self._update_gpu_status, self._update_intervals['gpu_status']),
            ("gpu_summary", self._update_gpu_summary, self._update_intervals['gpu_summary']),
            ("model_status", self._update_model_status, self._update_intervals['model_status']),
            ("queue_status", self._update_queue_status, self._update_intervals['queue_status']),
            ("system_status", self._update_system_status, self._update_intervals['system_status']),
            ("health", lambda: self._update_health(metrics_collector), self._update_intervals['health']),
            ("metrics", lambda: self._update_metrics(metrics_collector), self._update_intervals['metrics']),
            ("preload_status", self._update_preload_status, self._update_intervals['preload_status']),
            ("models_list", self._update_models_list, self._update_intervals['models_list']),
            ("models_summary", self._update_models_summary, self._update_intervals['models_summary']),
        ]
        
        for task_name, task_func, interval in tasks:
            task = asyncio.create_task(self._run_periodic_task(task_func, interval, task_name))
            self._tasks.append((task_name, task))
        
        logger.info("Cache updater service started")
    
    async def stop(self):
        self._running = False
        logger.info("Stopping cache updater service")
        
        for task_name, task in self._tasks:
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*[t[1] for t in self._tasks], return_exceptions=True)
        
        self._tasks.clear()
        logger.info("Cache updater service stopped")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "tasks_count": len(self._tasks),
            "update_intervals": self._update_intervals,
            "redis_connected": redis_client.is_connected(),
            "cache_stats": cache_service.get_stats()
        }