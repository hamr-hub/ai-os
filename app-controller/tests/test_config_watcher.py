import pytest
import tempfile
import os
import yaml
from unittest.mock import Mock, patch
from core.config_watcher import ConfigWatcher

class TestConfigWatcher:
    @pytest.fixture
    def temp_config(self):
        config = {
            "models": {
                "test-model": {
                    "service": "test-service",
                    "port": 8000
                }
            },
            "settings": {
                "concurrency_limit": 4
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            temp_path = f.name
        
        yield temp_path
        
        os.unlink(temp_path)

    def test_load_config(self, temp_config):
        watcher = ConfigWatcher(temp_config)
        config = watcher.load_config()
        
        assert "models" in config
        assert "test-model" in config["models"]
        assert config["models"]["test-model"]["port"] == 8000

    def test_load_empty_config(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            watcher = ConfigWatcher(temp_path)
            config = watcher.load_config()
            assert config == {}
        finally:
            os.unlink(temp_path)

    def test_register_callback(self, temp_config):
        watcher = ConfigWatcher(temp_config)
        callback = Mock()
        
        watcher.register_callback(callback)
        
        assert len(watcher._callbacks) == 1

    def test_notify_callbacks(self, temp_config):
        watcher = ConfigWatcher(temp_config)
        callback = Mock()
        watcher.register_callback(callback)
        
        new_config = {"test": "config"}
        watcher._notify_callbacks(new_config)
        
        callback.assert_called_once_with(new_config)

    def test_notify_callbacks_error_isolated(self, temp_config):
        watcher = ConfigWatcher(temp_config)
        bad_callback = Mock(side_effect=RuntimeError("boom"))
        good_callback = Mock()
        watcher.register_callback(bad_callback)
        watcher.register_callback(good_callback)

        watcher._notify_callbacks({"test": "config"})

        good_callback.assert_called_once()

    def test_start_watching_no_loop(self, temp_config):
        watcher = ConfigWatcher(temp_config)
        
        watcher.start_watching()
        
        assert watcher._watch_task is None or watcher._watch_task.done()

    def test_start_watching_idempotent(self, temp_config):
        watcher = ConfigWatcher(temp_config)
        mock_task = Mock()
        mock_task.done.return_value = False
        watcher._watch_task = mock_task

        result = watcher.start_watching()

        assert result is mock_task

    def test_stop_watching(self, temp_config):
        watcher = ConfigWatcher(temp_config)
        mock_task = Mock()
        watcher._watch_task = mock_task
        
        watcher.stop_watching()
        
        mock_task.cancel.assert_called_once()
        assert watcher._watch_task is None

    def test_stop_watching_idempotent(self, temp_config):
        watcher = ConfigWatcher(temp_config)
        watcher.stop_watching()
        assert watcher._watch_task is None

    def test_load_invalid_yaml_returns_empty_dict(self, temp_config):
        watcher = ConfigWatcher(temp_config)
        with patch('builtins.open', mock_open_invalid()):
            config = watcher.load_config()
        assert config == {}


def mock_open_invalid():
    from unittest.mock import mock_open
    return mock_open(read_data=': invalid yaml :')
