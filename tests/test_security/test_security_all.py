"""
安全测试 - 鉴权、输入校验、路径遍历
"""

import pytest
import requests
import json

GO_BASE = "http://localhost:35001"
PY_BASE = "http://localhost:35000"


class TestAuth:
    def test_no_auth_current_state(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "auth test"}], "stream": False},
            timeout=10,
        )
        assert resp.status_code in [200, 429, 503], "Currently no auth - this is a security risk"
        if resp.status_code == 200:
            pytest.warn("SECURITY RISK: OpenAI API accessible without authentication")

    def test_manage_api_access(self):
        resp = requests.get(f"{GO_BASE}/manage/config", timeout=5)
        assert resp.status_code == 200, "Manage API currently accessible - security risk"

    def test_b_end_no_auth(self):
        resp = requests.put(
            f"{PY_BASE}/manage/config",
            json={"settings": {"concurrency_limit": 10}},
            timeout=10,
        )
        assert resp.status_code == 200, "Python B-end config modification accessible without auth - security risk"


class TestInputValidation:
    def test_invalid_input_params(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default"},
            timeout=5,
        )
        assert resp.status_code == 400, "Missing messages should return 400"

        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            data="not json at all",
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 400, "Non-JSON should return 400"

        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "", "messages": [{"role": "user", "content": "test"}]},
            timeout=10,
        )
        assert resp.status_code in [400, 404, 503]

    def test_path_traversal_blocked(self):
        resp = requests.post(
            f"{GO_BASE}/manage/delete",
            json={"model_name": "../../../etc/passwd"},
            timeout=10,
        )
        assert resp.status_code in [400, 404, 500], "Path traversal should be blocked"

    def test_untrusted_download_source(self):
        resp = requests.post(
            f"{GO_BASE}/manage/download",
            json={"model_id": "http://malicious-site.com/model"},
            timeout=30,
        )
        assert resp.status_code in [400, 404, 503], "Untrusted download source should be rejected"

    def test_sql_injection_model_name(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "'; DROP TABLE models; --", "messages": [{"role": "user", "content": "test"}]},
            timeout=10,
        )
        assert resp.status_code == 404, "SQL injection in model name should fail"

    def test_xss_in_content(self):
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "<script>alert('xss')</script>"}], "stream": False},
            timeout=10,
        )
        assert resp.status_code in [200, 503, 429], "XSS in content should not crash server"

    def test_oversized_request(self):
        huge_content = "A" * 1000000
        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": huge_content}], "stream": False},
            timeout=10,
        )
        assert resp.status_code in [200, 429, 503], f"Unexpected: {resp.status_code}"
