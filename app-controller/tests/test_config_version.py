import pytest
import os
import tempfile
import yaml
import copy
from core.config_watcher import ConfigWatcher


@pytest.fixture
def temp_config_file():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config_data = {
            "models": {
                "demo": {
                    "service": "vllm",
                    "port": 8000,
                    "required_memory": "8GB",
                    "model_path": "/tmp/demo",
                    "preload": True,
                }
            },
            "settings": {"concurrency_limit": 10, "redis": {"host": "localhost", "port": 6379, "db": 0}},
            "vllm": {"service_name": "vllm", "default_port": 8000, "model_base_path": "/tmp"},
        }
        yaml.safe_dump(config_data, f)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def watcher(temp_config_file):
    w = ConfigWatcher(temp_config_file)
    ok, cfg = w.load_config_with_status()
    assert ok, f"Failed to load config: {w.get_last_error()}"
    w.save_config(cfg)
    return w


def test_version_starts_at_zero():
    w = ConfigWatcher("/nonexistent.yaml")
    assert w.get_version() == 0


def test_version_increments_on_save(watcher):
    initial_version = watcher.get_version()
    config = watcher.get_config()
    config["settings"]["concurrency_limit"] = 20
    assert watcher.save_config(config)
    assert watcher.get_version() == initial_version + 1


def test_check_version_matches(watcher):
    version = watcher.get_version()
    ok, current = watcher.check_version(version)
    assert ok is True
    assert current == version


def test_check_version_conflict(watcher):
    ok, current = watcher.check_version(999)
    assert ok is False
    assert current == watcher.get_version()


def test_check_version_none_passes(watcher):
    ok, current = watcher.check_version(None)
    assert ok is True


def test_multiple_saves_increment_version(watcher):
    v0 = watcher.get_version()
    config = watcher.get_config()
    watcher.save_config(config)
    assert watcher.get_version() == v0 + 1
    config2 = watcher.get_config()
    watcher.save_config(config2)
    assert watcher.get_version() == v0 + 2


def test_log_operation_creates_log(watcher):
    watcher.log_operation("test_user", "update", {"a": 1}, {"b": 2})
    from core.config_watcher import CONFIG_LOG_FILE
    log_dir = os.path.dirname(CONFIG_LOG_FILE)
    if os.path.exists(log_dir):
        log_files = [f for f in os.listdir(log_dir) if f.endswith(".log")]
        if log_files and os.path.exists(CONFIG_LOG_FILE):
            with open(CONFIG_LOG_FILE) as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1]
                    import json
                    entry = json.loads(last_line)
                    assert entry["operator"] == "test_user"
                    assert entry["action"] == "update"
