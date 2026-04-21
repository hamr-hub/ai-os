from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
from core.logger import setup_logger
from core.redis_client import redis_client

logger = setup_logger()

class MetricsCollector:
    def __init__(self):
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.response_times: List[float] = []
        self.model_requests: Dict[str, int] = defaultdict(int)
        self.start_time = datetime.now()
        self.gpu_status_history: List[Dict] = []
        self.queue_length_history: List[int] = []
        self.redis_prefix = "ai_controller:metrics:"
        
        self.image_request_counts: Dict[str, int] = defaultdict(int)
        self.image_request_sizes: List[int] = []
        self.image_response_times: List[float] = []
        self.image_error_counts: Dict[str, int] = defaultdict(int)
        
        self._load_from_redis()
    
    def _get_key(self, name: str) -> str:
        return f"{self.redis_prefix}{name}"
    
    def _load_from_redis(self):
        if not redis_client.is_connected():
            return
        
        try:
            request_counts_key = self._get_key("request_counts")
            data = redis_client.get_json(request_counts_key)
            if data:
                self.request_counts = defaultdict(int, data)
            
            error_counts_key = self._get_key("error_counts")
            data = redis_client.get_json(error_counts_key)
            if data:
                self.error_counts = defaultdict(int, data)
            
            model_requests_key = self._get_key("model_requests")
            data = redis_client.get_json(model_requests_key)
            if data:
                self.model_requests = defaultdict(int, data)
            
            response_times_key = self._get_key("response_times")
            data = redis_client.get_json(response_times_key)
            if data:
                self.response_times = data
            
            start_time_key = self._get_key("start_time")
            data = redis_client.get(start_time_key)
            if data:
                try:
                    self.start_time = datetime.fromisoformat(data)
                except:
                    pass
            
            image_request_counts_key = self._get_key("image_request_counts")
            data = redis_client.get_json(image_request_counts_key)
            if data:
                self.image_request_counts = defaultdict(int, data)
            
            image_request_sizes_key = self._get_key("image_request_sizes")
            data = redis_client.get_json(image_request_sizes_key)
            if data:
                self.image_request_sizes = data
            
            image_response_times_key = self._get_key("image_response_times")
            data = redis_client.get_json(image_response_times_key)
            if data:
                self.image_response_times = data
            
            image_error_counts_key = self._get_key("image_error_counts")
            data = redis_client.get_json(image_error_counts_key)
            if data:
                self.image_error_counts = defaultdict(int, data)
        except Exception as e:
            logger.error(f"Failed to load metrics from Redis: {e}")
    
    def _save_to_redis(self):
        if not redis_client.is_connected():
            return
        
        try:
            request_counts_key = self._get_key("request_counts")
            redis_client.set_json(request_counts_key, dict(self.request_counts))
            
            error_counts_key = self._get_key("error_counts")
            redis_client.set_json(error_counts_key, dict(self.error_counts))
            
            model_requests_key = self._get_key("model_requests")
            redis_client.set_json(model_requests_key, dict(self.model_requests))
            
            response_times_key = self._get_key("response_times")
            redis_client.set_json(response_times_key, self.response_times)
            
            start_time_key = self._get_key("start_time")
            redis_client.set(start_time_key, self.start_time.isoformat())
            
            image_request_counts_key = self._get_key("image_request_counts")
            redis_client.set_json(image_request_counts_key, dict(self.image_request_counts))
            
            image_request_sizes_key = self._get_key("image_request_sizes")
            redis_client.set_json(image_request_sizes_key, self.image_request_sizes)
            
            image_response_times_key = self._get_key("image_response_times")
            redis_client.set_json(image_response_times_key, self.image_response_times)
            
            image_error_counts_key = self._get_key("image_error_counts")
            redis_client.set_json(image_error_counts_key, dict(self.image_error_counts))
        except Exception as e:
            logger.error(f"Failed to save metrics to Redis: {e}")
    
    def record_request(self, endpoint: str, status_code: int, response_time: float, model_name: Optional[str] = None, is_image_request: bool = False, image_size_bytes: int = 0):
        self.request_counts[endpoint] += 1
        
        if status_code >= 400:
            self.error_counts[endpoint] += 1
        
        self.response_times.append(response_time)
        if len(self.response_times) > 1000:
            self.response_times = self.response_times[-1000:]
        
        if model_name:
            self.model_requests[model_name] += 1
        
        if is_image_request:
            self.record_image_request(endpoint, status_code, response_time, image_size_bytes)
        
        self._save_to_redis()
    
    def record_image_request(self, endpoint: str, status_code: int, response_time: float, image_size_bytes: int = 0):
        self.image_request_counts[endpoint] += 1
        self.image_response_times.append(response_time)
        if image_size_bytes > 0:
            self.image_request_sizes.append(image_size_bytes)
        
        if len(self.image_response_times) > 500:
            self.image_response_times = self.image_response_times[-500:]
        
        if len(self.image_request_sizes) > 500:
            self.image_request_sizes = self.image_request_sizes[-500:]
        
        if status_code >= 400:
            self.image_error_counts[endpoint] += 1
    
    def record_gpu_status(self, gpu_status: Dict):
        self.gpu_status_history.append({
            "timestamp": datetime.now().isoformat(),
            **gpu_status
        })
        if len(self.gpu_status_history) > 60:
            self.gpu_status_history = self.gpu_status_history[-60:]
        
        gpu_history_key = self._get_key("gpu_history")
        redis_client.set_json(gpu_history_key, self.gpu_status_history)
    
    def record_queue_length(self, length: int):
        self.queue_length_history.append(length)
        if len(self.queue_length_history) > 60:
            self.queue_length_history = self.queue_length_history[-60:]
        
        queue_history_key = self._get_key("queue_history")
        redis_client.set_json(queue_history_key, self.queue_length_history)
    
    def get_metrics(self) -> Dict:
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        max_response_time = max(self.response_times) if self.response_times else 0
        min_response_time = min(self.response_times) if self.response_times else 0
        
        avg_image_response_time = sum(self.image_response_times) / len(self.image_response_times) if self.image_response_times else 0
        max_image_response_time = max(self.image_response_times) if self.image_response_times else 0
        min_image_response_time = min(self.image_response_times) if self.image_response_times else 0
        avg_image_size_bytes = sum(self.image_request_sizes) / len(self.image_request_sizes) if self.image_request_sizes else 0
        max_image_size_bytes = max(self.image_request_sizes) if self.image_request_sizes else 0
        
        uptime = datetime.now() - self.start_time
        
        avg_queue_length = sum(self.queue_length_history) / len(self.queue_length_history) if self.queue_length_history else 0
        max_queue_length = max(self.queue_length_history) if self.queue_length_history else 0
        
        return {
            "uptime": str(uptime),
            "total_requests": sum(self.request_counts.values()),
            "total_errors": sum(self.error_counts.values()),
            "request_counts": dict(self.request_counts),
            "error_counts": dict(self.error_counts),
            "response_time": {
                "average": round(avg_response_time, 2),
                "max": round(max_response_time, 2),
                "min": round(min_response_time, 2),
                "count": len(self.response_times)
            },
            "model_requests": dict(self.model_requests),
            "image_requests": {
                "total": sum(self.image_request_counts.values()),
                "total_errors": sum(self.image_error_counts.values()),
                "request_counts": dict(self.image_request_counts),
                "error_counts": dict(self.image_error_counts),
                "response_time": {
                    "average": round(avg_image_response_time, 2),
                    "max": round(max_image_response_time, 2),
                    "min": round(min_image_response_time, 2),
                    "count": len(self.image_response_times)
                },
                "size": {
                    "average_bytes": round(avg_image_size_bytes, 2),
                    "average_mb": round(avg_image_size_bytes / (1024 * 1024), 2),
                    "max_bytes": max_image_size_bytes,
                    "max_mb": round(max_image_size_bytes / (1024 * 1024), 2),
                    "count": len(self.image_request_sizes)
                }
            },
            "queue": {
                "average_length": round(avg_queue_length, 2),
                "max_length": max_queue_length,
                "history_length": len(self.queue_length_history)
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def get_detailed_metrics(self) -> Dict:
        metrics = self.get_metrics()
        metrics["gpu_history"] = self.gpu_status_history
        return metrics
    
    def reset(self):
        self.request_counts.clear()
        self.error_counts.clear()
        self.response_times.clear()
        self.model_requests.clear()
        self.start_time = datetime.now()
        self.gpu_status_history.clear()
        self.queue_length_history.clear()
        
        self.image_request_counts.clear()
        self.image_request_sizes.clear()
        self.image_response_times.clear()
        self.image_error_counts.clear()
        
        if redis_client.is_connected():
            try:
                pattern = f"{self.redis_prefix}*"
                keys = redis_client.keys(pattern)
                for key in keys:
                    redis_client.delete(key)
            except Exception as e:
                logger.error(f"Failed to reset metrics in Redis: {e}")
    
    def get_health_score(self) -> float:
        total = sum(self.request_counts.values())
        errors = sum(self.error_counts.values())
        
        if total == 0:
            return 100.0
        
        error_rate = errors / total
        score = max(0, 100 - (error_rate * 100))
        return round(score, 2)
    
    def get_comprehensive_health_score(self, gpu_status: Optional[Dict] = None) -> Dict:
        scores = {}
        
        total = sum(self.request_counts.values())
        errors = sum(self.error_counts.values())
        
        if total > 0:
            error_rate = errors / total
            service_score = max(0, 100 - (error_rate * 100))
        else:
            service_score = 100.0
        
        scores["service"] = round(service_score, 2)
        
        if gpu_status and gpu_status.get("status") == "available":
            primary = gpu_status.get("primary", {})
            temp = primary.get("temperature", 0)
            total_mem = primary.get("total_memory", 1)
            used_mem = primary.get("used_memory", 0)
            
            temp_score = min(100, max(0, 100 - (temp - 85) * 2))
            mem_score = min(100, max(0, 100 - ((used_mem / total_mem) - 0.9) * 1000))
            
            scores["gpu_temperature"] = round(temp_score, 2)
            scores["gpu_memory"] = round(mem_score, 2)
            scores["gpu_overall"] = round((temp_score * 0.5 + mem_score * 0.5), 2)
        else:
            scores["gpu_temperature"] = 0.0
            scores["gpu_memory"] = 0.0
            scores["gpu_overall"] = 0.0
        
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        response_score = min(100, max(0, 100 - avg_response_time * 10))
        scores["response_time"] = round(response_score, 2)
        
        weights = {
            "service": 0.4,
            "gpu_overall": 0.3,
            "response_time": 0.3
        }
        
        overall_score = sum(scores.get(k, 0) * v for k, v in weights.items())
        scores["overall"] = round(overall_score, 2)
        
        scores["status"] = self._get_health_status(overall_score)
        
        return scores
    
    def _get_health_status(self, score: float) -> str:
        if score >= 90:
            return "healthy"
        elif score >= 70:
            return "degraded"
        elif score >= 50:
            return "warning"
        else:
            return "critical"
    
    def should_alert(self, threshold: float = 70) -> bool:
        score = self.get_health_score()
        return score < threshold
    
    def get_alert_reasons(self, gpu_status: Optional[Dict] = None) -> List[str]:
        reasons = []
        
        total = sum(self.request_counts.values())
        errors = sum(self.error_counts.values())
        
        if total > 0:
            error_rate = errors / total
            if error_rate > 0.1:
                reasons.append(f"高错误率: {error_rate:.2%}")
        
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        if avg_response_time > 5:
            reasons.append(f"响应时间过长: {avg_response_time:.2f}s")
        
        if gpu_status and gpu_status.get("status") == "available":
            primary = gpu_status.get("primary", {})
            temp = primary.get("temperature", 0)
            total_mem = primary.get("total_memory", 1)
            used_mem = primary.get("used_memory", 0)
            mem_util = primary.get("memory_utilization", 0)
            power_draw = primary.get("power_draw", 0)
            power_limit = primary.get("power_limit", 1)
            
            if temp > 90:
                reasons.append(f"GPU温度过高: {temp}°C")
            elif temp > 85:
                reasons.append(f"GPU温度偏高: {temp}°C")
            
            if mem_util > 95:
                reasons.append(f"显存使用率过高: {mem_util}%")
            elif mem_util > 90:
                reasons.append(f"显存使用率偏高: {mem_util}%")
            
            if used_mem > 0.95 * total_mem:
                reasons.append(f"显存接近满载")
            
            power_percent = (power_draw / power_limit) * 100 if power_limit > 0 else 0
            if power_percent > 90:
                reasons.append(f"GPU功耗过高: {power_draw}W/{power_limit}W ({power_percent:.0f}%)")
        
        return reasons
    
    def check_gpu_alerts(self, gpu_status: Dict) -> Dict[str, Dict]:
        """检查GPU告警阈值"""
        alerts = {
            "temperature": {
                "status": "ok",
                "value": 0,
                "threshold": 85,
                "critical_threshold": 95,
                "message": ""
            },
            "memory": {
                "status": "ok",
                "value": 0,
                "threshold": 90,
                "critical_threshold": 95,
                "message": ""
            },
            "power": {
                "status": "ok",
                "value": 0,
                "threshold": 85,
                "critical_threshold": 95,
                "message": ""
            },
            "utilization": {
                "status": "ok",
                "value": 0,
                "threshold": 95,
                "critical_threshold": 100,
                "message": ""
            }
        }
        
        if not gpu_status or gpu_status.get("status") != "available":
            for key in alerts:
                alerts[key]["status"] = "unavailable"
                alerts[key]["message"] = "GPU不可用"
            return alerts
        
        primary = gpu_status.get("primary", {})
        
        temp = primary.get("temperature", 0)
        alerts["temperature"]["value"] = temp
        if temp >= 95:
            alerts["temperature"]["status"] = "critical"
            alerts["temperature"]["message"] = f"GPU温度严重过高: {temp}°C"
        elif temp >= 85:
            alerts["temperature"]["status"] = "warning"
            alerts["temperature"]["message"] = f"GPU温度偏高: {temp}°C"
        
        mem_util = primary.get("memory_utilization", 0)
        alerts["memory"]["value"] = mem_util
        if mem_util >= 95:
            alerts["memory"]["status"] = "critical"
            alerts["memory"]["message"] = f"显存使用率严重过高: {mem_util}%"
        elif mem_util >= 90:
            alerts["memory"]["status"] = "warning"
            alerts["memory"]["message"] = f"显存使用率偏高: {mem_util}%"
        
        power_limit = primary.get("power_limit", 1)
        power_draw = primary.get("power_draw", 0)
        power_percent = (power_draw / power_limit) * 100 if power_limit > 0 else 0
        alerts["power"]["value"] = round(power_percent, 1)
        if power_percent >= 95:
            alerts["power"]["status"] = "critical"
            alerts["power"]["message"] = f"GPU功耗严重过高: {power_draw}W"
        elif power_percent >= 85:
            alerts["power"]["status"] = "warning"
            alerts["power"]["message"] = f"GPU功耗偏高: {power_draw}W"
        
        util = primary.get("utilization", 0)
        alerts["utilization"]["value"] = util
        if util >= 100:
            alerts["utilization"]["status"] = "critical"
            alerts["utilization"]["message"] = "GPU使用率达到100%"
        elif util >= 95:
            alerts["utilization"]["status"] = "warning"
            alerts["utilization"]["message"] = f"GPU使用率偏高: {util}%"
        
        return alerts
    
    def get_overall_alert_status(self, gpu_status: Optional[Dict] = None) -> Dict:
        """获取整体告警状态"""
        gpu_alerts = self.check_gpu_alerts(gpu_status) if gpu_status else {}
        alert_reasons = self.get_alert_reasons(gpu_status)
        
        has_critical = any(
            alert.get("status") == "critical" 
            for alert in gpu_alerts.values()
        ) or len([r for r in alert_reasons if "严重" in r]) > 0
        
        has_warning = any(
            alert.get("status") == "warning" 
            for alert in gpu_alerts.values()
        ) or len(alert_reasons) > 0
        
        status = "ok"
        if has_critical:
            status = "critical"
        elif has_warning:
            status = "warning"
        
        return {
            "status": status,
            "gpu_alerts": gpu_alerts,
            "service_alerts": alert_reasons,
            "has_critical": has_critical,
            "has_warning": has_warning,
            "timestamp": datetime.now().isoformat()
        }