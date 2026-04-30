import pytest


class TestHealthEndpoints:
    def test_health_check(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("ok", "healthy", "warning", "degraded", "unhealthy")

    def test_health_check_has_health_score(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "health_score" in data
        assert isinstance(data["health_score"], (int, float))

    def test_health_detailed(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data


class TestV1Models:
    def test_list_models(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert isinstance(data["data"], list)
        if len(data["data"]) > 0:
            assert "id" in data["data"][0]

    def test_get_model_detail(self, py_client, first_available_model):
        if not first_available_model:
            pytest.skip("No models available")
        resp = py_client.get(f"{py_client.base_url}/v1/models/{first_available_model}")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data or "name" in data

    def test_v1_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/v1/status")
        assert resp.status_code == 200


class TestChatCompletions:
    def test_chat_completions_model_not_found(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/v1/chat/completions",
            json={
                "model": "nonexistent-model-xyz",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert resp.status_code in (404, 400, 500)

    def test_chat_completions_with_running_model(self, py_client, running_model):
        if not running_model:
            pytest.skip("No running model available for chat test")
        resp = py_client.post(
            f"{py_client.base_url}/v1/chat/completions",
            json={
                "model": running_model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 10,
            },
            timeout=30,
        )
        assert resp.status_code in (200, 503)


class TestGPUManagement:
    def test_get_gpu_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/gpu")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("available", "unavailable")

    def test_get_gpu_summary(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/gpu/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_get_gpu_history(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/gpu/history")
        assert resp.status_code == 200

    def test_get_gpu_processes(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/gpu/processes")
        assert resp.status_code == 200

    def test_get_gpu_enhanced(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/gpu/enhanced")
        assert resp.status_code == 200

    def test_get_gpu_realtime(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/gpu/realtime")
        assert resp.status_code == 200

    def test_gpu_memory_check(self, py_client, first_available_model):
        if not first_available_model:
            pytest.skip("No models available")
        resp = py_client.post(
            f"{py_client.base_url}/manage/gpu/memory-check/{first_available_model}"
        )
        assert resp.status_code in (200, 404)


class TestModelManagement:
    def test_get_model_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/models")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_get_model_summary(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/models/summary")
        assert resp.status_code == 200

    def test_get_aggregated_models(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/models/aggregated")
        assert resp.status_code == 200

    def test_start_model_deprecated(self, py_client):
        resp = py_client.post(f"{py_client.base_url}/manage/models/test-model/start")
        assert resp.status_code == 410
        data = resp.json()
        error_data = data.get("error", data)
        assert "replacement" in str(error_data).lower() or "deprecated" in str(error_data).lower()

    def test_stop_model_deprecated(self, py_client):
        resp = py_client.post(f"{py_client.base_url}/manage/models/test-model/stop")
        assert resp.status_code == 410
        data = resp.json()
        error_data = data.get("error", data)
        assert "replacement" in str(error_data).lower() or "deprecated" in str(error_data).lower()

    def test_switch_model_deprecated(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/manage/models/test-model/switch?test_enabled=false"
        )
        assert resp.status_code == 410
        data = resp.json()
        error_data = data.get("error", data)
        assert "replacement" in str(error_data).lower() or "deprecated" in str(error_data).lower()

    def test_get_default_model(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/default-model")
        assert resp.status_code == 200

    def test_get_model_vllm_config(self, py_client, first_available_model):
        if not first_available_model:
            pytest.skip("No models available")
        resp = py_client.get(
            f"{py_client.base_url}/manage/models/{first_available_model}/vllm-config"
        )
        assert resp.status_code in (200, 404)

    def test_get_model_vllm_params(self, py_client, first_available_model):
        if not first_available_model:
            pytest.skip("No models available")
        resp = py_client.get(
            f"{py_client.base_url}/manage/models/{first_available_model}/vllm-params"
        )
        assert resp.status_code in (200, 404)

    def test_get_model_engine_params(self, py_client, first_available_model):
        if not first_available_model:
            pytest.skip("No models available")
        resp = py_client.get(
            f"{py_client.base_url}/manage/models/{first_available_model}/engine-params"
        )
        assert resp.status_code in (200, 404)


class TestSwitchManagement:
    def test_get_switch_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/switch/status")
        assert resp.status_code == 200

    def test_switch_atomic_invalid_action(self, py_client):
        resp = py_client.post(
            f"{py_client.base_url}/manage/switch/atomic",
            json={"action": "invalid_action", "model_name": "test"},
        )
        assert resp.status_code in (400, 422)


class TestQueueAndPreload:
    def test_queue_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_preload_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/preload")
        assert resp.status_code == 200
        data = resp.json()
        assert "preloaded_models" in data or "models" in data

    def test_preload_detail_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/preload/status")
        assert resp.status_code == 200


class TestConfigManagement:
    def test_get_config(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/config")
        assert resp.status_code == 200

    def test_get_vllm_default_config(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/vllm/default-config")
        assert resp.status_code == 200


class TestServiceManagement:
    def test_service_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/service/status")
        assert resp.status_code == 200


class TestSystemStatus:
    def test_system_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/system/status")
        assert resp.status_code == 200

    def test_system_history(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/system/history")
        assert resp.status_code == 200


class TestMonitorAll:
    def test_monitor_all(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/monitor/all")
        assert resp.status_code == 200
        data = resp.json()
        assert "gpu" in data or "models" in data or "success" in data


class TestTokenStats:
    def test_token_stats(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/token/stats")
        assert resp.status_code == 200

    def test_token_history(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/token/history")
        assert resp.status_code == 200


class TestMetrics:
    def test_get_metrics(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/metrics")
        assert resp.status_code == 200

    def test_metrics_health_detail(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/metrics/health-detail")
        assert resp.status_code == 200


class TestCache:
    def test_cache_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/cache/status")
        assert resp.status_code == 200

    def test_cache_stats(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/cache/stats")
        assert resp.status_code == 200


class TestRedis:
    def test_redis_health(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/redis/health")
        assert resp.status_code == 200


class TestRateLimit:
    def test_ratelimit_config(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/ratelimit/config")
        assert resp.status_code == 200

    def test_ratelimit_stats(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/ratelimit/stats")
        assert resp.status_code == 200


class TestEngineManagement:
    def test_engine_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/engines/status")
        assert resp.status_code == 200

    def test_engine_config(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/engines/config")
        assert resp.status_code == 200

    def test_engine_param_schema(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/engines/param-schema")
        assert resp.status_code == 200


class TestScheduler:
    def test_scheduler_status(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/scheduler/status")
        assert resp.status_code == 200

    def test_scheduler_pool(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/scheduler/pool")
        assert resp.status_code == 200


class TestHealthAlert:
    def test_health_alert(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/health/alert")
        assert resp.status_code == 200


class TestWebSocketConnections:
    def test_websocket_connections(self, py_client):
        resp = py_client.get(f"{py_client.base_url}/manage/websocket/connections")
        assert resp.status_code == 200


class TestGoBackend:
    def test_go_health(self, go_client):
        resp = go_client.get(f"{go_client.base_url}/health")
        assert resp.status_code == 200
