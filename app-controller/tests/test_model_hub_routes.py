import pytest
from unittest.mock import Mock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.model_hub import SearchResult
from core.model_pool import PoolEntry


def _setup_mocks():
    import routes.manage as manage_module

    mock_scheduler = MagicMock()
    mock_scheduler.search.return_value = [
        SearchResult(name="Qwen2.5-7B", source="hf", size_b=7, quant="4bit", feasible=True)
    ]
    mock_scheduler.recommend.return_value = {
        "recommended": SearchResult(name="Qwen2.5-7B", source="hf", size_b=7, quant="4bit", feasible=True),
        "gpu_info": {"available": True, "total_gb": 24},
        "candidates": [SearchResult(name="Qwen2.5-7B", source="hf", size_b=7, quant="4bit", feasible=True)],
    }
    manage_module.model_engine_scheduler = mock_scheduler

    mock_dl_mgr = MagicMock()
    mock_dl_mgr.create_task.return_value = {
        "task_id": "test-123", "status": "pending",
        "model_name": "Qwen2.5-7B", "source": "hf"
    }
    mock_dl_mgr.get_status.return_value = {
        "task_id": "test-123", "status": "pending", "progress_pct": 0
    }
    mock_dl_mgr.cancel_task.return_value = {"cancelled": True}
    mock_dl_mgr.list_tasks.return_value = []
    manage_module.download_task_manager = mock_dl_mgr

    entry = PoolEntry(
        name="Qwen2.5-7B", source="local",
        local_path="/mnt/pve_models/Qwen2.5-7B",
        download_status="completed"
    )
    mock_pool_mgr = MagicMock()
    mock_pool_mgr.get_pool_list.return_value = [{"name": "Qwen2.5-7B", "source": "local"}]
    mock_pool_mgr.get_pool_detail.return_value = {"name": "Qwen2.5-7B", "source": "local"}
    mock_pool_mgr.load_model.return_value = {
        "success": True, "model": "Qwen2.5-7B", "engine": "vllm", "port": 8000
    }
    mock_pool_mgr.delete_model.return_value = {"deleted": True}
    mock_pool_mgr._pool = {"Qwen2.5-7B": entry}
    manage_module.model_pool_manager = mock_pool_mgr

    mock_gpu_mgr = MagicMock()
    mock_gpu_mgr.check_model_feasibility.return_value = {
        "feasible": True, "available_gb": 16,
        "required_gb": 14, "safety_margin_gb": 1,
        "gpu_available": True
    }
    manage_module.gpu_memory_manager = mock_gpu_mgr

    return mock_scheduler, mock_dl_mgr, mock_pool_mgr, mock_gpu_mgr


@pytest.fixture
def app_client():
    _setup_mocks()
    from routes.manage import manage_router
    app = FastAPI()
    app.include_router(manage_router)
    return TestClient(app)


class TestSearchRoute:
    def test_search_returns_results(self, app_client):
        resp = app_client.get("/manage/models/search?keyword=qwen&source=all")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert data["keyword"] == "qwen"
        assert data["source"] == "all"

    def test_search_empty_keyword_returns_400(self, app_client):
        resp = app_client.get("/manage/models/search?keyword=&source=all")
        assert resp.status_code == 400


class TestRecommendRoute:
    def test_recommend_returns_result(self, app_client):
        resp = app_client.get("/manage/gpu/recommend?keyword=qwen")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommended" in data
        assert "gpu_info" in data
        assert "candidates" in data


class TestMemoryCheckRoute:
    def test_memory_check_returns_feasibility(self, app_client):
        resp = app_client.post("/manage/gpu/memory-check/Qwen2.5-7B-Instruct-4bit")
        assert resp.status_code == 200
        data = resp.json()
        assert "feasible" in data

    def test_memory_check_no_size_returns_404(self, app_client):
        resp = app_client.post("/manage/gpu/memory-check/nosizemodel")
        assert resp.status_code == 404


class TestDownloadRoutes:
    def test_start_download_returns_task_id(self, app_client):
        resp = app_client.post("/manage/models/download",
                               json={"model_name": "Qwen2.5-7B", "source": "hf"})
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data

    def test_start_download_no_model_name_returns_400(self, app_client):
        resp = app_client.post("/manage/models/download",
                               json={"source": "hf"})
        assert resp.status_code == 400

    def test_get_download_status(self, app_client):
        resp = app_client.get("/manage/models/download/test-123/status")
        assert resp.status_code == 200

    def test_cancel_download(self, app_client):
        resp = app_client.delete("/manage/models/download/test-123")
        assert resp.status_code == 200

    def test_list_downloads(self, app_client):
        resp = app_client.get("/manage/models/downloads")
        assert resp.status_code == 200


class TestPoolRoutes:
    def test_pool_list(self, app_client):
        resp = app_client.get("/manage/models/pool")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "total" in data

    def test_pool_load(self, app_client):
        resp = app_client.post("/manage/models/pool/Qwen2.5-7B/load",
                               json={"engine": "vllm"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True

    def test_pool_delete(self, app_client):
        resp = app_client.delete("/manage/models/pool/Qwen2.5-7B?remove_files=false")
        assert resp.status_code == 200


class TestEndToEndChain:
    def test_search_recommend_chain(self):
        from core.model_engine_scheduler import ModelEngineScheduler

        scheduler = ModelEngineScheduler.__new__(ModelEngineScheduler)
        scheduler._config = None
        scheduler._gpu_mgr = MagicMock()
        scheduler._model_hub = MagicMock()
        scheduler._download_mgr = MagicMock()
        scheduler._model_pool = MagicMock()
        scheduler._llm_mgr = MagicMock()
        scheduler._switching_lock = MagicMock()
        scheduler._active_service = None
        scheduler._switch_history = []
        scheduler._max_history = 50

        gpu_mgr = scheduler._gpu_mgr
        gpu_mgr.get_memory_summary.return_value = {
            "backend": "mock", "device_count": 1, "devices": [],
            "loaded_models": [], "total_loaded_memory_gb": 0,
        }
        gpu_mgr.get_total_free_gb.return_value = 16.0
        gpu_mgr.check_model_feasibility.return_value = {
            "feasible": True, "available_gb": 16, "required_gb": 14
        }

        results = [SearchResult(name="Qwen2.5-7B", source="hf",
                                 size_b=7, quant="4bit", feasible=True)]
        scheduler._model_hub.search_models.return_value = results

        search_result = scheduler.search("qwen", "hf")
        assert len(search_result) == 1
        assert search_result[0].feasible is True

        recommend_result = scheduler.recommend("qwen", "hf")
        assert recommend_result["recommended_engine"] is not None
        assert "gpu_info" in recommend_result

        gpu_info = scheduler.show_gpu()
        assert gpu_info["available"] is True
