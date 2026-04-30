import yaml
import os
import asyncio
import logging
import tempfile
import copy
import json
import time
from typing import Dict, Callable, List, Tuple, Optional
from core.config import load_config as load_app_config, validate_config
from pydantic import ValidationError

logger = logging.getLogger("ai_controller.config_watcher")

CONFIG_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "config_ops.log")

class ConfigWatcher:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._config = {}
        self._version = 0
        self._last_modified = None
        self._callbacks: List[Callable[[Dict], None]] = []
        self._watch_task = None
        self._stop_event = asyncio.Event()
        self._last_error = None
    
    def load_config(self) -> Dict:
        previous_error = self._last_error
        ok, config = self.load_config_with_status()
        if ok and previous_error:
            self._last_error = previous_error
        return config if ok else {}

    def load_config_with_status(self) -> Tuple[bool, Dict]:
        if not os.path.exists(self.config_path):
            self._last_error = None
            return True, {}
        try:
            config = load_app_config(self.config_path)
            errors = validate_config(config)
            if errors:
                self._last_error = "; ".join(errors)
                logger.error("Config validation failed for %s: %s", self.config_path, self._last_error)
                return False, {}
            normalized = config.model_dump(exclude_none=True)
            self._last_error = None
            if normalized.get("version", 0) > self._version:
                self._version = normalized.get("version", 0)
            return True, normalized
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("Failed to load config: %s", self.config_path)
            return False, {}
    
    def get_config(self) -> Dict:
        return copy.deepcopy(self._config)

    def get_last_error(self):
        return self._last_error
    
    def register_callback(self, callback: Callable[[Dict], None]):
        self._callbacks.append(callback)
    
    def _notify_callbacks(self, new_config: Dict):
        for callback in self._callbacks:
            try:
                callback(new_config)
            except Exception:
                logger.exception("Config callback failed: %s", getattr(callback, "__name__", repr(callback)))
    
    async def _watch_loop(self):
        while not self._stop_event.is_set():
            try:
                if os.path.exists(self.config_path):
                    current_modified = os.path.getmtime(self.config_path)
                    if self._last_modified is None:
                        self._last_modified = current_modified
                        ok, initial_config = self.load_config_with_status()
                        if ok:
                            self._config = initial_config
                            self._notify_callbacks(self._config)
                        else:
                            logger.warning("Skipping initial config apply due to invalid config: %s", self._last_error)
                    elif current_modified > self._last_modified:
                        self._last_modified = current_modified
                        ok, new_config = self.load_config_with_status()
                        if not ok:
                            logger.warning("Ignoring config file change due to invalid config: %s", self._last_error)
                            continue
                        if new_config != self._config:
                            self._config = new_config
                            self._notify_callbacks(self._config)
            except Exception:
                logger.exception("Config watch loop failed: %s", self.config_path)
            
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
        self._watch_task = None
    
    def start_watching(self):
        if self._watch_task is not None and not self._watch_task.done():
            return self._watch_task
        self._stop_event = asyncio.Event()
        try:
            loop = asyncio.get_running_loop()
            self._watch_task = loop.create_task(self._watch_loop())
            return self._watch_task
        except RuntimeError:
            logger.warning("No running event loop for config watcher: %s", self.config_path)
            self._watch_task = None
            return None
    
    def get_version(self) -> int:
        return self._version

    def check_version(self, expected_version: Optional[int]) -> Tuple[bool, int]:
        if expected_version is None:
            return True, self._version
        if expected_version != self._version:
            return False, self._version
        return True, self._version

    def log_operation(self, operator: str, action: str, before: Dict, after: Dict):
        log_dir = os.path.dirname(CONFIG_LOG_FILE)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "operator": operator,
            "action": action,
            "version_before": self._version - 1 if action == "update" else self._version,
            "version_after": self._version,
            "before_keys": list(before.keys()) if isinstance(before, dict) else [],
            "after_keys": list(after.keys()) if isinstance(after, dict) else [],
        }
        try:
            with open(CONFIG_LOG_FILE, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("Failed to write config operation log")

    def save_config(self, config: Dict) -> bool:
        try:
            if not isinstance(config, dict):
                raise ValueError("Config payload must be a dict")

            from core.config import AppConfig as _AppConfig, ModelConfig as _ModelConfig, SettingsConfig as _SettingsConfig

            merged_payload = copy.deepcopy(config)
            for key in ["models"]:
                if key not in merged_payload:
                    raw_config = {}
                    if os.path.exists(self.config_path):
                        with open(self.config_path, "r") as f:
                            raw_config = yaml.safe_load(f) or {}
                    if key in raw_config:
                        merged_payload[key] = raw_config[key]

            try:
                payload_config = _AppConfig(**merged_payload)
                payload_errors = validate_config(payload_config)
                if payload_errors:
                    self._last_error = "; ".join(payload_errors)
                    logger.error("Refusing to save invalid config payload for %s: %s", self.config_path, self._last_error)
                    return False
            except (ValidationError, ValueError) as exc:
                self._last_error = str(exc)
                logger.error("Refusing to save invalid config payload for %s: %s", self.config_path, self._last_error)
                return False

            normalized = load_app_config(self.config_path)
            errors = validate_config(normalized)
            if errors:
                self._last_error = "; ".join(errors)
                logger.error("Refusing to save invalid config for %s: %s", self.config_path, self._last_error)
                return False
            raw_config = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    raw_config = yaml.safe_load(f) or {}

            merged = copy.deepcopy(raw_config)
            normalized_dict = normalized.model_dump(exclude_none=True)
            for key, value in normalized_dict.items():
                merged[key] = value
            for key in config:
                if key not in normalized_dict:
                    merged[key] = config[key]

            temp_path = None
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.yaml',
                dir=os.path.dirname(self.config_path) or None,
                delete=False,
            ) as f:
                yaml.safe_dump(merged, f, default_flow_style=False, allow_unicode=True)
                temp_path = f.name

            try:
                os.replace(temp_path, self.config_path)
                self._config = normalized_dict
                self._last_modified = os.path.getmtime(self.config_path)
                self._last_error = None
                self._version += 1
                return True
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("Error saving config: %s", self.config_path)
            return False

    def stop_watching(self):
        if self._watch_task is None:
            return
        self._stop_event.set()
        self._watch_task.cancel()
        self._watch_task = None
