import pytest
from unittest.mock import Mock, patch, MagicMock
from core.gpu_memory_manager import GPUMemoryManager
from core.gpu_memory_checker import GPUMemoryChecker, GPUMemoryInfo


def _make_gpu_info(device_id=0, total=24*1024**3, used=8*1024**3, free=16*1024**3):
    return GPUMemoryInfo(
        device_id=device_id,
        total_bytes=total,
        used_bytes=used,
        free_bytes=free,
        reserved_bytes=0,
        allocated_bytes=0,
        utilization_pct=50.0,
        backend="mock",
    )


def _make_manager_with_mock_checker(total=24*1024**3, used=8*1024**3, free=16*1024**3):
    mgr = GPUMemoryManager.__new__(GPUMemoryManager)
    mgr._config = None
    mgr._checker = MagicMock(spec=GPUMemoryChecker)
    mgr._checker.backend = "mock"
    mgr._checker.device_count = 1
    mgr._checker.get_device_info.return_value = _make_gpu_info(0, total, used, free)
    mgr._checker.get_all_devices_info.return_value = [_make_gpu_info(0, total, used, free)]
    mgr._checker.get_total_free_bytes.return_value = free
    mgr._checker.parse_model_quant = GPUMemoryChecker.parse_model_quant
    mgr._checker.estimate_model_memory_by_params = GPUMemoryChecker().estimate_model_memory_by_params
    mgr._checker.estimate_model_memory_by_path.return_value = None
    mgr._checker.get_best_device_for_model.return_value = 0
    mgr._loaded_models = {}
    return mgr


class TestInit:
    def test_init_with_mock_checker(self):
        mgr = _make_manager_with_mock_checker()
        assert mgr._checker is not None
        assert mgr._checker.backend == "mock"
        assert mgr._checker.device_count == 1
        assert mgr._loaded_models == {}

    def test_checker_property(self):
        mgr = _make_manager_with_mock_checker()
        assert mgr.checker is mgr._checker

    def test_backend_property(self):
        mgr = _make_manager_with_mock_checker()
        assert mgr.backend == "mock"

    def test_device_count_property(self):
        mgr = _make_manager_with_mock_checker()
        assert mgr.device_count == 1


class TestGetGPUInfo:
    def test_get_gpu_info_returns_dict(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.get_gpu_info(0)
        assert result is not None
        assert "total_gb" in result
        assert "used_gb" in result
        assert "free_gb" in result
        assert "total_bytes" in result

    def test_get_all_gpu_info(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.get_all_gpu_info()
        assert len(result) == 1
        assert "total_gb" in result[0]

    def test_get_gpu_info_no_device(self):
        mgr = _make_manager_with_mock_checker()
        mgr._checker.get_device_info.return_value = None
        result = mgr.get_gpu_info(0)
        assert result is None


class TestFreeMemory:
    def test_get_total_free_bytes(self):
        free = 16 * 1024**3
        mgr = _make_manager_with_mock_checker(free=free)
        assert mgr.get_total_free_bytes() == free

    def test_get_total_free_gb(self):
        free = 16 * 1024**3
        mgr = _make_manager_with_mock_checker(free=free)
        result = mgr.get_total_free_gb()
        assert abs(result - 16.0) < 0.01

    def test_get_effective_free_bytes_no_loaded(self):
        total = 24 * 1024**3
        used = 8 * 1024**3
        mgr = _make_manager_with_mock_checker(total=total, used=used)
        eff = mgr.get_effective_free_bytes(0)
        expected = int(total * 0.85) - used
        assert eff == expected

    def test_get_effective_free_bytes_with_loaded(self):
        total = 24 * 1024**3
        used = 8 * 1024**3
        mgr = _make_manager_with_mock_checker(total=total, used=used)
        mgr._loaded_models = {"model1": {"device_id": 0, "estimated_bytes": 4*1024**3}}
        eff = mgr.get_effective_free_bytes(0)
        expected = int(total * 0.85) - used - 4*1024**3
        assert eff == expected

    def test_get_effective_free_gb(self):
        total = 24 * 1024**3
        used = 8 * 1024**3
        mgr = _make_manager_with_mock_checker(total=total, used=used)
        result = mgr.get_effective_free_gb(0)
        expected = (int(total * 0.85) - used) / (1024**3)
        assert abs(result - expected) < 0.1


class TestEstimateModelMemory:
    def test_estimate_from_size_b_4bit(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.estimate_model_memory("test-model", size_b=7, quant="4bit")
        expected = mgr._checker.estimate_model_memory_by_params(7, "4bit")
        assert result == expected

    def test_estimate_from_size_b_fp16(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.estimate_model_memory("test-model", size_b=7, quant="fp16")
        expected = mgr._checker.estimate_model_memory_by_params(7, "fp16")
        assert result == expected

    def test_estimate_from_size_b_awq(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.estimate_model_memory("test-model", size_b=7, quant="awq")
        expected = mgr._checker.estimate_model_memory_by_params(7, "awq")
        assert result == expected

    def test_estimate_from_size_b_gptq(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.estimate_model_memory("test-model", size_b=7, quant="gptq")
        expected = mgr._checker.estimate_model_memory_by_params(7, "gptq")
        assert result == expected

    def test_estimate_from_size_b_gguf(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.estimate_model_memory("test-model", size_b=7, quant="gguf")
        expected = mgr._checker.estimate_model_memory_by_params(7, "gguf")
        assert result == expected

    def test_estimate_from_size_b_8bit(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.estimate_model_memory("test-model", size_b=7, quant="8bit")
        expected = mgr._checker.estimate_model_memory_by_params(7, "8bit")
        assert result == expected

    def test_estimate_default_no_params(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.estimate_model_memory("unknown-model")
        assert result == 8 * 1024**3

    def test_estimate_gb(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.estimate_model_memory_gb("test-model", size_b=7, quant="4bit")
        bytes_result = mgr.estimate_model_memory("test-model", size_b=7, quant="4bit")
        assert abs(result - bytes_result / (1024**3)) < 0.01

    def test_estimate_large_model(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.estimate_model_memory("test-model", size_b=235, quant="awq")
        assert result > 100 * 1024**3


class TestCheckModelFeasibility:
    def test_feasible_model(self):
        mgr = _make_manager_with_mock_checker(total=24*1024**3, used=2*1024**3, free=22*1024**3)
        result = mgr.check_model_feasibility("test-model", size_b=7, quant="4bit")
        assert result["feasible"] is True
        assert "available_gb" in result
        assert "required_gb" in result
        assert "safety_margin_gb" in result
        assert result["gpu_available"] is True

    def test_not_feasible_model(self):
        mgr = _make_manager_with_mock_checker(total=8*1024**3, used=6*1024**3, free=2*1024**3)
        result = mgr.check_model_feasibility("test-model", size_b=7, quant="fp16")
        assert result["feasible"] is False
        assert result["reason"] == "insufficient_memory"

    def test_no_gpu_available(self):
        mgr = _make_manager_with_mock_checker()
        mgr._checker.get_device_info.return_value = None
        result = mgr.check_model_feasibility("test-model", size_b=7, quant="4bit")
        assert result["feasible"] is False
        assert result["reason"] == "gpu_unavailable"
        assert result["gpu_available"] is False

    def test_model_already_loaded_reason(self):
        mgr = _make_manager_with_mock_checker(total=8*1024**3, used=6*1024**3, free=2*1024**3)
        mgr._loaded_models = {"test-model": {"device_id": 0, "estimated_bytes": 15*1024**3}}
        result = mgr.check_model_feasibility("test-model", size_b=7, quant="fp16")
        assert result["feasible"] is False
        assert result["reason"] == "model_already_loaded"

    def test_feasibility_contains_device_info(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.check_model_feasibility("test-model", size_b=7, quant="4bit")
        assert "device_id" in result
        assert "backend" in result
        assert "loaded_models" in result


class TestLoadedModels:
    def test_register_loaded_model(self):
        mgr = _make_manager_with_mock_checker()
        mgr.register_loaded_model("test-model", device_id=0, size_b=7, quant="4bit")
        assert "test-model" in mgr._loaded_models
        assert mgr._loaded_models["test-model"]["device_id"] == 0
        assert mgr._loaded_models["test-model"]["estimated_bytes"] > 0

    def test_unregister_loaded_model(self):
        mgr = _make_manager_with_mock_checker()
        mgr.register_loaded_model("test-model", device_id=0, size_b=7, quant="4bit")
        mgr.unregister_loaded_model("test-model")
        assert "test-model" not in mgr._loaded_models

    def test_unregister_nonexistent_model(self):
        mgr = _make_manager_with_mock_checker()
        mgr.unregister_loaded_model("nonexistent")
        assert len(mgr._loaded_models) == 0

    def test_get_loaded_models(self):
        mgr = _make_manager_with_mock_checker()
        mgr.register_loaded_model("model1", device_id=0, size_b=7, quant="4bit")
        mgr.register_loaded_model("model2", device_id=0, size_b=14, quant="fp16")
        loaded = mgr.get_loaded_models()
        assert "model1" in loaded
        assert "model2" in loaded
        assert len(loaded) == 2

    def test_get_loaded_memory_gb(self):
        mgr = _make_manager_with_mock_checker()
        mgr.register_loaded_model("model1", device_id=0, size_b=7, quant="4bit")
        mem = mgr.get_loaded_memory_gb()
        assert mem > 0

    def test_get_loaded_memory_gb_by_device(self):
        mgr = _make_manager_with_mock_checker()
        mgr.register_loaded_model("model1", device_id=0, size_b=7, quant="4bit")
        mgr.register_loaded_model("model2", device_id=1, size_b=7, quant="fp16")
        mem0 = mgr.get_loaded_memory_gb(device_id=0)
        mem_all = mgr.get_loaded_memory_gb()
        assert mem0 < mem_all


class TestFindBestDevice:
    def test_find_best_device(self):
        mgr = _make_manager_with_mock_checker()
        result = mgr.find_best_device_for_model("test-model", size_b=7, quant="4bit")
        assert result == 0

    def test_find_best_device_no_fit(self):
        mgr = _make_manager_with_mock_checker()
        mgr._checker.get_best_device_for_model.return_value = None
        result = mgr.find_best_device_for_model("test-model", size_b=7, quant="fp16")
        assert result is None


class TestMemorySummary:
    def test_get_memory_summary(self):
        mgr = _make_manager_with_mock_checker()
        summary = mgr.get_memory_summary()
        assert "backend" in summary
        assert "device_count" in summary
        assert "devices" in summary
        assert "loaded_models" in summary
        assert "total_loaded_memory_gb" in summary
        assert len(summary["devices"]) == 1
        assert "device_id" in summary["devices"][0]
        assert "total_gb" in summary["devices"][0]
        assert "effective_free_gb" in summary["devices"][0]

    def test_memory_summary_with_loaded_models(self):
        mgr = _make_manager_with_mock_checker()
        mgr.register_loaded_model("model1", device_id=0, size_b=7, quant="4bit")
        summary = mgr.get_memory_summary()
        assert "model1" in summary["loaded_models"]
        assert summary["total_loaded_memory_gb"] > 0
