import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from core.scheduler import Scheduler, _parse_memory_size
from core.monitor import GPUMonitor
from core.sys_ctl import SystemController

class TestMemoryParsing:
    def test_parse_memory_bytes(self):
        assert _parse_memory_size("1024") == 1024
        assert _parse_memory_size("0") == 0
        assert _parse_memory_size("1000000") == 1000000

    def test_parse_memory_kb(self):
        assert _parse_memory_size("1KB") == 1024
        assert _parse_memory_size("1024KB") == 1024 * 1024

    def test_parse_memory_mb(self):
        assert _parse_memory_size("1MB") == 1024 ** 2
        assert _parse_memory_size("1024MB") == 1024 ** 3

    def test_parse_memory_gb(self):
        assert _parse_memory_size("1GB") == 1024 ** 3
        assert _parse_memory_size("12GB") == 12 * 1024 ** 3

    def test_parse_memory_tb(self):
        assert _parse_memory_size("1TB") == 1024 ** 4

    def test_parse_memory_case_insensitive(self):
        assert _parse_memory_size("1gb") == 1024 ** 3
        assert _parse_memory_size("1Gb") == 1024 ** 3

    def test_parse_memory_with_spaces(self):
        assert _parse_memory_size(" 12 GB ") == 12 * 1024 ** 3

    def test_parse_memory_invalid(self):
        assert _parse_memory_size("invalid") == 0
        assert _parse_memory_size("") == 0

class TestScheduler:
    @pytest.fixture
    def mock_gpu_monitor(self):
        monitor = Mock(spec=GPUMonitor)
        monitor.get_memory_usage.return_value = {
            "total": 24 * 1024 ** 3,
            "used": 5 * 1024 ** 3,
            "available": 19 * 1024 ** 3
        }
        return monitor

    @pytest.fixture
    def mock_sys_controller(self):
        controller = Mock(spec=SystemController)
        controller.is_service_running.return_value = False
        controller.start_service.return_value = True
        controller.stop_service.return_value = True
        return controller

    @pytest.fixture
    def scheduler(self, mock_gpu_monitor, mock_sys_controller):
        scheduler = Scheduler(mock_gpu_monitor, mock_sys_controller)
        scheduler.config = {
            "models": {
                "gemma-4-31b": {
                    "service": "vllm-gemma",
                    "port": 8000,
                    "required_memory": "12GB",
                    "preload": False,
                    "keep_alive": True
                },
                "llama-3-8b": {
                    "service": "vllm-llama",
                    "port": 8001,
                    "required_memory": "10GB",
                    "preload": False,
                    "keep_alive": True
                },
                "Gemma-4-31B-Abliterated": {
                    "service": "vllm",
                    "port": 8000,
                    "required_memory": "40GB",
                    "preload": True,
                    "keep_alive": True,
                    "model_path": "/mnt/pve_models/Gemma-4-31B-Abliterated"
                }
            },
            "settings": {
                "concurrency_limit": 4,
                "min_available_memory": "2GB",
                "preload_timeout": 120,
                "idle_timeout": 300,
                "memory_cleanup_delay": 3,
                "gpu_memory_utilization": 0.9
            }
        }
        scheduler.preloaded_models = set()
        return scheduler

    def test_get_available_models(self, scheduler):
        models = scheduler.get_available_models()
        assert isinstance(models, list)
        assert len(models) > 0
        assert "gemma-4-31b" in models
        assert "llama-3-8b" in models

    def test_is_model_available(self, scheduler):
        assert scheduler.is_model_available("gemma-4-31b") is True
        assert scheduler.is_model_available("llama-3-8b") is True
        assert scheduler.is_model_available("unknown-model") is False

    def test_get_model_config(self, scheduler):
        config = scheduler.get_model_config("gemma-4-31b")
        assert config is not None
        assert config.get("service") == "vllm-gemma"
        assert config.get("port") == 8000

    def test_get_model_service(self, scheduler):
        assert scheduler.get_model_service("gemma-4-31b") == "vllm-gemma"
        assert scheduler.get_model_service("llama-3-8b") == "vllm-llama"
        assert scheduler.get_model_service("unknown") is None

    def test_get_model_port(self, scheduler):
        assert scheduler.get_model_port("gemma-4-31b") == 8000
        assert scheduler.get_model_port("llama-3-8b") == 8001
        assert scheduler.get_model_port("unknown") is None

    def test_is_model_running(self, scheduler, mock_sys_controller):
        mock_sys_controller.get_process_info.return_value = {"pid": 1234}
        scheduler.running_models.clear()
        assert scheduler.is_model_running("gemma-4-31b") is True
        
        mock_sys_controller.get_process_info.return_value = None
        scheduler.running_models.clear()
        assert scheduler.is_model_running("gemma-4-31b") is False

    @pytest.mark.asyncio
    async def test_start_model_success(self, scheduler, mock_sys_controller, mock_gpu_monitor):
        mock_sys_controller.is_service_running.side_effect = [False, True]
        mock_gpu_monitor.get_memory_usage.return_value = {
            "total": 24 * 1024 ** 3,
            "used": 5 * 1024 ** 3,
            "available": 19 * 1024 ** 3
        }
        
        result = await scheduler.start_model("gemma-4-31b")
        assert result is True
        mock_sys_controller.start_service.assert_called_once_with("vllm-gemma")

    @pytest.mark.asyncio
    async def test_start_model_insufficient_memory(self, scheduler, mock_gpu_monitor):
        mock_gpu_monitor.get_memory_usage.return_value = {
            "total": 24 * 1024 ** 3,
            "used": 23 * 1024 ** 3,
            "available": 1 * 1024 ** 3
        }
        
        result = await scheduler.start_model("gemma-4-31b")
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_model(self, scheduler, mock_sys_controller):
        mock_sys_controller.stop_service.return_value = True
        
        result = await scheduler.stop_model("gemma-4-31b")
        assert result is True
        mock_sys_controller.stop_service.assert_called_once_with("vllm-gemma")

    def test_get_concurrency_limit(self, scheduler):
        assert scheduler.get_concurrency_limit() == 4

    def test_get_min_available_memory(self, scheduler):
        assert scheduler.get_min_available_memory() == 2 * 1024 ** 3

    def test_acquire_request(self, scheduler):
        result = scheduler.acquire_request("gemma-4-31b")
        assert result is True

    def test_release_request(self, scheduler):
        scheduler.acquire_request("gemma-4-31b")
        scheduler.release_request("gemma-4-31b")

    def test_get_current_model_name_prefers_latest_selected_running_model(self, scheduler):
        scheduler.running_models["gemma-4-31b"] = datetime(2026, 1, 1, 10, 0, 0)
        scheduler.running_models["llama-3-8b"] = datetime(2026, 1, 1, 9, 0, 0)
        scheduler.mark_model_selected("llama-3-8b")
        scheduler.mark_model_selected("gemma-4-31b")

        assert scheduler.get_current_model_name() == "gemma-4-31b"

    def test_get_active_requests(self, scheduler):
        scheduler.acquire_request("gemma-4-31b")
        count = scheduler.get_active_requests("gemma-4-31b")
        assert count >= 0

    def test_can_accept_request(self, scheduler):
        assert scheduler.can_accept_request("gemma-4-31b") is True

    def test_model_name_fuzzy_matching(self, scheduler):
        """测试模型名称模糊匹配功能"""
        # 精确匹配
        assert scheduler.is_model_available("gemma-4-31b") is True
        assert scheduler.is_model_available("llama-3-8b") is True
        
        # 大小写不敏感匹配
        assert scheduler.is_model_available("Gemma-4-31b") is True
        assert scheduler.is_model_available("GEMMA-4-31B") is True
        assert scheduler.is_model_available("Llama-3-8B") is True
        
        # 简写名称匹配
        assert scheduler.is_model_available("gemma") is True
        assert scheduler.is_model_available("llama") is True
        
        # 带后缀的模型名称匹配
        assert scheduler.is_model_available("Gemma-4-31B-Abliterated") is True
        assert scheduler.is_model_available("gemma-4-31b-abliterated") is True
        assert scheduler.is_model_available("abliterated") is True
        
        # 获取配置测试
        config = scheduler.get_model_config("gemma-4-31b")
        assert config is not None
        assert config.get("service") == "vllm-gemma"
        
        # 获取带后缀模型的配置
        config = scheduler.get_model_config("Gemma-4-31B-Abliterated")
        assert config is not None
        assert config.get("service") == "vllm"
        
        # 未知模型
        assert scheduler.is_model_available("unknown-model") is False
