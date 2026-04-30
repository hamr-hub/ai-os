import pytest
import requests
import os
import sys


PY_BASE = os.environ.get("PY_BASE", "http://localhost:35000")
GO_BASE = os.environ.get("GO_BASE", "http://localhost:35001")


class TestBackendService:
    def test_health_check(self):
        resp = requests.get(f"{PY_BASE}/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        status = data.get("status", "")
        assert status in ("ok", "healthy", "warning", "degraded", "unhealthy")

    def test_model_management(self):
        resp = requests.get(f"{PY_BASE}/manage/models", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_gpu_monitor(self):
        resp = requests.get(f"{PY_BASE}/manage/gpu", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("available", "unavailable")

    def test_gpu_summary(self):
        resp = requests.get(f"{PY_BASE}/manage/gpu/summary", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_health_score(self):
        resp = requests.get(f"{PY_BASE}/health", timeout=10)
        data = resp.json()
        assert "health_score" in data
        assert isinstance(data["health_score"], (int, float))


class TestGoService:
    def test_go_health(self):
        resp = requests.get(f"{GO_BASE}/health", timeout=10)
        assert resp.status_code == 200


class TestRedisConfig:
    def test_redis_health(self):
        resp = requests.get(f"{PY_BASE}/manage/redis/health", timeout=10)
        assert resp.status_code == 200
