import yaml
import os
import asyncio
import logging
from typing import Dict, Callable, List

logger = logging.getLogger("ai_controller.config_watcher")

class ConfigWatcher:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._config = {}
        self._last_modified = None
        self._callbacks: List[Callable[[Dict], None]] = []
        self._watch_task = None
        self._stop_event = asyncio.Event()
    
    def load_config(self) -> Dict:
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            if config is None:
                return {}
            if isinstance(config, dict):
                return config
            logger.warning("Config content is not a dict: %s", self.config_path)
            return {}
        except Exception:
            logger.exception("Failed to load config: %s", self.config_path)
            return {}
    
    def get_config(self) -> Dict:
        return self._config
    
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
                        self._config = self.load_config()
                        self._notify_callbacks(self._config)
                    elif current_modified > self._last_modified:
                        self._last_modified = current_modified
                        new_config = self.load_config()
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
            with open(self.config_path, 'w') as f:
                yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
            self._config = config if isinstance(config, dict) else {}
            self._last_modified = os.path.getmtime(self.config_path)
            return True
        except Exception:
            logger.exception("Error saving config: %s", self.config_path)
            return False

    def stop_watching(self):
        if self._watch_task is None:
            return
        self._stop_event.set()
        self._watch_task.cancel()
        self._watch_task = None
