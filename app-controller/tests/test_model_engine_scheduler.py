import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from core.model_engine_scheduler import ModelEngineScheduler
from core.model_hub import SearchResult


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
