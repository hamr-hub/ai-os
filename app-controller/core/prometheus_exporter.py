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
        
        self.gpu_ecc_errors = Gauge(
            'ai_controller_gpu_ecc_errors_total',
            'GPU ECC error count',
            ['gpu_id'],
            registry=self.registry
        )
        
        self.gpu_pcie_throughput = Gauge(
            'ai_controller_gpu_pcie_throughput_kbps',
            'GPU PCIe throughput in KB/s',
            ['gpu_id', 'direction'],
            registry=self.registry
        )
        
        self.gpu_bar1_memory = Gauge(
            'ai_controller_gpu_bar1_memory_bytes',
            'GPU BAR1 memory',
            ['gpu_id', 'type'],
            registry=self.registry
        )
        
        self.gpu_throttle_status = Gauge(
            'ai_controller_gpu_throttle_status',
            'GPU throttle status (1=throttled, 0=not throttled)',
            ['gpu_id'],
            registry=self.registry
        )
        
        self.gpu_power_draw = Gauge(
            'ai_controller_gpu_power_draw_watts',
            'GPU power draw in watts',
            ['gpu_id'],
            registry=self.registry
        )
        
        self.gpu_fan_speed = Gauge(
            'ai_controller_gpu_fan_speed_percent',
            'GPU fan speed percentage',
            ['gpu_id'],
            registry=self.registry
        )
        
        self.gpu_clock_sm = Gauge(
            'ai_controller_gpu_clock_sm_mhz',
            'GPU SM clock speed in MHz',
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
        
        self.vllm_running_requests = Gauge(
            'ai_controller_vllm_running_requests',
            'Running requests in vLLM',
            registry=self.registry
        )
        
        self.vllm_waiting_requests = Gauge(
            'ai_controller_vllm_waiting_requests',
            'Waiting requests in vLLM',
            registry=self.registry
        )
        
        self.vllm_gpu_cache_usage = Gauge(
            'ai_controller_vllm_gpu_cache_usage_percent',
            'vLLM GPU KV cache usage percentage',
            registry=self.registry
        )
        
        self.vllm_cpu_cache_usage = Gauge(
            'ai_controller_vllm_cpu_cache_usage_percent',
            'vLLM CPU KV cache usage percentage',
            registry=self.registry
        )
        
        self.vllm_generation_throughput = Gauge(
            'ai_controller_vllm_generation_throughput_tokens_per_sec',
            'vLLM generation throughput in tokens/sec',
            registry=self.registry
        )
        
        self.vllm_prompt_throughput = Gauge(
            'ai_controller_vllm_prompt_throughput_tokens_per_sec',
            'vLLM prompt processing throughput in tokens/sec',
            registry=self.registry
        )
        
        self.vllm_time_to_first_token = Gauge(
            'ai_controller_vllm_time_to_first_token_seconds',
            'vLLM time to first token in seconds',
            registry=self.registry
        )
        
        self.vllm_time_per_output_token = Gauge(
            'ai_controller_vllm_time_per_output_token_seconds',
            'vLLM time per output token in seconds',
            registry=self.registry
        )
        
        self.vllm_iteration_tokens_total = Gauge(
            'ai_controller_vllm_iteration_tokens_total',
            'vLLM total iteration tokens',
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
        
        if gpu_status.get("primary"):
            primary = gpu_status["primary"]
            self.gpu_memory_total.labels(gpu_id="0").set(primary.get("total_memory", 0))
            self.gpu_memory_used.labels(gpu_id="0").set(primary.get("used_memory", 0))
            self.gpu_memory_available.labels(gpu_id="0").set(primary.get("available_memory", 0))
            self.gpu_temperature.labels(gpu_id="0").set(primary.get("temperature", 0))
            self.gpu_utilization.labels(gpu_id="0").set(primary.get("utilization", 0))
            self.gpu_power_draw.labels(gpu_id="0").set(primary.get("power_draw", 0))
            self.gpu_fan_speed.labels(gpu_id="0").set(primary.get("fan_speed", 0))
            self.gpu_clock_sm.labels(gpu_id="0").set(primary.get("clock_sm", 0))
            self.gpu_ecc_errors.labels(gpu_id="0").set(primary.get("ecc_errors", 0))
            self.gpu_pcie_throughput.labels(gpu_id="0", direction="rx").set(primary.get("pcie_rx_throughput", 0))
            self.gpu_pcie_throughput.labels(gpu_id="0", direction="tx").set(primary.get("pcie_tx_throughput", 0))
            self.gpu_bar1_memory.labels(gpu_id="0", type="total").set(primary.get("bar1_total_memory", 0))
            self.gpu_bar1_memory.labels(gpu_id="0", type="used").set(primary.get("bar1_used_memory", 0))
            throttle_reasons = primary.get("throttle_reasons", [])
            self.gpu_throttle_status.labels(gpu_id="0").set(1 if throttle_reasons else 0)
        
        for i, gpu in enumerate(gpu_status.get("all_gpus", [])):
            self.gpu_memory_total.labels(gpu_id=str(i)).set(gpu.get("total_memory", 0))
            self.gpu_memory_used.labels(gpu_id=str(i)).set(gpu.get("used_memory", 0))
            self.gpu_memory_available.labels(gpu_id=str(i)).set(gpu.get("available_memory", 0))
            self.gpu_temperature.labels(gpu_id=str(i)).set(gpu.get("temperature", 0))
            self.gpu_utilization.labels(gpu_id=str(i)).set(gpu.get("utilization", 0))
            self.gpu_power_draw.labels(gpu_id=str(i)).set(gpu.get("power_draw", 0))
            self.gpu_fan_speed.labels(gpu_id=str(i)).set(gpu.get("fan_speed", 0))
            self.gpu_clock_sm.labels(gpu_id=str(i)).set(gpu.get("clock_sm", 0))
            self.gpu_ecc_errors.labels(gpu_id=str(i)).set(gpu.get("ecc_errors", 0))
            self.gpu_pcie_throughput.labels(gpu_id=str(i), direction="rx").set(gpu.get("pcie_rx_throughput", 0))
            self.gpu_pcie_throughput.labels(gpu_id=str(i), direction="tx").set(gpu.get("pcie_tx_throughput", 0))
            self.gpu_bar1_memory.labels(gpu_id=str(i), type="total").set(gpu.get("bar1_total_memory", 0))
            self.gpu_bar1_memory.labels(gpu_id=str(i), type="used").set(gpu.get("bar1_used_memory", 0))
            throttle_reasons = gpu.get("throttle_reasons", [])
            self.gpu_throttle_status.labels(gpu_id=str(i)).set(1 if throttle_reasons else 0)
    
    def update_vllm_metrics(self, vllm_metrics: Dict):
        if not vllm_metrics:
            return
        self.vllm_running_requests.set(vllm_metrics.get("running_requests", 0))
        self.vllm_waiting_requests.set(vllm_metrics.get("waiting_requests", 0))
        self.vllm_gpu_cache_usage.set(vllm_metrics.get("gpu_cache_usage", 0))
        self.vllm_cpu_cache_usage.set(vllm_metrics.get("cpu_cache_usage", 0))
        self.vllm_generation_throughput.set(vllm_metrics.get("generation_throughput", 0))
        self.vllm_prompt_throughput.set(vllm_metrics.get("prompt_throughput", 0))
        self.vllm_time_to_first_token.set(vllm_metrics.get("time_to_first_token", 0))
        self.vllm_time_per_output_token.set(vllm_metrics.get("time_per_output_token", 0))
        self.vllm_iteration_tokens_total.set(vllm_metrics.get("iteration_tokens_total", 0))
    
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
            'requests_total': {'type': 'counter', 'help': 'Total number of requests'},
            'request_duration_seconds': {'type': 'histogram', 'help': 'Request duration in seconds'},
            'active_requests': {'type': 'gauge', 'help': 'Number of active requests'},
            'gpu_memory_total_bytes': {'type': 'gauge', 'help': 'Total GPU memory'},
            'gpu_memory_used_bytes': {'type': 'gauge', 'help': 'Used GPU memory'},
            'gpu_memory_available_bytes': {'type': 'gauge', 'help': 'Available GPU memory'},
            'gpu_temperature_celsius': {'type': 'gauge', 'help': 'GPU temperature in Celsius'},
            'gpu_utilization_percent': {'type': 'gauge', 'help': 'GPU utilization percentage'},
            'gpu_ecc_errors_total': {'type': 'gauge', 'help': 'GPU ECC error count'},
            'gpu_pcie_throughput_kbps': {'type': 'gauge', 'help': 'GPU PCIe throughput in KB/s'},
            'gpu_bar1_memory_bytes': {'type': 'gauge', 'help': 'GPU BAR1 memory'},
            'gpu_throttle_status': {'type': 'gauge', 'help': 'GPU throttle status'},
            'gpu_power_draw_watts': {'type': 'gauge', 'help': 'GPU power draw in watts'},
            'gpu_fan_speed_percent': {'type': 'gauge', 'help': 'GPU fan speed percentage'},
            'gpu_clock_sm_mhz': {'type': 'gauge', 'help': 'GPU SM clock speed in MHz'},
            'model_status': {'type': 'gauge', 'help': 'Model status (1=running, 0=stopped)'},
            'model_requests_total': {'type': 'counter', 'help': 'Total requests per model'},
            'queue_length': {'type': 'gauge', 'help': 'Queue length per model'},
            'service_uptime_seconds': {'type': 'gauge', 'help': 'Service uptime in seconds'},
            'health_score': {'type': 'gauge', 'help': 'Overall health score (0-100)'},
            'vllm_running_requests': {'type': 'gauge', 'help': 'Running requests in vLLM'},
            'vllm_waiting_requests': {'type': 'gauge', 'help': 'Waiting requests in vLLM'},
            'vllm_gpu_cache_usage_percent': {'type': 'gauge', 'help': 'vLLM GPU KV cache usage'},
            'vllm_cpu_cache_usage_percent': {'type': 'gauge', 'help': 'vLLM CPU KV cache usage'},
            'vllm_generation_throughput': {'type': 'gauge', 'help': 'vLLM generation throughput tokens/s'},
            'vllm_prompt_throughput': {'type': 'gauge', 'help': 'vLLM prompt throughput tokens/s'},
            'vllm_time_to_first_token_seconds': {'type': 'gauge', 'help': 'vLLM TTFT in seconds'},
            'vllm_time_per_output_token_seconds': {'type': 'gauge', 'help': 'vLLM TPOT in seconds'},
            'vllm_iteration_tokens_total': {'type': 'gauge', 'help': 'vLLM total iteration tokens'},
        }
