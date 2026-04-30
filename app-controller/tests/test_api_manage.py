import pytest


class TestSwitchAtomic:
    def test_switch_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/switch/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "is_switching" in data or "status" in data

    def test_switch_start_missing_model(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/manage/switch/atomic",
            json={"action": "start"},
        )
        assert resp.status_code in (400, 422)

    def test_switch_stop_no_running_model(self, py_client, running_model):
        if running_model:
            pytest.skip("A model is running, skip stop test")
        resp = py_client.post(
            f"{py_client.base_url}/manage/switch/atomic",
            json={"action": "stop", "model_name": "nonexistent"},
        )
        assert resp.status_code in (200, 400, 404, 500)

    def test_switch_cancel_no_active(self, py_client):
        resp = py_client.delete(f"{py_client.base_url}/manage/switch/cancel")
        assert resp.status_code in (200, 404)


class TestPreload:
    def test_preload_all(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/preload/all")
        assert resp.status_code == 200

    def test_preload_model_not_available(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/manage/preload/nonexistent-model-xyz"
        )
        assert resp.status_code in (200, 404, 400)

    def test_preload_enable(self, py_client, first_available_model):
        if not first_available_model:
            pytest.skip("No models available")
        resp = py_client.post(
            f"{py_client.base_url}/manage/preload/{first_available_model}/enable"
        )
        assert resp.status_code in (200, 404)

    def test_preload_disable(self, py_client, first_available_model):
        if not first_available_model:
            pytest.skip("No models available")
        resp = py_client.post(
            f"{py_client.base_url}/manage/preload/{first_available_model}/disable"
        )
        assert resp.status_code in (200, 404)


class TestDefaultModel:
    def test_get_default_model(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/default-model")
        assert resp.status_code == 200

    def test_clear_default_model(self, py_client):
        resp = py_client.delete(f"{py_client.base_url}/manage/default-model")
        assert resp.status_code in (200, 404)


class TestVLLMMetrics:
    def test_vllm_metrics(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/vllm/metrics")
        assert resp.status_code == 200


class TestGPUHistoryConfig:
    def test_gpu_history_config(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/manage/gpu/history/config",
            json={"interval_seconds": 60, "max_entries": 1000},
        )
        assert resp.status_code in (200, 400)


class TestConfigReload:
    def test_config_reload(self, py_client):
        resp = py_client.post(f"{py_client.base_url}/manage/config/reload")
        assert resp.status_code in (200, 500)


class TestCacheRefresh:
    def test_cache_refresh(self, py_client):
        resp = py_client.post(f"{py_client.base_url}/manage/cache/refresh")
        assert resp.status_code == 200


class TestMetricsReset:
    def test_metrics_reset(self, py_client):
        resp = py_client.post(f"{py_client.base_url}/manage/metrics/reset")
        assert resp.status_code == 200
