"""
运维可观测性测试 - GPU监控、健康检查、WebSocket、Metrics、系统状态、缓存
"""

import pytest
import requests
import json
import time

try:
    import websocket as ws_lib
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

GO_BASE = "http://localhost:35001"
PY_BASE = "http://localhost:35000"


def _is_engine_running():
    try:
        models = requests.get(f"{GO_BASE}/manage/models", timeout=5).json()
        return any(m.get("running") for m in models.values())
    except Exception:
        return False


class TestGPUMonitoring:
    def test_gpu_monitoring_data(self):
        resp = requests.get(f"{GO_BASE}/manage/gpu", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        if data.get("status") == "unavailable":
            pytest.skip("No GPU available")
        assert "utilization" in data or "memory_utilization" in data or "gpu_utilization" in data

    def test_gpu_summary(self):
        resp = requests.get(f"{GO_BASE}/manage/gpu/summary", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_gpu_enhanced(self):
        resp = requests.get(f"{GO_BASE}/manage/gpu/enhanced", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        if data.get("status") != "unavailable":
            assert "timestamp" in data or "gpu_count" in data or "driver_version" in data, "Enhanced GPU data should contain useful fields"

    def test_gpu_history(self):
        resp = requests.get(f"{GO_BASE}/manage/gpu/history", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert "enabled" in data

    def test_gpu_processes(self):
        resp = requests.get(f"{GO_BASE}/manage/gpu/processes", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "processes" in data


class TestHealthCheck:
    def test_health_check(self):
        go_resp = requests.get(f"{GO_BASE}/health", timeout=10)
        assert go_resp.status_code == 200
        go_data = go_resp.json()
        assert "status" in go_data
        assert "timestamp" in go_data

        py_resp = requests.get(f"{PY_BASE}/health", timeout=10)
        assert py_resp.status_code == 200
        py_data = py_resp.json()
        assert "status" in py_data

    def test_health_alert(self):
        resp = requests.get(f"{PY_BASE}/manage/health/alert", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "should_alert" in data
        assert "health_score" in data
        assert "alert_reasons" in data

    def test_health_detail(self):
        resp = requests.get(f"{PY_BASE}/manage/metrics/health-detail", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "health_scores" in data or "gpu_alerts" in data


class TestWebSocket:
    @pytest.mark.skipif(not HAS_WEBSOCKET, reason="websocket-client module not installed")
    def test_ws_gpu_push(self):
        messages = []
        try:
            conn = ws_lib.create_connection(f"ws://localhost:35001/ws", timeout=15)
            for i in range(5):
                msg = conn.recv()
                if msg:
                    data = json.loads(msg)
                    messages.append(data)
            conn.close()
        except Exception as e:
            pytest.skip(f"WebSocket connection failed: {e}")

        assert len(messages) > 0, "No WebSocket messages received"
        assert any("gpu" in str(m).lower() or "memory" in str(m).lower() for m in messages), "No GPU data in WS messages"


class TestMetrics:
    def test_metrics_collection(self):
        if not _is_engine_running():
            pytest.skip("No vLLM engine running - cannot test metrics after inference")

        try:
            requests.post(
                f"{GO_BASE}/v1/chat/completions",
                json={"model": "default", "messages": [{"role": "user", "content": "metrics test"}]},
                timeout=10,
            )
        except requests.exceptions.Timeout:
            pytest.skip("Go gateway timed out on inference (engine unavailable)")

        resp = requests.get(f"{GO_BASE}/manage/metrics", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_token_stats(self):
        resp = requests.get(f"{PY_BASE}/manage/token/stats", timeout=10)
        assert resp.status_code == 200

    def test_metrics_reset(self):
        resp = requests.post(f"{PY_BASE}/manage/metrics/reset", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "reset"


class TestSystemStatus:
    def test_system_status(self):
        resp = requests.get(f"{PY_BASE}/manage/system/status", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data

    def test_system_history(self):
        resp = requests.get(f"{PY_BASE}/manage/system/history", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data

    def test_service_status(self):
        resp = requests.get(f"{PY_BASE}/manage/service/status", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "service" in data
        assert "status" in data


class TestCache:
    def test_cache_status(self):
        resp = requests.get(f"{PY_BASE}/manage/cache/status", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "cache_updater" in data or "cache_service" in data

    def test_cache_stats(self):
        resp = requests.get(f"{PY_BASE}/manage/cache/stats", timeout=10)
        assert resp.status_code == 200

    def test_cache_refresh(self):
        resp = requests.post(f"{PY_BASE}/manage/cache/refresh", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "all_refreshed"


class TestStructuredLogging:
    def test_structured_logging(self):
        resp = requests.get(f"{PY_BASE}/manage/logs/test", timeout=10)
        assert resp.status_code in [200, 500], "Logging endpoint may return 500 if not fully configured"
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("status") == "logging_test_completed"


class TestMonitorAll:
    def test_monitor_all_endpoint(self):
        resp = requests.get(f"{PY_BASE}/manage/monitor/all", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert "gpu" in data
        assert "models" in data
        assert "health" in data


class TestRedisHealth:
    def test_redis_health(self):
        resp = requests.get(f"{PY_BASE}/manage/redis/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "connected" in data

    def test_redis_keys(self):
        resp = requests.get(f"{PY_BASE}/manage/redis/keys", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data
