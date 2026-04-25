import yaml
import os
import asyncio
import logging
import tempfile
from typing import Dict, Callable, List, Tuple
from core.config import load_config as load_app_config, validate_config

logger = logging.getLogger("ai_controller.config_watcher")

class ConfigWatcher:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._config = {}
        self._last_modified = None
        self._callbacks: List[Callable[[Dict], None]] = []
        self._watch_task = None
        self._stop_event = asyncio.Event()
        self._last_error = None
    
    def load_config(self) -> Dict:
        ok, config = self.load_config_with_status()
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
            return True, normalized
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("Failed to load config: %s", self.config_path)
            return False, {}
    
    def get_config(self) -> Dict:
        return self._config

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
    
    def save_config(self, config: Dict) -> bool:
        try:
            if not isinstance(config, dict):
                raise ValueError("Config payload must be a dict")

            temp_path = None
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.yaml',
                dir=os.path.dirname(self.config_path) or None,
                delete=False,
            ) as f:
                yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
                temp_path = f.name

            try:
                normalized = load_app_config(temp_path)
                errors = validate_config(normalized)
                if errors:
                    self._last_error = "; ".join(errors)
                    logger.error("Refusing to save invalid config for %s: %s", self.config_path, self._last_error)
                    return False

                os.replace(temp_path, self.config_path)
                self._config = normalized.model_dump(exclude_none=True)
                self._last_modified = os.path.getmtime(self.config_path)
                self._last_error = None
                return True
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
        except Exception:
            logger.exception("Error saving config: %s", self.config_path)
            return False

    def stop_watching(self):
        if self._watch_task is None:
            return
        self._stop_event.set()
        self._watch_task.cancel()
        self._watch_task = None
