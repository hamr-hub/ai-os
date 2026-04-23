from core.scheduler import Scheduler
from core.monitor import GPUMonitor
from core.sys_ctl import SystemController
from core.websocket_manager import WebSocketManager
from core.config_watcher import ConfigWatcher
from core.metrics import MetricsCollector
from core.prometheus_exporter import PrometheusExporter
from core.structured_logger import StructuredLogger
from core.redis_client import redis_client
from core.cache_service import cache_service
from core.cache_updater import CacheUpdater
from core.model_testing import ModelTestingFramework
from core.logger import setup_logger
from core.vllm_manager import (
    get_available_models as vllm_get_available_models,
    get_current_model_info as vllm_get_current_model_info,
    start_vllm_service,
    stop_vllm_service,
    restart_vllm_service,
    get_vllm_service_status,
    switch_vllm_model,
    switch_vllm_model_with_test,
    MODEL_BASE_PATH,
    VLLM_SERVICE_NAME,
    VLLM_DEFAULT_PORT
)
from core.llama_cpp_manager import (
    llama_cpp_manager,
    test_llama_cpp_model,
    scan_gguf_models,
)
import httpx
import os

config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
config_watcher = ConfigWatcher(config_path)
config = config_watcher.load_config() or {}
log_dir = config.get('settings', {}).get('logging', {}).get('log_dir', None)

logger = setup_logger(log_dir=log_dir)
structured_logger = StructuredLogger("ai_controller")

gpu_monitor = GPUMonitor()
sys_controller = SystemController()
scheduler = Scheduler(gpu_monitor, sys_controller)
ws_manager = WebSocketManager()
metrics = MetricsCollector()
prometheus = PrometheusExporter()
model_tester = ModelTestingFramework(scheduler, gpu_monitor)
cache_updater = CacheUpdater(gpu_monitor, scheduler)

VLLM_REQUEST_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
VLLM_STREAM_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=60.0, pool=60.0)
VLLM_CLIENT_LIMITS = httpx.Limits(max_connections=200, max_keepalive_connections=50)

_background_tasks = []


def _on_config_changed(new_config):
    structured_logger.info("Configuration updated", action="config_reload")
    scheduler.config = new_config
