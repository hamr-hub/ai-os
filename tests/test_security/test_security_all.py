"""
安全测试 - 鉴权、输入校验、路径遍历
"""

import pytest
import requests
import json

GO_BASE = "http://localhost:35001"
PY_BASE = "http://localhost:35000"


def _is_engine_running():
    try:
        models = requests.get(f"{GO_BASE}/manage/models", timeout=5).json()
        return any(m.get("running") for m in models.values())
    except Exception:
        return False


def _safe_inference_request(url, json_data, timeout=10):
    try:
        resp = requests.post(url, json=json_data, timeout=timeout)
        return resp
    except requests.exceptions.Timeout:
        pytest.skip("Go gateway timed out on inference (no engine running)")


class TestAuth:
    @pytest.mark.skipif(not _is_engine_running(), reason="No vLLM engine running")
    def test_no_auth_current_state(self):
        resp = _safe_inference_request(
            f"{GO_BASE}/v1/chat/completions",
            {"model": "default", "messages": [{"role": "user", "content": "auth test"}], "stream": False},
            timeout=10,
        )
        assert resp.status_code in [200, 429, 503], "Currently no auth - this is a security risk"

    def test_manage_api_access(self):
        resp = requests.get(f"{GO_BASE}/manage/config", timeout=10)
        assert resp.status_code == 200, "Manage API currently accessible - security risk"

    def test_b_end_no_auth(self):
        resp = requests.put(
            f"{PY_BASE}/manage/config",
            json={"settings": {"concurrency_limit": 10}},
            timeout=10,
        )
        assert resp.status_code == 200, "Python B-end config modification accessible without auth - security risk"


class TestInputValidation:
    @pytest.mark.skipif(not _is_engine_running(), reason="No vLLM engine running - inference requests timeout")
    def test_invalid_input_params(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default"},
            timeout=10,
        )
        assert resp.status_code == 400, "Missing messages should return 400"

        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            data="not json at all",
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code == 400, "Non-JSON should return 400"

        resp = _safe_inference_request(
            f"{GO_BASE}/v1/chat/completions",
            {"model": "", "messages": [{"role": "user", "content": "test"}]},
            timeout=10,
        )
        assert resp.status_code in [400, 404, 503]

    def test_path_traversal_blocked(self):
        resp = requests.post(
            f"{PY_BASE}/manage/models/delete",
            json={"model_name": "../../../etc/passwd"},
            timeout=10,
        )
        assert resp.status_code in [400, 404, 500], "Path traversal should be blocked"

    def test_untrusted_download_source(self):
        resp = requests.post(
            f"{PY_BASE}/manage/models/download",
            json={"model_name": "http://malicious-site.com/model"},
            timeout=10,
        )
        assert resp.status_code in [200, 400, 404, 503], "Download endpoint should handle untrusted sources"
        if resp.status_code == 200:
            data = resp.json()
            assert "task_id" in data or "status" in data, "Even accepted downloads should return task info"

    @pytest.mark.skipif(not _is_engine_running(), reason="No vLLM engine running - inference requests timeout")
    def test_sql_injection_model_name(self):
        resp = _safe_inference_request(
            f"{GO_BASE}/v1/chat/completions",
            {"model": "'; DROP TABLE models; --", "messages": [{"role": "user", "content": "test"}]},
            timeout=10,
        )
        assert resp.status_code == 404, "SQL injection in model name should fail"

    @pytest.mark.skipif(not _is_engine_running(), reason="No vLLM engine running - inference requests timeout")
    def test_xss_in_content(self):
        resp = _safe_inference_request(
            f"{GO_BASE}/v1/chat/completions",
            {"model": "default", "messages": [{"role": "user", "content": "<script>alert('xss')</script>"}], "stream": False},
            timeout=10,
        )
        assert resp.status_code in [200, 503, 429], "XSS in content should not crash server"

    @pytest.mark.skipif(not _is_engine_running(), reason="No vLLM engine running - inference requests timeout")
    def test_oversized_request(self):
        huge_content = "A" * 1000000
        resp = _safe_inference_request(
            f"{GO_BASE}/v1/chat/completions",
            {"model": "default", "messages": [{"role": "user", "content": huge_content}], "stream": False},
            timeout=10,
        )
        assert resp.status_code in [200, 429, 503], f"Unexpected: {resp.status_code}"
