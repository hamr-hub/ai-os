import pytest
from unittest.mock import Mock, patch, MagicMock
from core.model_pool import ModelPoolManager, PoolEntry


def _make_pool_mgr(**kwargs):
    mgr = ModelPoolManager.__new__(ModelPoolManager)
    mgr._config = kwargs.get("config", None)
    mgr._gpu_memory_manager = kwargs.get("gpu_memory_manager", None)
    mgr._llm_service_manager = kwargs.get("llm_service_manager", None)
    mgr._model_hub = kwargs.get("model_hub", None)
    mgr._pool = {}
    mgr._model_base_path = kwargs.get("model_base_path", "/mnt/pve_models")
    mgr._config_path = ""
    return mgr


class TestScanAndSync:
    @patch("os.path.isdir", return_value=True)
    @patch("os.listdir", return_value=["Qwen3-235B-AWQ", "Gemma-4-31B"])
    @patch("os.path.isdir")
    def test_scan_local_models(self, mock_isdir_twice, mock_listdir, mock_isdir):
        mgr = _make_pool_mgr(model_base_path="/mnt/pve_models")
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["Qwen3-235B-AWQ", "Gemma-4-31B"]), \
             patch("os.path.isdir") as mock_sub_isdir:
            mock_sub_isdir.return_value = True
            count = mgr.scan_and_sync()
            assert count >= 2
            assert "Qwen3-235B-AWQ" in mgr._pool

    @patch("os.path.isdir", return_value=True)
    @patch("os.listdir", return_value=[])
    def test_scan_empty_dir(self, mock_listdir, mock_isdir):
        mgr = _make_pool_mgr(model_base_path="/mnt/pve_models")
        count = mgr.scan_and_sync()
        assert count == 0


class TestRegisterFromDownload:
    def test_register_downloaded_model(self):
        mgr = _make_pool_mgr()
        mgr.register_from_download(
            model_name="Qwen2.5-7B-Instruct",
            local_path="/mnt/pve_models/Qwen2.5-7B-Instruct",
            source="huggingface",
            size_b=7,
            quant="fp16",
        )
        assert "Qwen2.5-7B-Instruct" in mgr._pool
        entry = mgr._pool["Qwen2.5-7B-Instruct"]
        assert entry.source == "huggingface"
        assert entry.size_b == 7
        assert entry.quant == "fp16"
        assert entry.download_status == "completed"


class TestRegisterFromSearch:
    def test_register_search_result(self):
        mgr = _make_pool_mgr()
        mgr.register_from_search(
            model_name="Qwen2.5-7B-Instruct",
            source="modelscope",
            size_b=7,
            quant="4bit",
            required_gb=5.9,
            feasible=True,
        )
        assert "Qwen2.5-7B-Instruct" in mgr._pool
        entry = mgr._pool["Qwen2.5-7B-Instruct"]
        assert entry.download_status == "not_downloaded"
        assert entry.feasible is True


class TestGetPoolList:
    def test_list_all_models(self):
        mgr = _make_pool_mgr()
        mgr._pool = {
            "Qwen2.5-7B": PoolEntry(name="Qwen2.5-7B", source="local", local_path="/mnt/pve_models/Qwen2.5-7B", download_status="completed"),
            "Gemma-4-31B": PoolEntry(name="Gemma-4-31B", source="huggingface", local_path="/mnt/pve_models/Gemma-4-31B", download_status="completed"),
        }
        result = mgr.get_pool_list()
        assert len(result) == 2
        assert isinstance(result[0], dict)

    def test_list_with_filter(self):
        mgr = _make_pool_mgr()
        mgr._pool = {
            "Qwen2.5-7B": PoolEntry(name="Qwen2.5-7B", source="local", local_path="/mnt/pve_models/Qwen2.5-7B", download_status="completed"),
            "Gemma-4-31B": PoolEntry(name="Gemma-4-31B", source="huggingface", download_status="not_downloaded"),
        }
        result = mgr.get_pool_list(filter="downloaded")
        assert len(result) == 1
        assert result[0]["name"] == "Qwen2.5-7B"


class TestDeleteModel:
    def test_delete_stopped_model(self):
        mgr = _make_pool_mgr()
        mgr._pool = {
            "Qwen2.5-7B": PoolEntry(name="Qwen2.5-7B", source="local", local_path="/mnt/pve_models/Qwen2.5-7B", download_status="completed", running_status="stopped"),
        }
        result = mgr.delete_model("Qwen2.5-7B")
        assert result["deleted"] is True
        assert "Qwen2.5-7B" not in mgr._pool

    def test_delete_running_model_fails(self):
        mgr = _make_pool_mgr()
        mgr._pool = {
            "Qwen2.5-7B": PoolEntry(name="Qwen2.5-7B", source="local", running_status="running"),
        }
        result = mgr.delete_model("Qwen2.5-7B")
        assert result["deleted"] is False
        assert "running" in result.get("reason", "")

    def test_delete_nonexistent_model(self):
        mgr = _make_pool_mgr()
        result = mgr.delete_model("nonexistent")
        assert result["deleted"] is False
