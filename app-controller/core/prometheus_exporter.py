from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
    CONTENT_TYPE_LATEST
)
from fastapi import Response
from datetime import datetime
from typing import Dict, Optional

class PrometheusExporter:
    def __init__(self):
        self.registry = CollectorRegistry()
        
        self.request_counter = Counter(
            'ai_controller_requests_total',
            'Total number of requests',
            ['endpoint', 'method', 'status_code', 'model'],
            registry=self.registry
        )
        
        self.request_duration = Histogram(
            'ai_controller_request_duration_seconds',
            'Request duration in seconds',
            ['endpoint', 'model'],
            registry=self.registry,
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )
        
        self.active_requests = Gauge(
            'ai_controller_active_requests',
            'Number of active requests',
            ['model'],
            registry=self.registry
        )
        
        self.gpu_memory_total = Gauge(
            'ai_controller_gpu_memory_total_bytes',
            'Total GPU memory',
            ['gpu_id'],
            registry=self.registry
        )
        
        self.gpu_memory_used = Gauge(
            'ai_controller_gpu_memory_used_bytes',
            'Used GPU memory',
            ['gpu_id'],
            registry=self.registry
        )
        
        self.gpu_memory_available = Gauge(
            'ai_controller_gpu_memory_available_bytes',
            'Available GPU memory',
            ['gpu_id'],
            registry=self.registry
        )
        
        self.gpu_temperature = Gauge(
            'ai_controller_gpu_temperature_celsius',
            'GPU temperature in Celsius',
            ['gpu_id'],
            registry=self.registry
        )
        
        self.gpu_utilization = Gauge(
            'ai_controller_gpu_utilization_percent',
            'GPU utilization percentage',
            ['gpu_id'],
            registry=self.registry
        )
        
        self.model_status = Gauge(
            'ai_controller_model_status',
            'Model status (1=running, 0=stopped)',
            ['model', 'service'],
            registry=self.registry
        )
        
        self.model_requests_total = Counter(
            'ai_controller_model_requests_total',
            'Total requests per model',
            ['model'],
            registry=self.registry
        )
        
        self.queue_length = Gauge(
            'ai_controller_queue_length',
            'Queue length per model',
            ['model'],
            registry=self.registry
        )
        
        self.service_uptime = Gauge(
            'ai_controller_service_uptime_seconds',
            'Service uptime in seconds',
            registry=self.registry
        )
        
        self.health_score = Gauge(
            'ai_controller_health_score',
            'Overall health score (0-100)',
            registry=self.registry
        )
        
        self.start_time = datetime.now()
    
    def record_request(self, endpoint: str, method: str, status_code: int, 
                       duration: float, model: Optional[str] = None):
        self.request_counter.labels(
            endpoint=endpoint,
            method=method,
            status_code=str(status_code),
            model=model or "unknown"
        ).inc()
        
        self.request_duration.labels(
            endpoint=endpoint,
            model=model or "unknown"
        ).observe(duration)
    
    def set_active_requests(self, model: str, count: int):
        self.active_requests.labels(model=model).set(count)
    
    def update_gpu_metrics(self, gpu_status: Dict):
        if not gpu_status or gpu_status.get("status") != "available":
            return
        
        gpu_count = gpu_status.get("gpu_count", 0)
        
        if gpu_status.get("primary"):
            primary = gpu_status["primary"]
            self.gpu_memory_total.labels(gpu_id="0").set(primary.get("total_memory", 0))
            self.gpu_memory_used.labels(gpu_id="0").set(primary.get("used_memory", 0))
            self.gpu_memory_available.labels(gpu_id="0").set(primary.get("available_memory", 0))
            self.gpu_temperature.labels(gpu_id="0").set(primary.get("temperature", 0))
            self.gpu_utilization.labels(gpu_id="0").set(primary.get("utilization", 0))
        
        for i, gpu in enumerate(gpu_status.get("all_gpus", [])):
            self.gpu_memory_total.labels(gpu_id=str(i)).set(gpu.get("total_memory", 0))
            self.gpu_memory_used.labels(gpu_id=str(i)).set(gpu.get("used_memory", 0))
            self.gpu_memory_available.labels(gpu_id=str(i)).set(gpu.get("available_memory", 0))
            self.gpu_temperature.labels(gpu_id=str(i)).set(gpu.get("temperature", 0))
            self.gpu_utilization.labels(gpu_id=str(i)).set(gpu.get("utilization", 0))
    
    def set_model_status(self, model: str, service: str, running: bool):
        self.model_status.labels(model=model, service=service).set(1 if running else 0)
    
    def record_model_request(self, model: str):
        self.model_requests_total.labels(model=model).inc()
    
    def set_queue_length(self, model: str, length: int):
        self.queue_length.labels(model=model).set(length)
    
    def update_uptime(self):
        uptime = (datetime.now() - self.start_time).total_seconds()
        self.service_uptime.set(uptime)
    
    def set_health_score(self, score: float):
        self.health_score.set(score)
    
    def generate_metrics(self) -> Response:
        self.update_uptime()
        return Response(
            content=generate_latest(self.registry),
            media_type=CONTENT_TYPE_LATEST
        )
    
    def get_metrics_dict(self) -> Dict:
        self.update_uptime()
        return {
            'requests_total': {
                'type': 'counter',
                'help': 'Total number of requests'
            },
            'request_duration_seconds': {
                'type': 'histogram',
                'help': 'Request duration in seconds'
            },
            'active_requests': {
                'type': 'gauge',
                'help': 'Number of active requests'
            },
            'gpu_memory_total_bytes': {
                'type': 'gauge',
                'help': 'Total GPU memory'
            },
            'gpu_memory_used_bytes': {
                'type': 'gauge',
                'help': 'Used GPU memory'
            },
            'gpu_memory_available_bytes': {
                'type': 'gauge',
                'help': 'Available GPU memory'
            },
            'gpu_temperature_celsius': {
                'type': 'gauge',
                'help': 'GPU temperature in Celsius'
            },
            'gpu_utilization_percent': {
                'type': 'gauge',
                'help': 'GPU utilization percentage'
            },
            'model_status': {
                'type': 'gauge',
                'help': 'Model status (1=running, 0=stopped)'
            },
            'model_requests_total': {
                'type': 'counter',
                'help': 'Total requests per model'
            },
            'queue_length': {
                'type': 'gauge',
                'help': 'Queue length per model'
            },
            'service_uptime_seconds': {
                'type': 'gauge',
                'help': 'Service uptime in seconds'
            },
            'health_score': {
                'type': 'gauge',
                'help': 'Overall health score (0-100)'
            }
        }