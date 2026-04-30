import pytest
from unittest.mock import Mock, patch, MagicMock
from core.model_hub import MultiSourceModelHub, SearchResult


def _make_hub(**kwargs):
    mgr = MultiSourceModelHub.__new__(MultiSourceModelHub)
    mgr._config = kwargs.get("config", None)
    mgr._gpu_memory_manager = kwargs.get("gpu_memory_manager", None)
    mgr._local_models = {}
    mgr._model_metadata = {}
    mgr._hf_endpoint = kwargs.get("hf_endpoint", "https://hf-mirror.com")
    mgr._save_root = kwargs.get("save_root", "/mnt/pve_models")
    mgr._initialized = True
    return mgr


class TestParseSize:
    def test_parse_7b(self):
        mgr = _make_hub()
        assert mgr._parse_size("Qwen2.5-7B-Instruct") == 7

    def test_parse_8b(self):
        mgr = _make_hub()
        assert mgr._parse_size("Llama-3-8B") == 8

    def test_parse_235b(self):
        mgr = _make_hub()
        assert mgr._parse_size("Qwen3-235B-A22B") == 235

    def test_parse_31b(self):
        mgr = _make_hub()
        assert mgr._parse_size("Gemma-4-31B") == 31

    def test_parse_no_size(self):
        mgr = _make_hub()
        assert mgr._parse_size("some-model") is None

    def test_parse_size_with_dot(self):
        mgr = _make_hub()
        assert mgr._parse_size("Qwen3.6-35B") == 35


class TestParseQuant:
    def test_parse_4bit(self):
        mgr = _make_hub()
        assert mgr._parse_quant("Qwen2.5-7B-Instruct-4bit") == "4bit"

    def test_parse_int4_normalizes_to_4bit(self):
        mgr = _make_hub()
        assert mgr._parse_quant("model-int4") == "4bit"

    def test_parse_8bit(self):
        mgr = _make_hub()
        assert mgr._parse_quant("model-8bit") == "8bit"

    def test_parse_int8_normalizes_to_8bit(self):
        mgr = _make_hub()
        assert mgr._parse_quant("model-int8") == "8bit"

    def test_parse_fp16(self):
        mgr = _make_hub()
        assert mgr._parse_quant("model-fp16") == "fp16"

    def test_parse_awq(self):
        mgr = _make_hub()
        assert mgr._parse_quant("Qwen3-235B-A22B-AWQ") == "awq"

    def test_parse_gptq(self):
        mgr = _make_hub()
        assert mgr._parse_quant("model-GPTQ") == "gptq"

    def test_parse_gguf(self):
        mgr = _make_hub()
        assert mgr._parse_quant("model-GGUF") == "gguf"

    def test_parse_no_quant(self):
        mgr = _make_hub()
        assert mgr._parse_quant("Qwen2.5-7B-Instruct") is None


class TestSearchModels:
    def test_search_huggingface(self):
        mgr = _make_hub()
        mock_gpu_mgr = MagicMock()
        mock_gpu_mgr.check_model_feasibility.return_value = {
            "feasible": True, "available_gb": 20, "required_gb": 6
        }
        mgr._gpu_memory_manager = mock_gpu_mgr
        mock_model = MagicMock()
        mock_model.id = "Qwen/Qwen2.5-7B-Instruct"
        mock_hf_api = MagicMock()
        mock_hf_api.list_models.return_value = [mock_model]
        with patch.object(mgr, "_search_hf", return_value=[
            SearchResult(name="Qwen/Qwen2.5-7B-Instruct", source="huggingface", size_b=7, quant="fp16")
        ]):
            results = mgr.search_models("qwen", "huggingface", 5)
            assert len(results) >= 1

    def test_search_modelscope(self):
        mgr = _make_hub()
        with patch.object(mgr, "_search_ms", return_value=[
            SearchResult(name="Qwen2.5-7B", source="modelscope")
        ]):
            results = mgr.search_models("qwen", "modelscope", 5)
            assert isinstance(results, list)
            assert results[0].source == "modelscope"

    def test_search_all_aggregates(self):
        mgr = _make_hub()
        with patch.object(mgr, "_search_hf", return_value=[
            SearchResult(name="Qwen2.5-7B", source="huggingface")
        ]):
            with patch.object(mgr, "_search_ms", return_value=[
                SearchResult(name="Qwen2.5-7B-MS", source="modelscope")
            ]):
                results = mgr.search_models("qwen", "all", 5)
                assert len(results) >= 2

    def test_search_local(self):
        mgr = _make_hub()
        from core.model_hub import LocalModelInfo
        mgr._local_models["Qwen2.5-7B"] = LocalModelInfo(
            name="Qwen2.5-7B", path="/mnt/pve_models/Qwen2.5-7B",
            total_size_bytes=14*1024**3, quant="fp16",
        )
        mock_gpu_mgr = MagicMock()
        mock_gpu_mgr.check_model_feasibility.return_value = {"feasible": True}
        mgr._gpu_memory_manager = mock_gpu_mgr
        with patch.object(mgr, "_search_local", return_value=[
            SearchResult(name="Qwen2.5-7B", source="local", size_b=7)
        ]):
            results = mgr.search_models("qwen", "local", 5)
            assert len(results) >= 1


class TestGetModelLocalPath:
    def test_local_model_found(self):
        mgr = _make_hub()
        from core.model_hub import LocalModelInfo
        mgr._local_models["Qwen2.5-7B"] = LocalModelInfo(
            name="Qwen2.5-7B", path="/mnt/pve_models/Qwen2.5-7B",
            total_size_bytes=14*1024**3, quant="fp16",
        )
        result = mgr.get_model_local_path("Qwen2.5-7B")
        assert result == "/mnt/pve_models/Qwen2.5-7B"

    def test_local_model_not_found(self):
        mgr = _make_hub()
        result = mgr.get_model_local_path("nonexistent-model")
        assert result is None


class TestIsModelLocal:
    def test_model_is_local(self):
        mgr = _make_hub()
        from core.model_hub import LocalModelInfo
        mgr._local_models["Qwen2.5-7B"] = LocalModelInfo(
            name="Qwen2.5-7B", path="/mnt/pve_models/Qwen2.5-7B",
            total_size_bytes=14*1024**3, quant="fp16",
        )
        assert mgr.is_model_local("Qwen2.5-7B") is True

    def test_model_not_local(self):
        mgr = _make_hub()
        assert mgr.is_model_local("nonexistent") is False


class TestGetSourceInfo:
    def test_get_source_info(self):
        mgr = _make_hub()
        info = mgr.get_source_info()
        assert "sources" in info
        assert "save_root" in info
        assert "hf_endpoint" in info
