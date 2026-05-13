import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import signal
from core.llm_service_manager import LLMServiceManager
from core.config import AppConfig, ModelConfig, SettingsConfig


def _make_manager(config=None):
    mgr = LLMServiceManager.__new__(LLMServiceManager)
    mgr._config = config
    mgr._processes = {}
    mgr._engine_types = {}
    mgr._ports = {}
    mgr._models = {}
    mgr._start_times = {}
    mgr._restart_counts = {}
    mgr._health_status = {}
    mgr._model_paths = {}
    mgr._pgids = {}
    return mgr


def _make_config():
    return AppConfig(
        models={
            "Qwen3-235B": ModelConfig(
                service="vllm-Qwen3-235B",
                port=8000,
                required_memory="8GB",
                vllm_params={"max_model_len": 8192, "gpu_memory_utilization": 0.85},
            ),
        },
        settings=SettingsConfig(gpu_memory_utilization=0.85),
        vllm={"model_base_path": "/mnt/pve_models"},
    )


class TestBuildCommandVLLM:
    def test_vllm_basic_command(self):
        mgr = _make_manager()
        cmd = mgr.build_command("Qwen3-235B", "vllm", 8000)
        assert cmd[0] == "vllm"
        assert "serve" in cmd
        cmd_str = " ".join(cmd)
        assert "/mnt/pve_models/Qwen3-235B" in cmd_str
        assert "--port" in cmd_str

    def test_vllm_command_with_model_path(self):
        mgr = _make_manager()
        mgr._model_paths["Qwen3-235B"] = "/custom/path/Qwen3-235B"
        cmd = mgr.build_command("Qwen3-235B", "vllm", 8000)
        assert "/custom/path/Qwen3-235B" in " ".join(cmd)

    def test_vllm_with_config_params(self):
        config = _make_config()
        mgr = _make_manager(config)
        cmd = mgr.build_command("Qwen3-235B", "vllm", 8000)
        cmd_str = " ".join(cmd)
        assert "--max-model-len" in cmd_str
        assert "8192" in cmd_str
        assert "--gpu-memory-utilization" in cmd_str

    def test_vllm_with_tool_calling(self):
        config = AppConfig(
            models={
                "Qwen3-235B": ModelConfig(
                    service="vllm-Qwen3-235B",
                    port=8000,
                    required_memory="8GB",
                    supports_tool_calling=True,
                    vllm_params={"tool_call_parser": "hermes"},
                ),
            },
            settings=SettingsConfig(),
        )
        mgr = _make_manager(config)
        cmd = mgr.build_command("Qwen3-235B", "vllm", 8000)
        cmd_str = " ".join(cmd)
        assert "--tool-call-parser" in cmd_str
        assert "--enable-auto-tool-choice" in cmd_str

    def test_vllm_with_tool_calling_from_raw_config_dict(self):
        config = {
            "models": {
                "Gemma-4-31B-Abliterated": {
                    "service": "vllm-aiclient",
                    "port": 8000,
                    "required_memory": "40GB",
                    "model_path": "/mnt/pve_models/Gemma-4-31B-Abliterated",
                    "supports_images": True,
                    "supports_tool_calling": True,
                    "vllm_params": {"tool_call_parser": "gemma4"},
                },
            },
            "settings": {"gpu_memory_utilization": 0.9},
        }
        mgr = _make_manager(config)
        cmd = mgr.build_command("Gemma-4-31B-Abliterated", "vllm", 8000)
        cmd_str = " ".join(cmd)
        assert "--enable-auto-tool-choice" in cmd_str
        assert "--tool-call-parser" in cmd_str
        assert "gemma4" in cmd_str
        assert "--limit-mm-per-prompt" in cmd_str


class TestBuildCommandSGLang:
    def test_sglang_basic_command(self):
        mgr = _make_manager()
        cmd = mgr.build_command("Qwen3-235B", "sglang", 8100)
        assert cmd[0] == "python"
        assert "sglang" in " ".join(cmd)
        assert "--port" in " ".join(cmd)
        assert "--model-path" in " ".join(cmd)

    def test_sglang_with_tensor_parallel(self):
        config = AppConfig(
            models={
                "Qwen3-235B": ModelConfig(
                    service="sglang-Qwen3-235B",
                    port=8100,
                    required_memory="8GB",
                    sglang_params={"tensor_parallel_size": 2},
                ),
            },
            settings=SettingsConfig(),
        )
        mgr = _make_manager(config)
        cmd = mgr.build_command("Qwen3-235B", "sglang", 8100)
        cmd_str = " ".join(cmd)
        assert "--tp" in cmd_str
        assert "2" in cmd_str


class TestBuildCommandLLamaCpp:
    def test_llamacpp_basic_command(self):
        mgr = _make_manager()
        cmd = mgr.build_command("test-gguf", "llamacpp", 8200)
        assert "llama-server" in cmd or "./llama-server" in cmd
        assert "-m" in cmd
        assert "--port" in " ".join(cmd)
        assert "-ngl" in " ".join(cmd)

    def test_unsupported_engine_raises(self):
        mgr = _make_manager()
        with pytest.raises(ValueError, match="Unsupported engine type"):
            mgr.build_command("test", "unknown_engine", 8000)


class TestGetModelPath:
    def test_get_model_path_from_model_paths_dict(self):
        mgr = _make_manager()
        mgr._model_paths["test-model"] = "/custom/path"
        assert mgr._get_model_path("test-model") == "/custom/path"

    def test_get_model_path_from_config(self):
        config = AppConfig(
            models={
                "test-model": ModelConfig(
                    service="vllm-test",
                    port=8000,
                    required_memory="8GB",
                    model_path="/config/path/test-model",
                ),
            },
            settings=SettingsConfig(),
            vllm={"model_base_path": "/mnt/pve_models"},
        )
        mgr = _make_manager(config)
        assert mgr._get_model_path("test-model") == "/config/path/test-model"

    def test_get_model_path_default(self):
        mgr = _make_manager()
        result = mgr._get_model_path("test-model")
        assert result == "/mnt/pve_models/test-model"


class TestStartService:
    @patch("core.llm_service_manager.os.getpgid", return_value=12345)
    @patch("core.llm_service_manager.os.setsid", return_value=0)
    @patch("core.llm_service_manager.subprocess.Popen")
    def test_start_service_success(self, mock_popen, mock_setsid, mock_getpgid):
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        mgr = _make_manager()
        result = mgr.start_service("vllm-test", "test-model", "vllm", 8000)
        assert result["status"] == "started"
        assert result["pid"] == 12345
        assert "vllm-test" in mgr._processes
        assert mgr._engine_types["vllm-test"] == "vllm"
        assert mgr._health_status["vllm-test"] == "starting"

    @patch("core.llm_service_manager.os.getpgid", return_value=12345)
    @patch("core.llm_service_manager.os.setsid", return_value=0)
    @patch("core.llm_service_manager.subprocess.Popen")
    def test_start_service_with_model_path(self, mock_popen, mock_setsid, mock_getpgid):
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        mgr = _make_manager()
        result = mgr.start_service("vllm-test", "test-model", "vllm", 8000, model_path="/custom/path")
        assert result["status"] == "started"
        assert mgr._model_paths["test-model"] == "/custom/path"

    @patch("core.llm_service_manager.subprocess.Popen")
    def test_start_service_failure(self, mock_popen):
        mock_popen.side_effect = OSError("failed")
        mgr = _make_manager()
        result = mgr.start_service("vllm-test", "test-model", "vllm", 8000)
        assert result["status"] == "error"


class TestStopService:
    def test_graceful_stop(self):
        mgr = _make_manager()
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mgr._processes = {"test": mock_process}
        mgr._engine_types = {"test": "vllm"}
        mgr._ports = {"test": 8000}
        mgr._models = {"test": "model"}
        mgr._start_times = {"test": 1000.0}
        mgr._health_status = {"test": "healthy"}
        mgr._model_paths = {"model": "/path"}
        result = mgr.stop_service("test")
        assert result is True
        assert "test" not in mgr._processes
        assert "test" not in mgr._health_status

    def test_stop_nonexistent_service(self):
        mgr = _make_manager()
        result = mgr.stop_service("nonexistent")
        assert result is False


class TestForceStopService:
    def test_force_stop(self):
        mgr = _make_manager()
        mock_process = MagicMock()
        mgr._processes = {"test": mock_process}
        mgr._engine_types = {"test": "vllm"}
        mgr._health_status = {"test": "healthy"}
        result = mgr.force_stop_service("test")
        assert result is True
        assert "test" not in mgr._processes

    def test_force_stop_nonexistent(self):
        mgr = _make_manager()
        result = mgr.force_stop_service("nonexistent")
        assert result is False


class TestCleanupService:
    def test_cleanup_removes_all_entries(self):
        mgr = _make_manager()
        mgr._processes["svc"] = MagicMock()
        mgr._engine_types["svc"] = "vllm"
        mgr._ports["svc"] = 8000
        mgr._models["svc"] = "model"
        mgr._start_times["svc"] = 1000.0
        mgr._health_status["svc"] = "healthy"
        mgr._model_paths["model"] = "/path"
        mgr._cleanup_service("svc")
        assert "svc" not in mgr._processes
        assert "svc" not in mgr._engine_types
        assert "svc" not in mgr._ports
        assert "svc" not in mgr._models
        assert "svc" not in mgr._start_times
        assert "svc" not in mgr._health_status


class TestGetServiceStatus:
    def test_running_service_status(self):
        mgr = _make_manager()
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mgr._processes = {"vllm-test": mock_process}
        mgr._engine_types = {"vllm-test": "vllm"}
        mgr._ports = {"vllm-test": 8000}
        mgr._models = {"vllm-test": "Qwen3-235B"}
        mgr._start_times = {"vllm-test": 1000.0}
        mgr._health_status = {"vllm-test": "healthy"}
        result = mgr.get_service_status("vllm-test")
        assert result["status"] == "running"
        assert result["engine_type"] == "vllm"
        assert result["pid"] == 12345
        assert result["port"] == 8000
        assert result["model"] == "Qwen3-235B"
        assert result["health"] == "healthy"

    def test_nonexistent_service_status(self):
        mgr = _make_manager()
        result = mgr.get_service_status("nonexistent")
        assert result["status"] == "not_found"

    def test_stopped_service_cleanup(self):
        mgr = _make_manager()
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        mgr._processes = {"vllm-test": mock_process}
        mgr._engine_types = {"vllm-test": "vllm"}
        mgr._health_status = {"vllm-test": "healthy"}
        result = mgr.get_service_status("vllm-test")
        assert result["status"] == "stopped"
        assert "vllm-test" not in mgr._processes


class TestCheckHealth:
    def test_check_health_running(self):
        mgr = _make_manager()
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mgr._processes = {"test": mock_process}
        assert mgr.check_health("test") is True

    def test_check_health_not_found(self):
        mgr = _make_manager()
        assert mgr.check_health("nonexistent") is False


class TestAutoRestart:
    def test_auto_restart(self):
        mgr = _make_manager()
        mgr._models["test"] = "Qwen3-235B"
        mgr._engine_types["test"] = "vllm"
        mgr._ports["test"] = 8000
        mgr._restart_counts["test"] = 0
        with patch("core.llm_service_manager.os.getpgid", return_value=12346):
            with patch("core.llm_service_manager.os.setsid", return_value=0):
                with patch("core.llm_service_manager.subprocess.Popen") as mock_popen:
                    mock_process = MagicMock()
                    mock_process.pid = 12346
                    mock_popen.return_value = mock_process
                    result = mgr.auto_restart("test")
        assert result["status"] == "started"
        assert mgr._restart_counts["test"] == 0

    def test_max_restarts_exceeded(self):
        mgr = _make_manager()
        mgr._restart_counts["test"] = 3
        result = mgr.auto_restart("test")
        assert result["status"] == "max_restarts_exceeded"

    def test_get_and_reset_restart_count(self):
        mgr = _make_manager()
        mgr._restart_counts["test"] = 2
        assert mgr.get_restart_count("test") == 2
        mgr.reset_restart_count("test")
        assert mgr.get_restart_count("test") == 0


class TestListServices:
    def test_list_services(self):
        mgr = _make_manager()
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mgr._processes = {"svc1": mock_process}
        mgr._engine_types = {"svc1": "vllm"}
        mgr._ports = {"svc1": 8000}
        mgr._models = {"svc1": "model1"}
        mgr._start_times = {"svc1": 1000.0}
        mgr._health_status = {"svc1": "healthy"}
        result = mgr.list_services()
        assert len(result) == 1
        assert result[0]["service_name"] == "svc1"

    def test_list_services_by_engine(self):
        mgr = _make_manager()
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mgr._processes = {"svc1": mock_process, "svc2": mock_process}
        mgr._engine_types = {"svc1": "vllm", "svc2": "sglang"}
        mgr._ports = {"svc1": 8000, "svc2": 8100}
        mgr._models = {"svc1": "m1", "svc2": "m2"}
        mgr._start_times = {"svc1": 1000.0, "svc2": 1000.0}
        mgr._health_status = {"svc1": "healthy", "svc2": "healthy"}
        result = mgr.list_services_by_engine("vllm")
        assert len(result) == 1

    def test_get_service_by_model(self):
        mgr = _make_manager()
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mgr._processes = {"svc1": mock_process}
        mgr._engine_types = {"svc1": "vllm"}
        mgr._ports = {"svc1": 8000}
        mgr._models = {"svc1": "Qwen3-235B"}
        mgr._start_times = {"svc1": 1000.0}
        mgr._health_status = {"svc1": "healthy"}
        result = mgr.get_service_by_model("Qwen3-235B")
        assert result is not None
        assert result["model"] == "Qwen3-235B"

    def test_get_service_by_port(self):
        mgr = _make_manager()
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mgr._processes = {"svc1": mock_process}
        mgr._engine_types = {"svc1": "vllm"}
        mgr._ports = {"svc1": 8000}
        mgr._models = {"svc1": "model"}
        mgr._start_times = {"svc1": 1000.0}
        mgr._health_status = {"svc1": "healthy"}
        result = mgr.get_service_by_port(8000)
        assert result is not None
        assert result["port"] == 8000


class TestCleanupAll:
    def test_cleanup_all(self):
        mgr = _make_manager()
        mock_process1 = MagicMock()
        mock_process2 = MagicMock()
        mgr._processes = {"svc1": mock_process1, "svc2": mock_process2}
        mgr._engine_types = {"svc1": "vllm", "svc2": "sglang"}
        mgr._health_status = {"svc1": "healthy", "svc2": "healthy"}
        mgr.cleanup_all()
        assert len(mgr._processes) == 0
