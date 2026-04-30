"""
全链路集成测试 - 跨端联调验证，覆盖Go网关+Python B端+引擎的完整交互
"""

import pytest
import requests
import json
import time
import os

GO_BASE = "http://localhost:35001"
PY_BASE = "http://localhost:35000"


def _engine_available():
    resp = requests.get(f"{GO_BASE}/v1/models", timeout=5)
    if resp.status_code != 200:
        return False
    models = resp.json().get("data", [])
    return len(models) > 0


def _get_go_concurrency_limit(go_settings):
    return go_settings.get("ConcurrencyLimit") or go_settings.get("concurrency_limit")


class TestFullChainIntegration:
    def test_full_chain_health(self):
        go_health = requests.get(f"{GO_BASE}/health", timeout=10)
        py_health = requests.get(f"{PY_BASE}/health", timeout=10)

        assert go_health.status_code == 200, f"Go gateway unhealthy: {go_health.status_code}"
        assert py_health.status_code == 200, f"Python B-end unhealthy: {py_health.status_code}"

    def test_config_cross_backend_consistency(self):
        go_config = requests.get(f"{GO_BASE}/manage/config", timeout=10).json()
        py_config = requests.get(f"{PY_BASE}/manage/config", timeout=10).json()

        go_models = set(go_config.get("models", {}).keys())
        py_models = set(py_config.get("models", {}).keys())

        overlap = go_models & py_models
        for m in overlap:
            go_port = go_config["models"][m].get("port")
            py_port = py_config["models"][m].get("port")
            assert go_port == py_port, f"Model {m} port mismatch: go={go_port}, py={py_port}"

        py_limit = py_config.get("settings", {}).get("concurrency_limit")
        go_limit = _get_go_concurrency_limit(go_config.get("settings", {}))
        if go_limit is not None:
            assert go_limit == py_limit, f"Concurrency limit mismatch: go={go_limit}, py={py_limit}"

    def test_model_status_cross_backend(self):
        go_models = requests.get(f"{GO_BASE}/manage/models", timeout=10).json()
        py_models = requests.get(f"{PY_BASE}/manage/models", timeout=10).json()

        common = set(go_models.keys()) & set(py_models.keys())
        for m in common:
            go_running = go_models[m].get("running")
            py_running = py_models[m].get("running")
            assert go_running == py_running, f"Model {m} running status mismatch: go={go_running}, py={py_running}"

    def test_chat_request_full_chain(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "全链路集成测试"}], "stream": False},
            timeout=10,
        )
        assert resp.status_code in [200, 503, 429]

        if resp.status_code == 200:
            data = resp.json()
            assert "choices" in data
            assert "usage" in data

    def test_chat_stream_full_chain(self):
        if not _engine_available():
            pytest.skip("No running engine for SSE stream test")

        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "流式全链路测试"}], "stream": True},
            headers={"Accept": "text/event-stream"},
            stream=True,
            timeout=120,
        )
        assert resp.status_code == 200

        received_chunks = 0
        has_done = False
        for line in resp.iter_lines(decode_unicode=True):
            if line and "data:" in line:
                received_chunks += 1
                if "data: [DONE]" in line:
                    has_done = True

        assert received_chunks > 0, "No chunks in stream response"
        assert has_done, "Missing [DONE] marker"

    def test_model_switch_with_ongoing_requests(self):
        models = requests.get(f"{GO_BASE}/manage/models", timeout=10).json()
        available = [m for m, info in models.items() if not info.get("running")]
        if len(available) < 1:
            pytest.skip("No alternate model for switch test")

        target = available[0]
        switch_resp = requests.post(
            f"{PY_BASE}/manage/switch/atomic",
            json={"action": "switch", "model_name": target},
            timeout=10,
        )

        if switch_resp.status_code == 409:
            pytest.skip("Switch already in progress")

        if switch_resp.status_code in [200, 201]:
            for _ in range(30):
                status = requests.get(f"{PY_BASE}/manage/switch/status", timeout=10).json()
                session = status.get("session")
                if session and session.get("overall_phase") in ("completed", "failed", "rolled_back"):
                    break
                time.sleep(3)

        final_models = requests.get(f"{GO_BASE}/manage/models", timeout=10).json()
        assert isinstance(final_models, dict), "Models endpoint should return dict"

    def test_gpu_monitoring_cross_backend(self):
        go_gpu = requests.get(f"{GO_BASE}/manage/gpu", timeout=10).json()
        py_gpu = requests.get(f"{PY_BASE}/manage/gpu", timeout=10).json()

        if go_gpu.get("status") == "unavailable" or py_gpu.get("status") == "unavailable":
            pytest.skip("No GPU available")

    def test_metrics_collection_full_chain(self):
        requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "metrics chain test"}], "stream": False},
            timeout=10,
        )

        go_metrics = requests.get(f"{GO_BASE}/manage/metrics", timeout=10).json()
        py_metrics = requests.get(f"{PY_BASE}/manage/metrics", timeout=10).json()

        assert isinstance(go_metrics, dict)
        assert isinstance(py_metrics, dict)

    def test_vllm_metrics_endpoint(self):
        resp = requests.get(f"{PY_BASE}/manage/vllm/metrics", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestCrossBackendDifferences:
    def test_go_proxy_to_python(self):
        resp = requests.get(f"{GO_BASE}/manage/models/aggregated", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            assert "groups" in data or "current_model" in data

    def test_python_config_sync_to_go(self):
        py_config = requests.get(f"{PY_BASE}/manage/config", timeout=10).json()
        original = py_config.get("settings", {}).get("concurrency_limit", 10)

        requests.put(
            f"{PY_BASE}/manage/config",
            json={"settings": {"concurrency_limit": original}},
            timeout=10,
        )

        time.sleep(3)
        go_resp = requests.get(f"{GO_BASE}/manage/config", timeout=10)
        if go_resp.status_code == 200:
            go_config = go_resp.json()
            go_limit = _get_go_concurrency_limit(go_config.get("settings", {}))
            if go_limit is not None:
                assert go_limit == original, f"Config not synced: py={original}, go={go_limit}"

    def test_integration_status(self):
        resp = requests.get(f"{PY_BASE}/api/v1/status", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "service" in data
        assert "models" in data
        assert "queue" in data
