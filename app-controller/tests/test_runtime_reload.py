import asyncio
from unittest.mock import Mock

import pytest

import main


@pytest.mark.asyncio
async def test_reload_runtime_config_applies_loaded_config(monkeypatch):
    loaded = {"models": {"demo": {"port": 8000}}}
    apply_mock = Mock()
    log_mock = Mock()

    monkeypatch.setattr(main.config_watcher, "load_config_with_status", lambda: (True, loaded))
    monkeypatch.setattr(main, "_on_config_changed", apply_mock)
    monkeypatch.setattr(main.structured_logger, "info", log_mock)

    result = await main.reload_runtime_config()

    assert result is True
    apply_mock.assert_called_once_with(loaded)
    log_mock.assert_called_once()


@pytest.mark.asyncio
async def test_reload_runtime_config_rejects_invalid_payload(monkeypatch):
    warn_mock = Mock()
    apply_mock = Mock()

    monkeypatch.setattr(main.config_watcher, "load_config_with_status", lambda: (False, {}))
    monkeypatch.setattr(main.config_watcher, "get_last_error", lambda: "invalid config")
    monkeypatch.setattr(main.logger, "warning", warn_mock)
    monkeypatch.setattr(main, "_on_config_changed", apply_mock)

    result = await main.reload_runtime_config()

    assert result is False
    apply_mock.assert_not_called()
    warn_mock.assert_called_once()


def test_install_signal_handlers_registers_sighup(monkeypatch):
    loop = Mock()
    monkeypatch.setattr(main.asyncio, "get_running_loop", lambda: loop)

    main._install_signal_handlers()

    loop.add_signal_handler.assert_called_once()
    registered_signal = loop.add_signal_handler.call_args.args[0]
    callback = loop.add_signal_handler.call_args.args[1]

    assert registered_signal == main.signal.SIGHUP
    assert callable(callback)
