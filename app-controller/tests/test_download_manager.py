import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio
from core.download_manager import DownloadTaskManager, DownloadTask


def _make_dl_mgr(**kwargs):
    mgr = DownloadTaskManager.__new__(DownloadTaskManager)
    mgr._config = kwargs.get("config", None)
    mgr._model_hub = kwargs.get("model_hub", MagicMock())
    mgr._model_pool = kwargs.get("model_pool", MagicMock())
    mgr._ws_manager = kwargs.get("ws_manager", None)
    mgr._sse_push = kwargs.get("sse_push", None)
    mgr._tasks = {}
    mgr._active_count = 0
    mgr._max_concurrent = 3
    mgr._disk_warning_pct = 0.85
    mgr._disk_abort_pct = 0.95
    mgr._save_root = kwargs.get("save_root", "/tmp/models")
    mgr._progress_callbacks = []
    mgr._semaphore = None
    return mgr


class TestCreateTask:
    def test_create_task_basic(self):
        model_hub = MagicMock()
        model_hub.is_model_local.return_value = False
        mgr = _make_dl_mgr(model_hub=model_hub)
        result = mgr.create_task("Qwen2.5-7B-Instruct", "hf", auto_start=False)
        assert "task_id" in result
        assert result["status"] == "pending"

    def test_create_task_model_already_exists(self):
        model_hub = MagicMock()
        model_hub.is_model_local.return_value = True
        model_hub.get_model_local_path.return_value = "/tmp/models/Qwen2.5-7B"
        mgr = _make_dl_mgr(model_hub=model_hub)
        result = mgr.create_task("Qwen2.5-7B-Instruct", "hf")
        assert result.get("status") == "already_exists"
        assert "local_path" in result

    def test_create_task_disk_space_abort(self):
        model_hub = MagicMock()
        model_hub.is_model_local.return_value = False
        mgr = _make_dl_mgr(model_hub=model_hub)
        with patch.object(mgr, "_check_disk_space", return_value={
            "ok": False, "reason": "disk_full", "pct": 97,
        }):
            result = mgr.create_task("Qwen2.5-7B-Instruct", "hf")
            assert result.get("status") == "error"


class TestGetStatus:
    def test_get_status_existing_task(self):
        mgr = _make_dl_mgr(model_hub=None)
        task = DownloadTask(
            task_id="abc123", model_name="Qwen2.5-7B",
            source="hf", status="downloading", progress_pct=45.0,
            speed_mbps=10.5, eta_seconds=120,
        )
        mgr._tasks["abc123"] = task
        result = mgr.get_status("abc123")
        assert result["task_id"] == "abc123"
        assert result["status"] == "downloading"

    def test_get_status_nonexistent_task(self):
        mgr = _make_dl_mgr(model_hub=None)
        result = mgr.get_status("nonexistent")
        assert result is None


class TestCancelTask:
    def test_cancel_existing_task(self):
        mgr = _make_dl_mgr(model_hub=None)
        task = DownloadTask(
            task_id="abc123", model_name="Qwen2.5-7B",
            source="hf", status="downloading",
        )
        mgr._tasks["abc123"] = task
        result = mgr.cancel_task("abc123")
        assert result["cancelled"] is True

    def test_cancel_nonexistent_task(self):
        mgr = _make_dl_mgr(model_hub=None)
        result = mgr.cancel_task("nonexistent")
        assert result["cancelled"] is False

    def test_cancel_completed_task(self):
        mgr = _make_dl_mgr(model_hub=None)
        task = DownloadTask(
            task_id="abc123", model_name="Qwen2.5-7B",
            source="hf", status="completed",
        )
        mgr._tasks["abc123"] = task
        result = mgr.cancel_task("abc123")
        assert result["cancelled"] is False


class TestListTasks:
    def test_list_all_tasks(self):
        mgr = _make_dl_mgr(model_hub=None)
        mgr._tasks = {
            "t1": DownloadTask(task_id="t1", model_name="A", source="hf", status="downloading"),
            "t2": DownloadTask(task_id="t2", model_name="B", source="ms", status="completed"),
        }
        result = mgr.list_tasks()
        assert len(result) == 2

    def test_list_tasks_with_filter(self):
        mgr = _make_dl_mgr(model_hub=None)
        mgr._tasks = {
            "t1": DownloadTask(task_id="t1", model_name="A", source="hf", status="downloading"),
            "t2": DownloadTask(task_id="t2", model_name="B", source="ms", status="completed"),
        }
        result = mgr.list_tasks(status_filter="completed")
        assert len(result) == 1


class TestGetStats:
    def test_get_stats(self):
        mgr = _make_dl_mgr(model_hub=None)
        mgr._tasks = {
            "t1": DownloadTask(task_id="t1", model_name="A", source="hf", status="downloading"),
        }
        stats = mgr.get_stats()
        assert stats["total_tasks"] == 1
        assert "by_status" in stats


class TestCreateTaskWithNewParams:
    def test_create_task_with_hf_token(self):
        model_hub = MagicMock()
        model_hub.is_model_local.return_value = False
        mgr = _make_dl_mgr(model_hub=model_hub)
        result = mgr.create_task("Qwen2.5-7B-Instruct", "hf", auto_start=False, hf_token="hf_test_token")
        assert "task_id" in result
        task = mgr._tasks[result["task_id"]]
        assert task.hf_token == "hf_test_token"

    def test_create_task_with_allow_patterns(self):
        model_hub = MagicMock()
        model_hub.is_model_local.return_value = False
        mgr = _make_dl_mgr(model_hub=model_hub)
        result = mgr.create_task("Qwen2.5-7B-Instruct", "hf", auto_start=False, allow_patterns=["*.safetensors", "config.json"])
        task = mgr._tasks[result["task_id"]]
        assert task.allow_patterns == ["*.safetensors", "config.json"]

    def test_create_task_with_ignore_patterns(self):
        model_hub = MagicMock()
        model_hub.is_model_local.return_value = False
        mgr = _make_dl_mgr(model_hub=model_hub)
        result = mgr.create_task("Qwen2.5-7B-Instruct", "hf", auto_start=False, ignore_patterns=["*.bin"])
        task = mgr._tasks[result["task_id"]]
        assert task.ignore_patterns == ["*.bin"]

    def test_create_task_with_max_workers(self):
        model_hub = MagicMock()
        model_hub.is_model_local.return_value = False
        mgr = _make_dl_mgr(model_hub=model_hub)
        result = mgr.create_task("Qwen2.5-7B-Instruct", "hf", auto_start=False, max_workers=4)
        task = mgr._tasks[result["task_id"]]
        assert task.max_workers == 4

    def test_create_task_with_force_download(self):
        model_hub = MagicMock()
        model_hub.is_model_local.return_value = False
        mgr = _make_dl_mgr(model_hub=model_hub)
        result = mgr.create_task("Qwen2.5-7B-Instruct", "hf", auto_start=False, force_download=True)
        task = mgr._tasks[result["task_id"]]
        assert task.force_download == True

    def test_create_task_default_params(self):
        model_hub = MagicMock()
        model_hub.is_model_local.return_value = False
        mgr = _make_dl_mgr(model_hub=model_hub)
        result = mgr.create_task("Qwen2.5-7B-Instruct", "hf", auto_start=False)
        task = mgr._tasks[result["task_id"]]
        assert task.hf_token is None
        assert task.allow_patterns is None
        assert task.ignore_patterns is None
        assert task.max_workers is None
        assert task.force_download == False
