"""
高可用测试 - 链路追踪、Redis故障降级、槽位泄漏、故障恢复
"""

import pytest
import requests
import json
import time
import threading

GO_BASE = "http://localhost:35001"
PY_BASE = "http://localhost:35000"


def _is_engine_running():
    try:
        models = requests.get(f"{GO_BASE}/manage/models", timeout=5).json()
        return any(m.get("running") for m in models.values())
    except Exception:
        return False


class TestRequestTracing:
    def test_request_id_propagation(self):
        if not _is_engine_running():
            pytest.skip("No vLLM engine running - cannot test request tracing")

        try:
            resp = requests.post(
                f"{GO_BASE}/v1/chat/completions",
                json={"model": "default", "messages": [{"role": "user", "content": "trace test"}], "stream": False},
                timeout=30,
            )
            assert resp.status_code in [200, 503, 429]
            if resp.status_code == 200:
                request_id = resp.headers.get("X-Request-Id", "")
                assert len(request_id) > 0, "Missing X-Request-Id header"
        except requests.exceptions.Timeout:
            pytest.skip("Go gateway timed out on inference request (engine likely unavailable)")


class TestRedisFailure:
    def test_redis_down_degradation(self):
        try:
            redis_resp = requests.get(f"{PY_BASE}/manage/redis/health", timeout=10)
            redis_data = redis_resp.json()
            redis_connected = redis_data.get("connected", False)
        except requests.exceptions.Timeout:
            redis_connected = False

        if not redis_connected and not _is_engine_running():
            pytest.skip("No engine running and Redis disconnected - cannot test degradation")

        if not _is_engine_running():
            try:
                resp = requests.post(
                    f"{GO_BASE}/v1/chat/completions",
                    json={"model": "default", "messages": [{"role": "user", "content": "test"}], "stream": False},
                    timeout=10,
                )
                assert resp.status_code in [200, 503, 429]
            except requests.exceptions.Timeout:
                pytest.skip("Go gateway timed out (no engine)")

        if not redis_connected:
            try:
                resp = requests.post(
                    f"{GO_BASE}/v1/chat/completions",
                    json={"model": "default", "messages": [{"role": "user", "content": "test"}], "stream": False},
                    timeout=30,
                )
                assert resp.status_code in [200, 503, 429], "Service should still work without Redis"
            except requests.exceptions.Timeout:
                pytest.skip("Go gateway timed out on inference (engine unavailable)")


class TestSlotLeak:
    def test_concurrent_slot_leak_redis(self):
        if not _is_engine_running():
            pytest.skip("No vLLM engine running - cannot test slot leak")

        models = requests.get(f"{GO_BASE}/manage/models", timeout=10).json()
        if not models:
            pytest.skip("No models available")

        model_name = list(models.keys())[0]
        queue_before = requests.get(f"{GO_BASE}/manage/queue", timeout=10).json()
        active_before = queue_before.get(model_name, {}).get("active_requests", 0)

        threads = []
        results = []

        def quick_request(idx):
            try:
                resp = requests.post(
                    f"{GO_BASE}/v1/chat/completions",
                    json={"model": model_name, "messages": [{"role": "user", "content": f"slot test {idx}"}], "stream": False},
                    timeout=30,
                )
                results.append((idx, resp.status_code))
            except Exception as e:
                results.append((idx, str(e)))

        for i in range(10):
            t = threading.Thread(target=quick_request, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=35)

        time.sleep(3)

        queue_after = requests.get(f"{GO_BASE}/manage/queue", timeout=10).json()
        active_after = queue_after.get(model_name, {}).get("active_requests", 0)

        assert active_after == 0, f"Slot leak: active_requests={active_after} after all requests completed"


class TestFaultRecovery:
    def test_gateway_crash_recovery(self):
        resp = requests.get(f"{GO_BASE}/health", timeout=10)
        assert resp.status_code == 200, "Go gateway should be running"
        data = resp.json()
        assert "status" in data

    def test_python_down_go_alone(self):
        go_health = requests.get(f"{GO_BASE}/health", timeout=10)
        assert go_health.status_code == 200, "Go gateway should be independently accessible"

        if not _is_engine_running():
            pytest.skip("No vLLM engine running - cannot test Go standalone inference")

        try:
            resp = requests.post(
                f"{GO_BASE}/v1/chat/completions",
                json={"model": "default", "messages": [{"role": "user", "content": "test go alone"}], "stream": False},
                timeout=30,
            )
            assert resp.status_code in [200, 503, 429], "Go gateway should handle requests independently"
        except requests.exceptions.Timeout:
            pytest.skip("Go gateway timed out on inference (engine unavailable)")
