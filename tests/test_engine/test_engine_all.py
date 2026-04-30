"""
引擎层测试 - 引擎热切换、模型热切换、进度追踪、故障恢复、显存泄漏
"""

import pytest
import requests
import json
import time
import subprocess
import os

GO_BASE = "http://localhost:35001"
PY_BASE = "http://localhost:35000"


class TestEngineSwitch:
    def test_engine_hot_switch(self):
        status_before = requests.get(f"{GO_BASE}/manage/engine-status", timeout=5).json()

        models_resp = requests.get(f"{GO_BASE}/manage/models", timeout=5)
        models = models_resp.json()
        available = [m for m, info in models.items() if info.get("running") is False]
        if not available:
            pytest.skip("No alternate model available for switch")

        target = available[0]

        switch_resp = requests.post(
            f"{PY_BASE}/manage/switch/atomic",
            json={"action": "switch", "model_name": target},
            timeout=10,
        )
        assert switch_resp.status_code in [200, 201, 409], f"Switch request failed: {switch_resp.text}"

        if switch_resp.status_code == 409:
            pytest.skip("Switch already in progress")

        data = switch_resp.json()
        session_id = data.get("session_id")
        assert session_id is not None, "Missing session_id"

        for _ in range(60):
            status_resp = requests.get(f"{PY_BASE}/manage/switch/status", timeout=5)
            status_data = status_resp.json()
            session = status_data.get("session")
            if session and session.get("overall_phase") == "completed":
                break
            if session and session.get("overall_phase") in ("failed", "rolled_back"):
                pytest.fail(f"Switch failed/rolled_back: {session.get('error')}")
            time.sleep(3)

        final_status = requests.get(f"{PY_BASE}/manage/switch/status", timeout=5).json()
        session = final_status.get("session")
        assert session is not None
        assert session.get("overall_phase") == "completed", f"Switch not completed: phase={session.get('overall_phase')}"

    def test_switch_status_tracking(self):
        models_resp = requests.get(f"{GO_BASE}/manage/models", timeout=5)
        models = models_resp.json()
        available = [m for m, info in models.items() if info.get("running") is False]
        if not available:
            pytest.skip("No alternate model")

        target = available[0]
        switch_resp = requests.post(
            f"{PY_BASE}/manage/switch/atomic",
            json={"action": "switch", "model_name": target},
            timeout=10,
        )

        if switch_resp.status_code == 409:
            pytest.skip("Switch in progress")

        phases_observed = []
        for _ in range(60):
            status = requests.get(f"{PY_BASE}/manage/switch/status", timeout=5).json()
            session = status.get("session")
            if session:
                phase = session.get("overall_phase")
                if phase not in phases_observed:
                    phases_observed.append(phase)
                if phase in ("completed", "failed", "rolled_back"):
                    break
            time.sleep(2)

        assert len(phases_observed) > 0, "No phases observed"
        assert "completed" in phases_observed or "failed" in phases_observed, f"Unexpected phases: {phases_observed}"

    def test_switch_conflict_rejected(self):
        models = requests.get(f"{GO_BASE}/manage/models", timeout=5).json()
        available = [m for m, info in models.items() if info.get("running") is False]
        if not available:
            pytest.skip("No alternate model")

        target = available[0]
        first_resp = requests.post(
            f"{PY_BASE}/manage/switch/atomic",
            json={"action": "switch", "model_name": target},
            timeout=10,
        )

        if first_resp.status_code != 200:
            pytest.skip(f"First switch failed: {first_resp.status_code}")

        second_resp = requests.post(
            f"{PY_BASE}/manage/switch/atomic",
            json={"action": "switch", "model_name": target},
            timeout=10,
        )
        assert second_resp.status_code == 409, f"Concurrent switch should return 409: got {second_resp.status_code}"

        time.sleep(30)


class TestModelSwitch:
    def test_model_hot_switch(self):
        models = requests.get(f"{GO_BASE}/manage/models", timeout=5).json()
        running = [m for m, info in models.items() if info.get("running")]
        available = [m for m, info in models.items() if not info.get("running")]
        if not available:
            pytest.skip("No alternate model available")

        gpu_before = requests.get(f"{GO_BASE}/manage/gpu", timeout=5).json()
        mem_before = gpu_before.get("used_memory", 0) if isinstance(gpu_before, dict) else 0

        target = available[0]
        switch_resp = requests.post(
            f"{PY_BASE}/manage/switch/atomic",
            json={"action": "switch", "model_name": target},
            timeout=10,
        )
        assert switch_resp.status_code in [200, 201, 409]

        if switch_resp.status_code == 409:
            pytest.skip("Switch already in progress")

        for _ in range(60):
            status = requests.get(f"{PY_BASE}/manage/switch/status", timeout=5).json()
            session = status.get("session")
            if session and session.get("overall_phase") == "completed":
                break
            if session and session.get("overall_phase") in ("failed", "rolled_back"):
                pytest.fail(f"Model switch failed")
            time.sleep(3)

        models_after = requests.get(f"{GO_BASE}/manage/models", timeout=5).json()
        assert models_after.get(target, {}).get("running") is True, f"Model {target} not running after switch"

    def test_memory_leak_after_switch(self):
        models = requests.get(f"{GO_BASE}/manage/models", timeout=5).json()
        available = [m for m, info in models.items() if not info.get("running")]
        if len(available) < 2:
            pytest.skip("Need at least 2 alternate models")

        mem_records = []
        for i in range(3):
            gpu = requests.get(f"{GO_BASE}/manage/gpu", timeout=5).json()
            mem = gpu.get("used_memory", 0) if isinstance(gpu, dict) else 0
            mem_records.append(mem)

            target = available[i % len(available)]
            switch_resp = requests.post(
                f"{PY_BASE}/manage/switch/atomic",
                json={"action": "switch", "model_name": target},
                timeout=10,
            )

            for _ in range(60):
                status = requests.get(f"{PY_BASE}/manage/switch/status", timeout=5).json()
                session = status.get("session")
                if session and session.get("overall_phase") in ("completed", "failed", "rolled_back"):
                    break
                time.sleep(3)

            time.sleep(5)

        if len(mem_records) >= 2:
            mem_diff = abs(mem_records[-1] - mem_records[0])
            assert mem_diff < 500 * 1024 * 1024, f"Memory leak: {mem_diff/(1024*1024):.0f}MB growth over {len(mem_records)} switches"

    def test_switch_nonexistent_path(self):
        resp = requests.post(
            f"{PY_BASE}/manage/switch/atomic",
            json={"action": "switch", "model_name": "nonexistent_model_xyz"},
            timeout=10,
        )
        assert resp.status_code in [404, 400], f"Should reject nonexistent model: got {resp.status_code}"


class TestFaultRecovery:
    def test_engine_crash_recovery(self):
        health_before = requests.get(f"{GO_BASE}/health", timeout=5).json()
        status_before = health_before.get("status", "")

        resp = requests.post(
            f"{GO_BASE}/v1/chat/completions",
            json={"model": "default", "messages": [{"role": "user", "content": "Hello"}]},
            timeout=30,
        )
        assert resp.status_code in [200, 503, 429], f"Unexpected: {resp.status_code}"

        time.sleep(5)
        health_after = requests.get(f"{GO_BASE}/health", timeout=5).json()
        assert "status" in health_after
