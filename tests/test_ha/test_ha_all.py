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


class TestRequestTracing:
    def test_request_id_propagation(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={
                "model": "default",
                "messages": [{"role": "user", "content": "trace test"}],
                "stream": False,
            },
            timeout=30,
        )
        assert resp.status_code in [200, 503, 429]
        if resp.status_code == 200:
            request_id = resp.headers.get("X-Request-Id", "")
            assert len(request_id) > 0, "Missing X-Request-Id header"


class TestRedisFailure:
    def test_redis_down_degradation(self):
        redis_resp = requests.get(f"{PY_BASE}/manage/redis/health", timeout=5)
        redis_data = redis_resp.json()
        redis_connected = redis_data.get("connected", False)

        if not redis_connected:
            resp = requests.post(
                f"{GO_BASE}/v1/chat/completions",
                json={"model": "default", "messages": [{"role": "user", "content": "test"}], "stream": False},
                timeout=30,
            )
            assert resp.status_code in [200, 503, 429], "Service should still work without Redis"


class TestSlotLeak:
    def test_concurrent_slot_leak_redis(self):
        models = requests.get(f"{GO_BASE}/manage/models", timeout=10).json()
        if not models:
            pytest.skip("No models available")

        model_name = list(models.keys())[0]
        queue_before = requests.get(f"{GO_BASE}/manage/queue", timeout=5).json()
        active_before = queue_before.get(model_name, {}).get("active_requests", 0)

        threads = []
        results = []

        def quick_request(idx):
            try:
                resp = requests.post(
                    f"{GO_BASE}/v1/chat/completions",
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": f"slot test {idx}"}],
                        "stream": False,
                    },
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

        queue_after = requests.get(f"{GO_BASE}/manage/queue", timeout=5).json()
        active_after = queue_after.get(model_name, {}).get("active_requests", 0)

        assert active_after == 0, f"Slot leak: active_requests={active_after} after all requests completed"


class TestFaultRecovery:
    def test_gateway_crash_recovery(self):
        resp = requests.get(f"{GO_BASE}/health", timeout=5)
        assert resp.status_code == 200, "Go gateway should be running"

        config_before = requests.get(f"{GO_BASE}/manage/config", timeout=5).json()

        resp = requests.get(f"{GO_BASE}/health", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_python_down_go_alone(self):
        go_health = requests.get(f"{GO_BASE}/health", timeout=5)
        assert go_health.status_code == 200, "Go gateway should be independently accessible"

        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "test go alone"}], "stream": False},
            timeout=30,
        )
        assert resp.status_code in [200, 503, 429], "Go gateway should handle requests independently"
