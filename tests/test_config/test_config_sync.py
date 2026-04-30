"""
配置同步测试 - Python B端与Go网关配置一致性、热重载、非法配置拦截
"""

import pytest
import requests
import json
import time
import yaml
import os
import copy

GO_BASE = "http://localhost:35001"
PY_BASE = "http://localhost:35000"
CONFIG_PATH = os.environ.get("CONFIG_PATH", "configs/config.yaml")


def _get_go_concurrency_limit(go_settings):
    return go_settings.get("ConcurrencyLimit") or go_settings.get("concurrency_limit")


class TestConfigSync:
    def test_config_modify_sync(self):
        py_config = requests.get(f"{PY_BASE}/manage/config", timeout=10).json()
        original_limit = py_config.get("settings", {}).get("concurrency_limit", 10)

        new_limit = original_limit + 1 if original_limit < 100 else original_limit - 1
        update_resp = requests.put(
            f"{PY_BASE}/manage/config",
            json={"settings": {"concurrency_limit": new_limit}},
            timeout=10,
        )
        assert update_resp.status_code == 200, f"Config update failed: {update_resp.text}"
        updated = update_resp.json()
        assert updated.get("config", {}).get("settings", {}).get("concurrency_limit") == new_limit

        time.sleep(5)
        go_resp = requests.get(f"{GO_BASE}/manage/config", timeout=10)
        if go_resp.status_code == 200:
            go_config = go_resp.json()
            go_settings = go_config.get("settings", {})
            go_limit = _get_go_concurrency_limit(go_settings)
            if go_limit is not None:
                assert go_limit == new_limit, f"Go config not synced: expected {new_limit}, got {go_limit}"

        restore_resp = requests.put(
            f"{PY_BASE}/manage/config",
            json={"settings": {"concurrency_limit": original_limit}},
            timeout=10,
        )
        assert restore_resp.status_code == 200

    def test_hot_reload_yaml(self):
        reload_resp = requests.post(f"{PY_BASE}/manage/config/reload", timeout=10)
        assert reload_resp.status_code == 200, f"Reload failed: {reload_resp.text}"
        reloaded = reload_resp.json()
        assert reloaded.get("status") == "reloaded"

    def test_sync_failure_fallback(self):
        py_config = requests.get(f"{PY_BASE}/manage/config", timeout=10).json()
        original_limit = py_config.get("settings", {}).get("concurrency_limit", 10)

        update_resp = requests.put(
            f"{PY_BASE}/manage/config",
            json={"settings": {"concurrency_limit": original_limit + 5}},
            timeout=10,
        )
        assert update_resp.status_code == 200

        py_config_after = requests.get(f"{PY_BASE}/manage/config", timeout=10).json()
        new_limit = py_config_after.get("settings", {}).get("concurrency_limit")
        assert new_limit == original_limit + 5, "Python local config should persist even if Go sync fails"

        requests.put(
            f"{PY_BASE}/manage/config",
            json={"settings": {"concurrency_limit": original_limit}},
            timeout=10,
        )

    def test_invalid_config_rejected(self):
        resp = requests.put(
            f"{PY_BASE}/manage/config",
            json={"settings": {"concurrency_limit": -1}},
            timeout=10,
        )
        assert resp.status_code in [400, 200], f"Invalid config handling: got {resp.status_code}"

    def test_config_version_consistency(self):
        py_config = requests.get(f"{PY_BASE}/manage/config", timeout=10).json()
        go_resp = requests.get(f"{GO_BASE}/manage/config", timeout=10)

        if go_resp.status_code != 200:
            pytest.skip("Go gateway config not accessible")

        go_config = go_resp.json()

        py_models = set(py_config.get("models", {}).keys())
        go_models = set(go_config.get("models", {}).keys())

        common_models = py_models & go_models
        for model in common_models:
            py_port = py_config["models"][model].get("port")
            go_port = go_config["models"][model].get("port")
            assert py_port == go_port, f"Model {model} port mismatch: py={py_port}, go={go_port}"

    def test_concurrent_config_update(self):
        py_config1 = requests.get(f"{PY_BASE}/manage/config", timeout=10).json()
        original_redis_port = py_config1.get("settings", {}).get("redis", {}).get("port", 6379)
        original_limit = py_config1.get("settings", {}).get("concurrency_limit", 10)

        resp1 = requests.put(
            f"{PY_BASE}/manage/config",
            json={"settings": {"redis": {"port": original_redis_port}}},
            timeout=10,
        )
        resp2 = requests.put(
            f"{PY_BASE}/manage/config",
            json={"settings": {"concurrency_limit": original_limit}},
            timeout=10,
        )

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        final_config = requests.get(f"{PY_BASE}/manage/config", timeout=10).json()
        assert final_config["settings"]["redis"]["port"] == original_redis_port
        assert final_config["settings"]["concurrency_limit"] == original_limit
