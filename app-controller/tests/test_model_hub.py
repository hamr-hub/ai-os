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
    mgr._hf_token = kwargs.get("hf_token", None)
    mgr._ms_token = kwargs.get("ms_token", None)
    mgr._save_root = kwargs.get("save_root", "/mnt/pve_models")
    mgr._max_workers = kwargs.get("max_workers", 8)
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


class TestDownloadModelWithToken:
    def test_download_hf_with_request_token(self):
        mgr = _make_hub(hf_token="default_token")
        with patch("core.model_hub.MultiSourceModelHub._download_hf", return_value={
            "status": "completed", "local_path": "/tmp/models/Qwen", "source": "huggingface"
        }) as mock_dl:
            mgr.download_model("Qwen/Qwen2.5-7B", source="hf", hf_token="request_token")
            mock_dl.assert_called_once()
            args = mock_dl.call_args
            assert args[0][2] == "request_token" or args.kwargs.get("hf_token") == "request_token"

    def test_download_hf_with_config_token(self):
        mgr = _make_hub(hf_token="config_token")
        with patch("core.model_hub.MultiSourceModelHub._download_hf", return_value={
            "status": "completed", "local_path": "/tmp/models/Qwen", "source": "huggingface"
        }) as mock_dl:
            mgr.download_model("Qwen/Qwen2.5-7B", source="hf")
            mock_dl.assert_called_once()
            args = mock_dl.call_args
            assert args[0][2] == "config_token" or args.kwargs.get("hf_token") == "config_token"

    def test_download_hf_with_allow_patterns(self):
        mgr = _make_hub()
        with patch("core.model_hub.MultiSourceModelHub._download_hf", return_value={
            "status": "completed", "local_path": "/tmp/models/Qwen", "source": "huggingface"
        }) as mock_dl:
            mgr.download_model("Qwen/Qwen2.5-7B", source="hf", allow_patterns=["*.safetensors", "config.json"])
            mock_dl.assert_called_once()
            args = mock_dl.call_args
            assert args[0][3] == ["*.safetensors", "config.json"] or args.kwargs.get("allow_patterns") == ["*.safetensors", "config.json"]

    def test_download_hf_with_ignore_patterns(self):
        mgr = _make_hub()
        with patch("core.model_hub.MultiSourceModelHub._download_hf", return_value={
            "status": "completed", "local_path": "/tmp/models/Qwen", "source": "huggingface"
        }) as mock_dl:
            mgr.download_model("Qwen/Qwen2.5-7B", source="hf", ignore_patterns=["*.bin", "*.msgpack"])
            mock_dl.assert_called_once()
            args = mock_dl.call_args
            assert args[0][4] == ["*.bin", "*.msgpack"] or args.kwargs.get("ignore_patterns") == ["*.bin", "*.msgpack"]

    def test_download_ms_with_local_dir(self):
        mgr = _make_hub()
        with patch("core.model_hub.MultiSourceModelHub._download_ms", return_value={
            "status": "completed", "local_path": "/tmp/models/Qwen", "source": "modelscope"
        }) as mock_dl:
            mgr.download_model("Qwen/Qwen2.5-7B", source="ms", save_dir="/custom/path")
            mock_dl.assert_called_once()
            call_args = mock_dl.call_args[0] if mock_dl.call_args[0] else ()
            assert call_args[1] == "/custom/path"

    def test_download_force_download(self):
        mgr = _make_hub()
        from core.model_hub import LocalModelInfo
        mgr._local_models["Qwen2.5-7B"] = LocalModelInfo(
            name="Qwen2.5-7B", path="/mnt/pve_models/Qwen2.5-7B",
            total_size_bytes=14*1024**3, quant="fp16",
        )
        with patch("core.model_hub.MultiSourceModelHub._download_hf", return_value={
            "status": "completed", "local_path": "/mnt/pve_models/Qwen2.5-7B", "source": "huggingface"
        }) as mock_dl:
            mgr.download_model("Qwen2.5-7B", source="hf", force_download=True)
            mock_dl.assert_called_once()

    def test_download_hf_snapshot_kwargs(self):
        mgr = _make_hub(hf_token="test_token")
        with patch("huggingface_hub.snapshot_download", return_value="/tmp/models/Qwen") as mock_sd:
            result = mgr._download_hf("Qwen/Qwen2.5-7B", "/tmp/models/Qwen", hf_token="test_token", allow_patterns=["*.safetensors"], ignore_patterns=["*.bin"], max_workers=4, force_download=True)
            assert result["status"] == "completed"
            call_kwargs = mock_sd.call_args[1] if mock_sd.call_args[1] else mock_sd.call_args.kwargs
            assert call_kwargs.get("token") == "test_token"
            assert call_kwargs.get("allow_patterns") == ["*.safetensors"]
            assert call_kwargs.get("ignore_patterns") == ["*.bin"]
            assert call_kwargs.get("max_workers") == 4
            assert call_kwargs.get("force_download") == True


class TestMSResumeDownload:
    def test_ms_download_passes_resume_download(self):
        mgr = _make_hub()
        with patch("modelscope.hub.snapshot_download.snapshot_download", return_value="/tmp/models/Qwen") as mock_dl:
            result = mgr._download_ms("Qwen/Qwen2.5-7B", "/tmp/models/Qwen")
            assert result["status"] == "completed"
            call_kwargs = mock_dl.call_args[1] if mock_dl.call_args[1] else mock_dl.call_args.kwargs
            assert call_kwargs.get("resume_download") == True

    def test_ms_download_resume_false(self):
        mgr = _make_hub()
        with patch("modelscope.hub.snapshot_download.snapshot_download", return_value="/tmp/models/Qwen") as mock_dl:
            result = mgr._download_ms("Qwen/Qwen2.5-7B", "/tmp/models/Qwen", resume_download=False)
            assert result["status"] == "completed"
            call_kwargs = mock_dl.call_args[1] if mock_dl.call_args[1] else mock_dl.call_args.kwargs
            assert call_kwargs.get("resume_download") == False

    def test_ms_download_with_progress_callback(self):
        mgr = _make_hub()
        cb = Mock()
        with patch("modelscope.hub.snapshot_download.snapshot_download", return_value="/tmp/models/Qwen"):
            result = mgr._download_ms("Qwen/Qwen2.5-7B", "/tmp/models/Qwen", progress_callback=cb)
            assert result["status"] == "completed"
            cb.assert_called_with(100.0)


class TestSearchSort:
    def test_sort_by_size_asc(self):
        mgr = _make_hub()
        with patch.object(mgr, "_search_hf", return_value=[
            SearchResult(name="big", source="huggingface", size_b=70),
            SearchResult(name="small", source="huggingface", size_b=7),
            SearchResult(name="medium", source="huggingface", size_b=14),
        ]):
            results = mgr.search_models("qwen", "huggingface", 10, sort="size")
            assert results[0].size_b == 7
            assert results[1].size_b == 14
            assert results[2].size_b == 70

    def test_sort_by_size_desc(self):
        mgr = _make_hub()
        with patch.object(mgr, "_search_hf", return_value=[
            SearchResult(name="small", source="huggingface", size_b=7),
            SearchResult(name="big", source="huggingface", size_b=70),
        ]):
            results = mgr.search_models("qwen", "huggingface", 10, sort="-size")
            assert results[0].size_b == 70
            assert results[1].size_b == 7

    def test_sort_by_required_gb(self):
        mgr = _make_hub()
        with patch.object(mgr, "_search_hf", return_value=[
            SearchResult(name="m1", source="huggingface", required_gb=14),
            SearchResult(name="m2", source="huggingface", required_gb=6),
        ]):
            results = mgr.search_models("qwen", "huggingface", 10, sort="required_gb")
            assert results[0].required_gb == 6
            assert results[1].required_gb == 14

    def test_sort_by_feasible(self):
        mgr = _make_hub()
        with patch.object(mgr, "_search_hf", return_value=[
            SearchResult(name="bad", source="huggingface", feasible=False),
            SearchResult(name="good", source="huggingface", feasible=True),
        ]):
            results = mgr.search_models("qwen", "huggingface", 10, sort="-feasible")
            assert results[0].feasible == True
            assert results[1].feasible == False

    def test_sort_by_downloads(self):
        mgr = _make_hub()
        with patch.object(mgr, "_search_hf", return_value=[
            SearchResult(name="popular", source="huggingface", downloads=5000),
            SearchResult(name="rare", source="huggingface", downloads=100),
        ]):
            results = mgr.search_models("qwen", "huggingface", 10, sort="-downloads")
            assert results[0].downloads == 5000
            assert results[1].downloads == 100

    def test_sort_none_no_sorting(self):
        mgr = _make_hub()
        with patch.object(mgr, "_search_hf", return_value=[
            SearchResult(name="b", source="huggingface", size_b=70),
            SearchResult(name="a", source="huggingface", size_b=7),
        ]):
            results = mgr.search_models("qwen", "huggingface", 10)
            assert results[0].name == "b"
            assert results[1].name == "a"
