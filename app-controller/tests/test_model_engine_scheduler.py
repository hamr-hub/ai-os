import pytest
import time
import signal
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from core.model_engine_scheduler import ModelEngineScheduler
from core.model_hub import SearchResult
from core.llm_service_manager import LLMServiceManager


def _make_scheduler(**kwargs):
    scheduler = ModelEngineScheduler.__new__(ModelEngineScheduler)
    scheduler._config = kwargs.get("config", None)
    scheduler._gpu_mgr = kwargs.get("gpu_mgr", MagicMock())
    scheduler._model_hub = kwargs.get("model_hub", MagicMock())
    scheduler._download_mgr = kwargs.get("download_mgr", None)
    scheduler._model_pool = kwargs.get("model_pool", None)
    scheduler._llm_mgr = kwargs.get("llm_mgr", MagicMock())
    scheduler._switching_lock = MagicMock()
    scheduler._active_service = None
    scheduler._switch_history = []
    scheduler._max_history = 50
    scheduler._engine_model_registry = {}
    return scheduler


class TestShowGPU:
    def test_show_gpu_returns_summary(self):
        gpu_mgr = MagicMock()
        gpu_mgr.get_memory_summary.return_value = {
            "backend": "mock",
            "device_count": 1,
            "devices": [{"device_id": 0, "total_gb": 24.0, "used_gb": 8.0, "free_gb": 16.0}],
            "loaded_models": [],
            "total_loaded_memory_gb": 0,
        }
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr)
        result = scheduler.show_gpu()
        assert result["available"] is True
        assert result["backend"] == "mock"
        assert "devices" in result

    def test_show_gpu_no_gpu_manager(self):
        scheduler = _make_scheduler(gpu_mgr=None)
        result = scheduler.show_gpu()
        assert result["available"] is False
        assert "message" in result


class TestSearch:
    def test_search_with_feasibility(self):
        gpu_mgr = MagicMock()
        gpu_mgr.check_model_feasibility.return_value = {"feasible": True, "required_gb": 6}
        model_hub = MagicMock()
        model_hub.search_models.return_value = [
            SearchResult(name="Qwen2.5-7B", source="huggingface", size_b=7, quant="4bit", feasible=True)
        ]
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr, model_hub=model_hub)
        result = scheduler.search("qwen", "huggingface")
        assert len(result) >= 1

    def test_search_no_model_hub(self):
        scheduler = _make_scheduler(model_hub=None)
        result = scheduler.search("qwen", "huggingface")
        assert result == []


class TestRecommendEngine:
    def test_recommend_from_config(self):
        from core.config import AppConfig, ModelConfig, SettingsConfig
        config = AppConfig(
            models={"test-model": ModelConfig(service="svc", port=8000, required_memory="8GB", engine_type="sglang")},
            settings=SettingsConfig(),
        )
        scheduler = _make_scheduler(config=config)
        result = scheduler.recommend_engine("test-model")
        assert result == "sglang"

    def test_recommend_gguf_to_llamacpp(self):
        scheduler = _make_scheduler()
        result = scheduler.recommend_engine("model-gguf-Q4")
        assert result == "llamacpp"

    def test_recommend_awq_to_vllm(self):
        scheduler = _make_scheduler()
        result = scheduler.recommend_engine("model-awq")
        assert result == "vllm"

    def test_recommend_default_vllm(self):
        scheduler = _make_scheduler()
        result = scheduler.recommend_engine("test-model")
        assert result == "vllm"

    def test_recommend_with_low_free_gb_preference(self):
        gpu_mgr = MagicMock()
        gpu_mgr.get_total_free_gb.return_value = 4.0
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr, config=None)
        result = scheduler.recommend_engine("test-model-gguf-Q4")
        assert result == "llamacpp"

    def test_recommend_with_capabilities(self):
        scheduler = _make_scheduler()
        result = scheduler.recommend_engine("test-model", required_capabilities=["supports_tool_calling"])
        assert result == "vllm"


class TestRecommend:
    def test_recommend_returns_full_result(self):
        gpu_mgr = MagicMock()
        gpu_mgr.get_memory_summary.return_value = {"backend": "mock", "device_count": 1, "devices": []}
        gpu_mgr.get_total_free_gb.return_value = 16.0
        gpu_mgr.check_model_feasibility.return_value = {"feasible": True, "required_gb": 6}
        model_hub = MagicMock()
        model_hub.search_models.return_value = [
            SearchResult(name="Qwen2.5-7B", source="hf", size_b=7, quant="4bit", feasible=True)
        ]
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr, model_hub=model_hub)
        result = scheduler.recommend("qwen", "huggingface")
        assert "gpu_info" in result
        assert "recommended_engine" in result
        assert "engine_capabilities" in result
        assert "candidates" in result

    def test_recommend_no_results(self):
        gpu_mgr = MagicMock()
        gpu_mgr.get_memory_summary.return_value = {"backend": "mock", "device_count": 0, "devices": []}
        model_hub = MagicMock()
        model_hub.search_models.return_value = []
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr, model_hub=model_hub)
        result = scheduler.recommend("nonexistent", "all")
        assert result["recommended"] is None


class TestSwitchModel:
    @pytest.mark.asyncio
    async def test_switch_model_already_running(self):
        llm_mgr = MagicMock()
        target_service = {"status": "running", "service_name": "vllm-Qwen2.5-7B", "model": "Qwen2.5-7B"}
        llm_mgr.get_service_by_model.return_value = target_service
        scheduler = _make_scheduler(llm_mgr=llm_mgr, gpu_mgr=MagicMock())
        scheduler._switching_lock = AsyncMock()
        scheduler._switching_lock.__aenter__ = AsyncMock(return_value=None)
        scheduler._switching_lock.__aexit__ = AsyncMock(return_value=None)
        result = await scheduler.switch_model("Qwen2.5-7B")
        assert result["success"] is True
        assert result["reason"] == "already_running"

    @pytest.mark.asyncio
    async def test_switch_model_insufficient_memory(self):
        gpu_mgr = MagicMock()
        gpu_mgr.check_model_feasibility.return_value = {"feasible": False}
        llm_mgr = MagicMock()
        llm_mgr.list_services.return_value = []
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr, llm_mgr=llm_mgr)
        scheduler._switching_lock = AsyncMock()
        scheduler._switching_lock.__aenter__ = AsyncMock(return_value=None)
        scheduler._switching_lock.__aexit__ = AsyncMock(return_value=None)
        scheduler._free_up_memory_for = AsyncMock(return_value=False)
        result = await scheduler.switch_model("huge-model")
        assert result["success"] is False
        assert "insufficient" in result["reason"] or "memory" in result["reason"]


class TestDeployModel:
    @pytest.mark.asyncio
    async def test_deploy_insufficient_memory_no_force(self):
        gpu_mgr = MagicMock()
        gpu_mgr.check_model_feasibility.return_value = {"feasible": False}
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr)
        scheduler._switching_lock = AsyncMock()
        scheduler._switching_lock.__aenter__ = AsyncMock(return_value=None)
        scheduler._switching_lock.__aexit__ = AsyncMock(return_value=None)
        result = await scheduler.deploy_model("huge-model")
        assert result["success"] is False
        assert result["reason"] == "insufficient_gpu_memory"


class TestUndeployModel:
    @pytest.mark.asyncio
    async def test_undeploy_model_not_running(self):
        llm_mgr = MagicMock()
        llm_mgr.get_service_by_model.return_value = None
        scheduler = _make_scheduler(llm_mgr=llm_mgr)
        scheduler._switching_lock = AsyncMock()
        scheduler._switching_lock.__aenter__ = AsyncMock(return_value=None)
        scheduler._switching_lock.__aexit__ = AsyncMock(return_value=None)
        result = await scheduler.undeploy_model("nonexistent")
        assert result["success"] is False
        assert result["reason"] == "model_not_running"


class TestSwitchHistory:
    def test_record_and_get_history(self):
        scheduler = _make_scheduler()
        scheduler._record_switch("model1", "vllm", 8000, "deploy")
        scheduler._record_switch("model2", "sglang", 8100, "switch")
        history = scheduler.get_switch_history(limit=2)
        assert len(history) == 2
        assert history[0]["model"] == "model1"
        assert history[1]["model"] == "model2"

    def test_history_max_limit(self):
        scheduler = _make_scheduler()
        for i in range(60):
            scheduler._record_switch(f"model{i}", "vllm", 8000, "deploy")
        assert len(scheduler._switch_history) == 50


class TestGetActiveService:
    def test_get_active_service(self):
        llm_mgr = MagicMock()
        llm_mgr.get_service_status.return_value = {"status": "running"}
        scheduler = _make_scheduler(llm_mgr=llm_mgr)
        scheduler._active_service = "vllm-test"
        result = scheduler.get_active_service()
        assert result["status"] == "running"

    def test_get_active_service_none(self):
        scheduler = _make_scheduler(llm_mgr=None)
        result = scheduler.get_active_service()
        assert result is None


class TestGetAvailableEngines:
    def test_get_available_engines(self):
        scheduler = _make_scheduler()
        engines = scheduler.get_available_engines()
        assert "vllm" in engines
        assert "sglang" in engines
        assert "llamacpp" in engines
        assert "supports_images" in engines["vllm"]


class TestFindAvailablePort:
    def test_find_available_port_default(self):
        llm_mgr = MagicMock()
        llm_mgr.list_services.return_value = []
        scheduler = _make_scheduler(llm_mgr=llm_mgr)
        port = scheduler._find_available_port("vllm")
        assert port == 8000

    def test_find_available_port_with_used(self):
        llm_mgr = MagicMock()
        llm_mgr.list_services.return_value = [{"port": 8000}]
        scheduler = _make_scheduler(llm_mgr=llm_mgr)
        port = scheduler._find_available_port("vllm")
        assert port == 8001

    def test_find_available_port_no_llm_mgr(self):
        scheduler = _make_scheduler(llm_mgr=None)
        port = scheduler._find_available_port("vllm")
        assert port == 8000


class TestDeploymentSummary:
    def test_get_deployment_summary(self):
        gpu_mgr = MagicMock()
        gpu_mgr.get_memory_summary.return_value = {"backend": "mock"}
        gpu_mgr.get_loaded_models.return_value = {}
        llm_mgr = MagicMock()
        llm_mgr.list_services.return_value = []
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr, llm_mgr=llm_mgr)
        summary = scheduler.get_deployment_summary()
        assert "gpu" in summary
        assert "running_services" in summary
        assert "loaded_models" in summary
        assert "active_service" in summary


class TestSwitchEngine:
    def test_switch_engine_unsupported_engine(self):
        scheduler = _make_scheduler(llm_mgr=MagicMock())
        result = scheduler.switch_engine("model", "unknown_engine", 8000)
        assert result["success"] is False
        assert "unsupported" in result["reason"]

    def test_switch_engine_no_llm_mgr(self):
        scheduler = _make_scheduler(llm_mgr=None)
        result = scheduler.switch_engine("model", "vllm", 8000)
        assert result["success"] is False
        assert result["reason"] == "no_llm_service_manager"

    def test_switch_engine_insufficient_memory(self):
        gpu_mgr = MagicMock()
        gpu_mgr.check_model_feasibility.return_value = {"feasible": False, "available_gb": 4.0, "required_gb": 40.0}
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr, llm_mgr=MagicMock())
        result = scheduler.switch_engine("big-model", "vllm", 8000)
        assert result["success"] is False
        assert result["reason"] == "insufficient_gpu_memory"

    def test_switch_engine_already_same_engine(self):
        llm_mgr = MagicMock()
        llm_mgr.get_service_by_model.return_value = {"status": "running", "service_name": "vllm-model"}
        gpu_mgr = MagicMock()
        gpu_mgr.check_model_feasibility.return_value = {"feasible": True}
        scheduler = _make_scheduler(llm_mgr=llm_mgr, gpu_mgr=gpu_mgr)
        scheduler._engine_model_registry["model"] = {"engine": "vllm"}
        result = scheduler.switch_engine("model", "vllm", 8000)
        assert result["success"] is True
        assert result["reason"] == "already_running_same_engine"

    def test_switch_engine_initiates_async(self):
        llm_mgr = MagicMock()
        llm_mgr.get_service_by_model.return_value = None
        gpu_mgr = MagicMock()
        gpu_mgr.check_model_feasibility.return_value = {"feasible": True}
        scheduler = _make_scheduler(llm_mgr=llm_mgr, gpu_mgr=gpu_mgr)
        with patch('asyncio.get_running_loop', side_effect=RuntimeError("no loop")):
            result = scheduler.switch_engine("model", "sglang", 8100)
        assert result["success"] is True
        assert result["status"] == "switching"
        assert scheduler._engine_model_registry["model"]["engine"] == "sglang"


class TestGetRealtimeGPU:
    def test_get_realtime_no_gpu_mgr(self):
        scheduler = _make_scheduler(gpu_mgr=None)
        result = scheduler.get_realtime_gpu_info()
        assert result["available"] is False

    def test_get_realtime_with_gpu_mgr(self):
        gpu_mgr = MagicMock()
        gpu_mgr.get_realtime_info.return_value = {
            "total_gb": 80.0, "used_gb": 40.0, "free_gb": 40.0,
            "utilization_pct": 50.0, "backend": "pynvml",
            "effective_free_gb": 35.0,
        }
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr)
        result = scheduler.get_realtime_gpu_info(0)
        assert result["available"] is True
        assert result["effective_free_gb"] == 35.0

    def test_get_all_gpu_realtime(self):
        gpu_mgr = MagicMock()
        gpu_mgr.get_all_gpu_info.return_value = [{"device_id": 0}]
        gpu_mgr.backend = "pynvml"
        gpu_mgr.get_loaded_memory_gb.return_value = 10.0
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr)
        result = scheduler.get_all_gpu_realtime()
        assert result["available"] is True
        assert result["device_count"] == 1


class TestModelPool:
    def test_build_model_pool_from_config(self):
        from core.config import AppConfig, ModelConfig, SettingsConfig
        config = AppConfig(
            models={
                "test-model": ModelConfig(
                    service="svc", port=8000, engine_type="vllm",
                    required_memory="40GB", model_path="/mnt/test"
                )
            },
            settings=SettingsConfig(),
        )
        scheduler = _make_scheduler(config=config)
        pool = scheduler._build_model_pool_from_config()
        assert "test-model" in pool
        assert pool["test-model"]["engine"] == "vllm"
        assert pool["test-model"]["port"] == 8000

    def test_get_model_pool_merges_registry(self):
        from core.config import AppConfig, ModelConfig, SettingsConfig
        config = AppConfig(
            models={"config-model": ModelConfig(service="svc", port=8000, required_memory="8GB")},
            settings=SettingsConfig(),
        )
        scheduler = _make_scheduler(config=config)
        scheduler._engine_model_registry["runtime-model"] = {
            "engine": "sglang", "port": 8100, "status": "running"
        }
        pool = scheduler.get_model_pool()
        assert "config-model" in pool
        assert "runtime-model" in pool

    def test_empty_config_pool(self):
        scheduler = _make_scheduler(config=None)
        pool = scheduler._build_model_pool_from_config()
        assert pool == {}


class TestSchedulerStatus:
    def test_get_scheduler_status(self):
        gpu_mgr = MagicMock()
        gpu_mgr.get_memory_summary.return_value = {"backend": "mock", "devices": []}
        gpu_mgr.get_loaded_models.return_value = {}
        llm_mgr = MagicMock()
        llm_mgr.list_services.return_value = [{"status": "running", "model": "test"}]
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr, llm_mgr=llm_mgr)
        status = scheduler.get_scheduler_status()
        assert "active_service" in status
        assert "gpu" in status
        assert "running_services" in status
        assert status["running_count"] == 1
        assert "available_engines" in status


class TestAutoDeployModel:
    @pytest.mark.asyncio
    async def test_auto_deploy_insufficient_memory(self):
        gpu_mgr = MagicMock()
        gpu_mgr.check_model_feasibility.return_value = {"feasible": False, "required_gb": 40, "available_gb": 4}
        scheduler = _make_scheduler(gpu_mgr=gpu_mgr)
        result = await scheduler.auto_deploy_model("huge-model")
        assert result["success"] is False
        assert result["stage"] == "memory_check"


class TestSyncConfigToRegistry:
    def test_sync_config_to_registry(self):
        from core.config import AppConfig, ModelConfig, SettingsConfig
        config = AppConfig(
            models={
                "preload-model": ModelConfig(
                    service="svc", port=8000, required_memory="40GB",
                    preload=True, engine_type="vllm"
                ),
                "no-preload-model": ModelConfig(
                    service="svc", port=8000, required_memory="8GB",
                    preload=False, engine_type="sglang"
                ),
            },
            settings=SettingsConfig(),
        )
        scheduler = _make_scheduler(config=config)
        scheduler._sync_config_to_registry()
        assert "preload-model" in scheduler._engine_model_registry
        assert scheduler._engine_model_registry["preload-model"]["preload_intended"] is True
        assert "no-preload-model" in scheduler._engine_model_registry


class TestLLMServiceManagerVllmServe:
    def test_build_vllm_command_uses_vllm_serve(self):
        mgr = LLMServiceManager(config=None)
        cmd = mgr._build_vllm_command("/mnt/models/Qwen3", 8000, {})
        assert cmd[0] == "vllm"
        assert cmd[1] == "serve"
        assert cmd[2] == "/mnt/models/Qwen3"
        assert "--port" in cmd
        assert "--host" in cmd
        assert "0.0.0.0" in cmd
        assert "--trust-remote-code" in cmd
        assert "--enforce-eager" in cmd

    def test_build_vllm_command_with_params(self):
        mgr = LLMServiceManager(config=None)
        cfg = {"vllm_params": {"gpu_memory_utilization": 0.90, "max_model_len": 40960, "max_num_seqs": 256, "max_num_batched_tokens": 16384, "enable_chunked_prefill": True, "moe_backend": "cutlass"}}
        cmd = mgr._build_vllm_command("/mnt/models/Qwen3", 8000, cfg)
        assert "--gpu-memory-utilization" in cmd
        assert "0.9" in cmd
        assert "--max-model-len" in cmd
        assert "40960" in cmd
        assert "--max-num-seqs" in cmd
        assert "--enable-chunked-prefill" in cmd
        assert "--moe-backend" in cmd
        assert "cutlass" in cmd

    def test_build_vllm_command_tool_call(self):
        mgr = LLMServiceManager(config=None)
        from core.config import ModelConfig
        cfg = ModelConfig(service="svc", port=8000, required_memory="8GB", supports_tool_calling=True, vllm_params={"tool_call_parser": "hermes"})
        cmd = mgr._build_vllm_command("/mnt/models/Qwen3", 8000, cfg)
        assert "--enable-auto-tool-choice" in cmd
        assert "--tool-call-parser" in cmd
        assert "hermes" in cmd

    def test_build_vllm_env_includes_required_vars(self):
        mgr = LLMServiceManager(config=None)
        env = mgr._get_vllm_env("test-model")
        assert env["VLLM_USE_V1"] == "1"
        assert env["NCCL_P2P_DISABLE"] == "1"
        assert env["CUDA_MANAGED_FORCE_DEVICE_ALLOC"] == "1"
        assert env["OMP_NUM_THREADS"] == "16"
        assert env["VLLM_NO_FLASHINFER"] == "1"
        assert "HF_ENDPOINT" in env

    def test_build_vllm_env_with_attention_backend(self):
        from core.config import AppConfig, ModelConfig, SettingsConfig
        config = AppConfig(
            models={"Qwen3": ModelConfig(service="svc", port=8000, required_memory="40GB", vllm_params={"attention_backend": "FLASH_ATTN", "env_vars": {"CUSTOM_VLLM_FLAG": "enabled"}, "nvfp4_gemm_backend": "cutlass", "use_flashinfer_moe_fp4": False})},
            settings=SettingsConfig(),
        )
        mgr = LLMServiceManager(config=config)
        env = mgr._get_vllm_env("Qwen3")
        assert env["VLLM_ATTENTION_BACKEND"] == "FLASH_ATTN"
        assert env["CUSTOM_VLLM_FLAG"] == "enabled"
        assert env["VLLM_NVFP4_GEMM_BACKEND"] == "cutlass"
        assert env["VLLM_USE_FLASHINFER_MOE_FP4"] == "0"

    def test_build_vllm_env_no_attention_backend(self):
        mgr = LLMServiceManager(config=None)
        env = mgr._get_vllm_env("test-model")
        assert "VLLM_ATTENTION_BACKEND" not in env

    def test_stop_service_uses_killpg(self):
        mgr = LLMServiceManager(config=None)
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.wait.side_effect = [None]
        mgr._processes["test-svc"] = mock_process
        mgr._pgids["test-svc"] = 12345
        mgr._engine_types["test-svc"] = "vllm"
        mgr._ports["test-svc"] = 8000
        mgr._models["test-svc"] = "test"
        mgr._start_times["test-svc"] = time.time()
        mgr._health_status["test-svc"] = "healthy"
        with patch('os.killpg') as mock_killpg:
            result = mgr.stop_service("test-svc")
            mock_killpg.assert_called_with(12345, signal.SIGINT)
        assert result is True

    def test_get_service_status_includes_pgid(self):
        mgr = LLMServiceManager(config=None)
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mgr._processes["test-svc"] = mock_process
        mgr._pgids["test-svc"] = 12345
        mgr._engine_types["test-svc"] = "vllm"
        mgr._ports["test-svc"] = 8000
        mgr._models["test-svc"] = "test"
        mgr._start_times["test-svc"] = time.time()
        mgr._health_status["test-svc"] = "healthy"
        status = mgr.get_service_status("test-svc")
        assert status["status"] == "running"
        assert status["pgid"] == 12345
