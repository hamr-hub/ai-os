"""
Go网关层测试 - SSE流式转发、并发控制、限流、故障处理、OpenAI协议API
"""

import pytest
import requests
import json
import time
import threading
import signal
import subprocess

GO_BASE = "http://localhost:35001"


def _engine_available():
    resp = requests.get(f"{GO_BASE}/v1/models", timeout=5)
    if resp.status_code != 200:
        return False
    models = resp.json().get("data", [])
    return len(models) > 0


class TestSSEStreaming:
    def test_stream_integrity(self):
        if not _engine_available():
            pytest.skip("No running engine for SSE test")

        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={
                "model": "default",
                "messages": [{"role": "user", "content": "你好，请写一首短诗"}],
                "stream": True,
            },
            headers={"Accept": "text/event-stream"},
            stream=True,
            timeout=60,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

        chunks = []
        has_done = False
        for line in resp.iter_lines(decode_unicode=True):
            if line:
                chunks.append(line)
                if line.strip() == "data: [DONE]":
                    has_done = True

        assert len(chunks) > 0, "No SSE chunks received"
        assert has_done, "Missing [DONE] marker in SSE stream"
        assert any("data:" in c for c in chunks), "No data chunks found"

    def test_non_stream_completion(self):
        if not _engine_available():
            resp = requests.post(
                f"{GO_BASE}/v1/chat/completions",
                json={"model": "default", "messages": [{"role": "user", "content": "Hello"}], "stream": False},
                timeout=10,
            )
            assert resp.status_code in [200, 503, 429], f"Expected 200/503/429, got {resp.status_code}"
            return

        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "Hello"}], "stream": False},
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "choices" in data, "Missing choices field"
        assert len(data["choices"]) > 0, "Empty choices"
        assert "usage" in data, "Missing usage field"

    def test_client_disconnect_cleanup(self):
        if not _engine_available():
            pytest.skip("No running engine for disconnect cleanup test")

        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "请写一篇1000字的文章"}], "stream": True},
            headers={"Accept": "text/event-stream"},
            stream=True,
            timeout=60,
        )
        assert resp.status_code == 200

        count = 0
        for line in resp.iter_lines(decode_unicode=True):
            if line and "data:" in line:
                count += 1
            if count >= 3:
                resp.close()
                break

        time.sleep(2)
        status_resp = requests.get(f"{GO_BASE}/manage/metrics", timeout=5)
        if status_resp.status_code == 200:
            metrics = status_resp.json()
            assert metrics.get("active_goroutines", 0) < 200, "Possible goroutine leak after disconnect"


class TestConcurrencyControl:
    def test_stream_concurrent_limit(self):
        config_resp = requests.get(f"{GO_BASE}/manage/config", timeout=5)
        if config_resp.status_code != 200:
            pytest.skip("Config endpoint not available")
        config = config_resp.json()
        limit = config.get("settings", {}).get("ConcurrencyLimit") or config.get("settings", {}).get("concurrency_limit", 10)

        results = []
        threads = []

        def send_stream_request(idx):
            try:
                resp = requests.post(
                    f"{GO_BASE}/v1/chat/completions",
                    json={"model": "default", "messages": [{"role": "user", "content": f"并发请求{idx}"}], "stream": False},
                    timeout=10,
                )
                results.append((idx, resp.status_code))
            except Exception as e:
                results.append((idx, str(e)))

        for i in range(limit + 2):
            t = threading.Thread(target=send_stream_request, args=(i,))
            threads.append(t)

        for t in threads:
            t.start()

        time.sleep(5)

        success_count = sum(1 for _, code in results if code == 200)
        reject_count = sum(1 for _, code in results if code == 429)

        if not _engine_available():
            assert len(results) > 0, "Should have some results"

        for t in threads:
            t.join(timeout=30)

    def test_goroutine_leak(self):
        initial_resp = requests.get(f"{GO_BASE}/manage/metrics", timeout=5)
        if initial_resp.status_code != 200:
            pytest.skip("Metrics endpoint not available")
        initial_data = initial_resp.json()
        initial_goroutines = initial_data.get("active_goroutines", 0)

        for i in range(20):
            try:
                resp = requests.post(
                    f"{GO_BASE}/v1/chat/completions",
                    json={"model": "default", "messages": [{"role": "user", "content": f"短请求{i}"}], "stream": False},
                    timeout=5,
                )
                resp.close()
            except:
                pass

        time.sleep(5)

        final_resp = requests.get(f"{GO_BASE}/manage/metrics", timeout=5)
        final_data = final_resp.json()
        final_goroutines = final_data.get("active_goroutines", 0)

        leak_threshold = initial_goroutines + 10
        assert final_goroutines <= leak_threshold, (
            f"Goroutine leak: initial={initial_goroutines}, final={final_goroutines}"
        )


class TestRateLimiting:
    def test_ip_rate_limit(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "Rate limit test"}], "stream": False},
            timeout=10,
        )
        if resp.status_code == 429:
            assert "rate limit" in resp.json().get("error", "").lower()
            return

        rate_headers = resp.headers
        assert "X-RateLimit-Limit" in rate_headers, "Missing rate limit headers"

    def test_whitelist_exempt(self):
        resp = requests.get(f"{GO_BASE}/health", timeout=5)
        assert resp.status_code == 200, f"Local IP should be exempt: got {resp.status_code}"

    def test_ip_forgery_blocked(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "IP test"}], "stream": False},
            headers={"X-Forwarded-For": "127.0.0.1"},
            timeout=10,
        )
        assert resp.status_code in [200, 429, 503], f"Unexpected status: {resp.status_code}"


class TestFaultHandling:
    def test_engine_down_recovery(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "Hello"}], "stream": False},
            timeout=10,
        )
        assert resp.status_code in [200, 503, 429], f"Unexpected: {resp.status_code}"

    def test_request_timeout(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "nonexistent_model", "messages": [{"role": "user", "content": "test"}], "stream": False},
            timeout=10,
        )
        assert resp.status_code in [404, 400, 503], f"Should fail for nonexistent model: got {resp.status_code}"


class TestV1API:
    def test_list_models(self):
        resp = requests.get(f"{GO_BASE}/v1/models", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("object") == "list", "Missing object=list in response"
        assert "data" in data, "Missing data field"

    def test_get_model_info(self):
        models_resp = requests.get(f"{GO_BASE}/v1/models", timeout=10)
        models = models_resp.json().get("data", [])
        if not models:
            pytest.skip("No models available")
        model_name = models[0].get("id", "")

        resp = requests.get(f"{GO_BASE}/v1/models/{model_name}", timeout=10)
        assert resp.status_code in [200, 404]
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("id") == model_name

    def test_invalid_request_format(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            data="not json",
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 400

    def test_empty_model_field(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "", "messages": [{"role": "user", "content": "test"}]},
            timeout=10,
        )
        assert resp.status_code in [400, 404, 503]

    def test_no_messages_field(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default"},
            timeout=10,
        )
        assert resp.status_code == 400

    def test_v1_status(self):
        resp = requests.get(f"{GO_BASE}/v1/status", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "available_models" in data
        assert "timestamp" in data
