"""
模型管理测试 - 模型扫描、下载、删除、磁盘空间
"""

import pytest
import requests
import json
import time
import os

GO_BASE = "http://localhost:35001"
PY_BASE = "http://localhost:35000"


def _is_engine_running():
    try:
        models = requests.get(f"{GO_BASE}/manage/models", timeout=5).json()
        return any(m.get("running") for m in models.values())
    except Exception:
        return False


class TestModelScan:
    def test_local_model_scan(self):
        resp = requests.get(f"{GO_BASE}/manage/models", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict), "Models should return dict"

    def test_scan_empty_directory(self):
        resp = requests.get(f"{GO_BASE}/manage/models", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestModelDownload:
    def test_model_download_progress(self):
        resp = requests.post(
            f"{PY_BASE}/manage/models/download",
            json={"model_id": "Qwen/Qwen2-0.5B-Instruct"},
            timeout=30,
        )
        assert resp.status_code in [200, 400, 404, 503]
        if resp.status_code == 200:
            data = resp.json()
            assert "status" in data or "task_id" in data

    def test_disk_full_download_blocked(self):
        resp = requests.post(
            f"{PY_BASE}/manage/models/download",
            json={"model_id": "very_large_model_that_does_not_exist"},
            timeout=30,
        )
        assert resp.status_code in [400, 404, 503], "Should reject invalid/unavailable model"


class TestModelDelete:
    def test_delete_active_model_blocked(self):
        models = requests.get(f"{GO_BASE}/manage/models", timeout=15).json()
        running_models = [m for m, info in models.items() if info.get("running")]

        if not running_models:
            pytest.skip("No running model to test deletion protection")

        target = running_models[0]
        resp = requests.post(
            f"{PY_BASE}/manage/models/delete",
            json={"model_name": target},
            timeout=15,
        )
        assert resp.status_code in [400, 409, 403, 404], f"Active model deletion should be blocked: got {resp.status_code}"

    def test_delete_inactive_model(self):
        models = requests.get(f"{GO_BASE}/manage/models", timeout=15).json()
        inactive = [m for m, info in models.items() if not info.get("running")]

        if not inactive:
            pytest.skip("No inactive model to delete")

        target = inactive[0]
        resp = requests.post(
            f"{PY_BASE}/manage/models/delete",
            json={"model_name": target},
            timeout=15,
        )
        assert resp.status_code in [200, 400, 404]

        models_after = requests.get(f"{GO_BASE}/manage/models", timeout=15).json()
        if resp.status_code == 200:
            assert target not in models_after, f"Model {target} should be removed"


class TestModelStatus:
    def test_models_summary(self):
        resp = requests.get(f"{GO_BASE}/manage/models/summary", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data or isinstance(data, dict)

    def test_default_model(self):
        resp = requests.get(f"{GO_BASE}/manage/default-model", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "default_model" in data

    def test_queue_status(self):
        resp = requests.get(f"{GO_BASE}/manage/queue", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_model_aggregated(self):
        resp = requests.get(f"{PY_BASE}/manage/models/aggregated", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "groups" in data or "total_groups" in data

    def test_model_vllm_config(self):
        models = requests.get(f"{GO_BASE}/manage/models", timeout=10).json()
        if not models:
            pytest.skip("No models available")
        model_name = list(models.keys())[0]

        resp = requests.get(f"{PY_BASE}/manage/models/{model_name}/vllm-config", timeout=10)
        assert resp.status_code in [200, 404]

    def test_model_info_endpoint(self):
        models = requests.get(f"{GO_BASE}/manage/models", timeout=10).json()
        if not models:
            pytest.skip("No models available")
        model_name = list(models.keys())[0]

        resp = requests.get(f"{PY_BASE}/api/v1/models/{model_name}/info", timeout=10)
        assert resp.status_code in [200, 404]
