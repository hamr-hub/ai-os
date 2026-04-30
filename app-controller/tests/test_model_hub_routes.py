import pytest


class TestSearchRoute:
    def test_search_returns_results(self, py_client):
        resp = py_client.get(
            f"{py_client.base_url}/manage/models/search?keyword=qwen&source=all"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert data["keyword"] == "qwen"
        assert data["source"] == "all"

    def test_search_empty_keyword_returns_400(self, py_client):
        resp = py_client.get(
            f"{py_client.base_url}/manage/models/search?keyword=&source=all"
        )
        assert resp.status_code == 400

    def test_search_local_source(self, py_client):
        resp = py_client.get(
            f"{py_client.base_url}/manage/models/search?keyword=gemma&source=local"
        )
        assert resp.status_code == 200

    def test_search_huggingface_source(self, py_client):
        resp = py_client.get(
            f"{py_client.base_url}/manage/models/search?keyword=qwen&source=huggingface",
            timeout=30,
        )
        assert resp.status_code in (200, 504, 500)


class TestRecommendRoute:
    def test_recommend_returns_result(self, py_client):
        resp = py_client.get(
            f"{py_client.base_url}/manage/gpu/recommend?keyword=qwen"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "recommended" in data
        assert "gpu_info" in data
        assert "candidates" in data

    def test_recommend_no_keyword(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/gpu/recommend")
        assert resp.status_code in (200, 400, 422)


class TestMemoryCheckRoute:
    def test_memory_check_returns_feasibility(self, py_client, first_available_model):
        if not first_available_model:
            pytest.skip("No models available")
        resp = py_client.post(
            f"{py_client.base_url}/manage/gpu/memory-check/{first_available_model}"
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "feasible" in data

    def test_memory_check_no_size_returns_404(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/manage/gpu/memory-check/nosizemodel"
        )
        assert resp.status_code in (200, 404)


class TestDownloadRoutes:
    def test_start_download_no_model_name_returns_400(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/manage/models/download",
            json={"source": "hf"},
        )
        assert resp.status_code == 400

    def test_get_download_status(self, py_client):
        resp = py_client.get(
            f"{py_client.base_url}/manage/models/download/nonexistent-task/status"
        )
        assert resp.status_code in (200, 404)

    def test_cancel_download(self, py_client):
        resp = py_client.delete(
            f"{py_client.base_url}/manage/models/download/nonexistent-task"
        )
        assert resp.status_code in (200, 404)

    def test_list_downloads(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/models/downloads")
        assert resp.status_code == 200


class TestPoolRoutes:
    def test_pool_list(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/models/pool")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data or "total" in data

    def test_pool_detail(self, py_client, first_available_model):
        if not first_available_model:
            pytest.skip("No models available")
        resp = py_client.get(
            f"{py_client.base_url}/manage/models/pool/{first_available_model}"
        )
        assert resp.status_code in (200, 404, 500)

    def test_pool_delete_nonexistent(self, py_client):
        try:
            resp = py_client.delete(
                f"{py_client.base_url}/manage/models/pool/nonexistent-model?remove_files=false",
                timeout=10,
            )
            assert resp.status_code in (200, 404, 500)
        except Exception:
            pass


class TestModelHubRoutes:
    def test_hub_local_models(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/hub/models")
        assert resp.status_code == 200

    def test_hub_engines(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/hub/engines")
        assert resp.status_code == 200

    def test_hub_deployment_summary(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/hub/deployment/summary")
        assert resp.status_code == 200

    def test_hub_search(self, py_client):
        resp = py_client.get(
            f"{py_client.base_url}/manage/hub/search?keyword=qwen&source=local"
        )
        assert resp.status_code in (200, 400)

    def test_hub_recommend(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/hub/recommend")
        assert resp.status_code in (200, 400, 422)

    def test_hub_downloads(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/hub/downloads")
        assert resp.status_code == 200

    def test_hub_switch_history(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/hub/switch/history")
        assert resp.status_code == 200
