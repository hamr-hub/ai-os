"""
============================================
deps.py - 依赖注入模块（全局单例管理）
============================================
作用：
- 创建和管理所有核心服务的单例实例
- 提供全局配置加载和初始化
- 定义跨模块共享的常量（如 HTTP 超时配置）
- 注册配置变更回调函数

初始化顺序：
1. 加载配置文件 (config.yaml)
2. 初始化日志系统
3. 创建各核心服务实例
4. 定义 HTTP 客户端超时和限制
5. 注册配置变更回调

所有其他模块都从此文件导入实例，确保全局唯一性。
============================================
"""

# 导入核心服务类
from core.scheduler import Scheduler                    # 模型调度器
from core.monitor import GPUMonitor, SystemMonitor      # GPU/系统监控
from core.sys_ctl import SystemController               # 系统服务控制
from core.websocket_manager import WebSocketManager     # WebSocket 连接管理
from core.config_watcher import ConfigWatcher           # 配置文件监听
from core.metrics import MetricsCollector               # 指标收集器
from core.prometheus_exporter import PrometheusExporter # Prometheus 指标导出
from core.structured_logger import StructuredLogger     # 结构化日志
from core.redis_client import redis_client              # Redis 客户端
from core.cache_service import cache_service            # 缓存服务
from core.cache_updater import CacheUpdater             # 缓存更新器
from core.model_testing import ModelTestingFramework    # 模型测试框架
from core.logger import setup_logger                    # 基础日志
from core.vllm_manager import (                         # vLLM 管理
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
import httpx
import os

# 确定配置文件路径（相对于此文件的上两级目录）
config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")

# 创建配置监听器并加载初始配置
config_watcher = ConfigWatcher(config_path)
config_ok, config = config_watcher.load_config_with_status()
if not config_ok:
    config = {}

# 从配置中获取日志目录
log_dir = config.get('settings', {}).get('logging', {}).get('log_dir', None)

# 初始化日志系统
logger = setup_logger(log_dir=log_dir)                  # 基础日志（用于启动阶段）
structured_logger = StructuredLogger("ai_controller")   # 结构化日志（JSON 格式）

# 创建核心服务实例（按依赖顺序）
gpu_monitor = GPUMonitor()                              # GPU 监控器（监控显存、利用率等）
system_monitor = SystemMonitor()                        # 系统监控器（CPU/内存/磁盘）
sys_controller = SystemController()                     # 系统服务控制器（systemd 管理）
scheduler = Scheduler(gpu_monitor, sys_controller)      # 模型调度器（依赖 GPU 监控和系统控制）
ws_manager = WebSocketManager()                         # WebSocket 管理器（实时状态推送）
metrics = MetricsCollector()                            # 指标收集器（请求统计、Token 统计）
prometheus = PrometheusExporter()                       # Prometheus 指标导出器
model_tester = ModelTestingFramework(scheduler, gpu_monitor)  # 模型测试框架
cache_updater = CacheUpdater(gpu_monitor, scheduler)    # 缓存更新器（定时刷新缓存）

from core.model_switch_orchestrator import ModelSwitchOrchestrator
model_switch_orchestrator = ModelSwitchOrchestrator(
    ws_manager=ws_manager,
    vllm_service_name=VLLM_SERVICE_NAME,
    vllm_port=VLLM_DEFAULT_PORT,
    model_base_path=MODEL_BASE_PATH,
)

# HTTP 客户端超时配置（用于代理请求到 vLLM）
VLLM_REQUEST_TIMEOUT = httpx.Timeout(60.0, connect=10.0)          # 普通请求：60 秒总超时，10 秒连接超时
VLLM_STREAM_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=60.0, pool=60.0)  # 流式请求：120 秒读取超时
VLLM_CLIENT_LIMITS = httpx.Limits(max_connections=200, max_keepalive_connections=50)  # 连接池限制

# 后台任务列表（用于优雅关闭时清理）
_background_tasks = []


def _on_config_changed(new_config):
    """
    配置变更回调函数：
    - 当 config.yaml 被修改时自动调用
    - 记录配置变更信息
    - 清除所有相关缓存
    - 更新调度器配置
    
    参数:
        new_config: 新的配置字典
    """
    new_config = new_config if isinstance(new_config, dict) else {}
    model_count = len(new_config.get('models', {}))
    structured_logger.info(f"Configuration updated, models={model_count}, keys={list(new_config.get('models', {}).keys())[:5]}", action="config_reload")
    cache_service.delete_pattern("ai_controller:cache:*")
    scheduler.set_config(new_config)
