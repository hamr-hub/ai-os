import os
import shutil
import logging
import yaml
import time
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field

from core.gpu_memory_checker import GPUMemoryChecker

logger = logging.getLogger("ai_controller.model_pool")

_LOAD_PRIORITY_ORDER = ["critical", "high", "normal", "low"]
_PRIORITY_MAP = {"critical": 0, "high": 1, "normal": 2, "low": 3}


@dataclass
class PoolEntry:
    name: str
    source: str = "local"
    size_b: Optional[float] = None
    quant: Optional[str] = None
    required_gb: Optional[float] = None
    feasible: Optional[bool] = None
    local_path: Optional[str] = None
    engine_type: Optional[str] = None
    download_status: str = "not_downloaded"
    running_status: str = "stopped"
    port: Optional[int] = None
    config_key: Optional[str] = None
    priority: str = "normal"
    keep_alive: bool = False
    preload: bool = False
    last_used: Optional[float] = None
    estimated_memory_bytes: Optional[int] = None
    supports_images: bool = False
    supports_tool_calling: bool = False
    description: Optional[str] = None
    architecture: Optional[str] = None
    file_size_bytes: Optional[int] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "size_b": self.size_b,
            "quant": self.quant,
            "required_gb": self.required_gb,
            "feasible": self.feasible,
            "local_path": self.local_path,
            "engine_type": self.engine_type,
            "download_status": self.download_status,
            "running_status": self.running_status,
            "port": self.port,
            "priority": self.priority,
            "keep_alive": self.keep_alive,
            "preload": self.preload,
            "last_used": self.last_used,
            "estimated_memory_gb": round(self.estimated_memory_bytes / (1024**3), 2) if self.estimated_memory_bytes else None,
            "supports_images": self.supports_images,
            "supports_tool_calling": self.supports_tool_calling,
            "description": self.description,
            "file_size_bytes": self.file_size_bytes,
        }


class ModelPoolManager:

    def __init__(
        self, config=None, gpu_memory_manager=None,
        llm_service_manager=None, model_hub=None,
    ):
        self._config = config
        self._gpu_memory_manager = gpu_memory_manager
        self._llm_service_manager = llm_service_manager
        self._model_hub = model_hub
        self._pool: Dict[str, PoolEntry] = {}
        self._model_base_path = "/mnt/pve_models"
        self._config_path = ""

        if config:
            if hasattr(config, 'vllm') and config.vllm:
                self._model_base_path = config.vllm.get("model_base_path", self._model_base_path)
        if hasattr(config, 'config_path'):
            self._config_path = config.config_path
        elif config and isinstance(config, dict):
            self._config_path = config.get('config_path', '')

    def scan_and_sync(self) -> int:
        count = 0
        if os.path.isdir(self._model_base_path):
            for name in os.listdir(self._model_base_path):
                full_path = os.path.join(self._model_base_path, name)
                if not os.path.isdir(full_path):
                    continue
                if name in self._pool and self._pool[name].download_status == "completed":
                    continue
                entry = self._create_entry_from_path(name, full_path)
                self._pool[name] = entry
                count += 1

        if self._config:
            models_dict = self._config.get('models', {}) if isinstance(self._config, dict) else (self._config.models if hasattr(self._config, 'models') else {})
            for name, model_cfg in models_dict.items():
                if name not in self._pool:
                    entry = self._create_entry_from_config(name, model_cfg)
                    self._pool[name] = entry
                    count += 1

        if self._model_hub:
            local_models = self._model_hub.list_local_models()
            for lm in local_models:
                n = lm["name"]
                if n not in self._pool:
                    file_size_bytes = None
                    if lm.get("size_gb"):
                        file_size_bytes = int(lm.get("size_gb") * (1024 ** 3))
                    entry = PoolEntry(
                        name=n, source="local",
                        local_path=lm["path"],
                        download_status="completed",
                        running_status="stopped",
                        quant=lm.get("quant", "fp16"),
                        architecture=lm.get("architecture"),
                        file_size_bytes=file_size_bytes,
                    )
                    self._pool[n] = entry
                    count += 1

        self._estimate_all_memory()
        logger.info("Scanned and synced %d models into pool", count)
        return count

    def _create_entry_from_path(self, name: str, path: str) -> PoolEntry:
        size_b = GPUMemoryChecker.parse_model_size(name)
        quant = GPUMemoryChecker.parse_model_quant(name)
        
        file_size_bytes = None
        if self._model_hub:
            model_info = self._model_hub.get_model_info(name)
            if model_info and model_info.get("size_gb"):
                file_size_bytes = int(model_info.get("size_gb") * (1024 ** 3))
        
        entry = PoolEntry(
            name=name, source="local",
            size_b=size_b, quant=quant,
            local_path=path,
            download_status="completed",
            running_status="stopped",
            file_size_bytes=file_size_bytes,
        )
        entry.estimated_memory_bytes = self._estimate_entry_memory(entry)
        return entry

    def _cfg_get(self, cfg: Any, key: str, default=None):
        if isinstance(cfg, dict):
            return cfg.get(key, default)
        return getattr(cfg, key, default)

    def _create_entry_from_config(self, name: str, cfg: Any) -> PoolEntry:
        size_b = GPUMemoryChecker.parse_model_size(name)
        quant = GPUMemoryChecker.parse_model_quant(name)
        model_path = self._cfg_get(cfg, 'model_path') or os.path.join(self._model_base_path, name)
        entry = PoolEntry(
            name=name, source="config",
            size_b=size_b, quant=quant,
            local_path=model_path,
            download_status="completed",
            running_status="stopped",
            config_key=name,
            engine_type=self._cfg_get(cfg, 'engine_type', 'vllm') or self._cfg_get(cfg, 'service', 'vllm'),
            port=self._cfg_get(cfg, 'port'),
            keep_alive=self._cfg_get(cfg, 'keep_alive', False),
            preload=self._cfg_get(cfg, 'preload', False),
            supports_images=self._cfg_get(cfg, 'supports_images', False),
            supports_tool_calling=self._cfg_get(cfg, 'supports_tool_calling', False),
            description=self._cfg_get(cfg, 'description'),
        )
        entry.estimated_memory_bytes = self._estimate_entry_memory(entry)
        return entry

    def _estimate_entry_memory(self, entry: PoolEntry) -> int:
        if not self._gpu_memory_manager:
            return 0
        return self._gpu_memory_manager.estimate_model_memory(
            entry.name, size_b=entry.size_b, quant=entry.quant,
            model_path=entry.local_path,
        )

    def _estimate_all_memory(self):
        for entry in self._pool.values():
            if entry.estimated_memory_bytes is None or entry.estimated_memory_bytes == 0:
                entry.estimated_memory_bytes = self._estimate_entry_memory(entry)

    def _check_feasibility_for_entry(self, entry: PoolEntry) -> Optional[Dict]:
        if not self._gpu_memory_manager:
            return None
        return self._gpu_memory_manager.check_model_feasibility(
            entry.name, size_b=entry.size_b, quant=entry.quant,
            model_path=entry.local_path,
        )

    def register_from_download(
        self, model_name: str, local_path: str, source: str,
        size_b: Optional[float] = None, quant: Optional[str] = None,
        required_gb: Optional[float] = None,
    ) -> PoolEntry:
        short_name = model_name.split("/")[-1]
        
        # 从 model_hub 获取完整的模型信息
        architecture = None
        file_size_bytes = None
        if self._model_hub:
            # 确保模型被 model_hub 正确扫描和注册
            self._model_hub.refresh_local_models()
            model_info = self._model_hub.get_model_info(model_name)
            if model_info:
                quant = quant or model_info.get("quant")
                architecture = model_info.get("architecture")
                if model_info.get("size_gb"):
                    # 将 GB 转换为字节
                    file_size_bytes = int(model_info.get("size_gb") * (1024 ** 3))
            # 优先从名称解析模型参数大小（size_b）
            if size_b is None:
                size_b = GPUMemoryChecker.parse_model_size(model_name)
        
        entry = PoolEntry(
            name=short_name, source=source,
            size_b=size_b, quant=quant, required_gb=required_gb,
            local_path=local_path,
            download_status="completed",
            running_status="stopped",
            architecture=architecture,
            file_size_bytes=file_size_bytes,
        )
        entry.estimated_memory_bytes = self._estimate_entry_memory(entry)
        self._pool[short_name] = entry
        logger.info("Registered downloaded model %s from %s", short_name, source)
        return entry

    def register_from_search(
        self, model_name: str, source: str,
        size_b: Optional[float] = None, quant: Optional[str] = None,
        required_gb: Optional[float] = None, feasible: Optional[bool] = None,
    ) -> PoolEntry:
        short_name = model_name.split("/")[-1]
        entry = PoolEntry(
            name=short_name, source=source,
            size_b=size_b, quant=quant, required_gb=required_gb,
            feasible=feasible,
            download_status="not_downloaded",
            running_status="stopped",
        )
        self._pool[short_name] = entry
        return entry

    def get_pool_list(
        self, filter: str = "all", page: int = 1, page_size: int = 50,
    ) -> List[Dict]:
        entries = list(self._pool.values())
        if filter == "downloaded":
            entries = [e for e in entries if e.download_status == "completed"]
        elif filter == "running":
            entries = [e for e in entries if e.running_status == "running"]
        elif filter == "local":
            entries = [e for e in entries if e.source in ("local", "config")]
        elif filter == "feasible":
            entries = [e for e in entries if e.feasible is True]
        entries.sort(key=lambda e: (
            _PRIORITY_MAP.get(e.priority, 2),
            -(e.estimated_memory_bytes or 0),
            e.name,
        ))
        start = (page - 1) * page_size
        return [e.to_dict() for e in entries[start:start + page_size]]

    def get_pool_detail(self, model_key: str) -> Optional[Dict]:
        entry = self._pool.get(model_key)
        if not entry:
            return None
        result = entry.to_dict()
        feasibility = self._check_feasibility_for_entry(entry)
        if feasibility:
            result["feasibility"] = feasibility
        return result

    def load_model(
        self, model_key: str, engine: str = "vllm",
        port: Optional[int] = None, device_id: int = 0,
        force: bool = False,
    ) -> Dict:
        entry = self._pool.get(model_key)
        if not entry:
            return {"success": False, "reason": "model_not_in_pool"}

        if not entry.local_path or entry.download_status != "completed":
            return {"success": False, "reason": "model_not_downloaded"}

        if entry.running_status == "running" and not force:
            return {"success": False, "reason": "model_already_running", "port": entry.port}

        feasibility = self._check_feasibility_for_entry(entry)
        if feasibility and not feasibility["feasible"] and not force:
            return {
                "success": False,
                "reason": "insufficient_gpu_memory",
                "feasibility": feasibility,
            }

        if not self._llm_service_manager:
            return {"success": False, "reason": "no_llm_service_manager"}

        if force and entry.running_status == "running":
            svc = self._llm_service_manager.get_service_by_model(model_key)
            if svc:
                self._llm_service_manager.stop_service(svc["service_name"])

        actual_port = port or entry.port or 8000
        result = self._llm_service_manager.start_service(
            model_key, model_key, engine, actual_port,
            model_path=entry.local_path,
        )
        if result.get("status") == "started":
            entry.running_status = "running"
            entry.engine_type = engine
            entry.port = actual_port
            entry.last_used = time.time()
            if self._gpu_memory_manager:
                self._gpu_memory_manager.register_loaded_model(
                    model_key, device_id=device_id,
                    size_b=entry.size_b, quant=entry.quant,
                    model_path=entry.local_path,
                )
            return {
                "success": True,
                "model": model_key,
                "engine": engine,
                "port": actual_port,
            }
        return {"success": False, "reason": result.get("message", "start_failed"), "detail": result}

    def unload_model(self, model_key: str) -> Dict:
        entry = self._pool.get(model_key)
        if not entry:
            return {"success": False, "reason": "model_not_in_pool"}
        if entry.running_status != "running":
            return {"success": False, "reason": "model_not_running"}
        if not self._llm_service_manager:
            return {"success": False, "reason": "no_llm_service_manager"}

        svc = self._llm_service_manager.get_service_by_model(model_key)
        if svc:
            stopped = self._llm_service_manager.stop_service(svc["service_name"])
            if not stopped:
                return {"success": False, "reason": "stop_failed"}

        entry.running_status = "stopped"
        entry.port = None
        if self._gpu_memory_manager:
            self._gpu_memory_manager.unregister_loaded_model(model_key)
        return {"success": True, "model": model_key}

    def hot_switch(
        self, target_model: str, engine: str = "vllm",
        port: Optional[int] = None,
    ) -> Dict:
        running = [e for e in self._pool.values() if e.running_status == "running"]
        unload_results = []
        for e in running:
            if e.name != target_model:
                r = self.unload_model(e.name)
                unload_results.append(r)

        load_result = self.load_model(target_model, engine, port)
        return {
            "success": load_result.get("success", False),
            "target": target_model,
            "unload_results": unload_results,
            "load_result": load_result,
        }

    def delete_model(self, model_key: str, remove_files: bool = False) -> Dict:
        entry = self._pool.get(model_key)
        if not entry:
            return {"deleted": False, "reason": "not_in_pool"}
        if entry.running_status == "running":
            return {"deleted": False, "reason": "model_is_running"}
        self._pool.pop(model_key, None)
        if remove_files and entry.local_path and os.path.isdir(entry.local_path):
            try:
                shutil.rmtree(entry.local_path)
            except Exception as e:
                logger.warning("Failed to remove files for %s: %s", model_key, e)
        return {"deleted": True, "model_key": model_key}

    def update_priority(self, model_key: str, priority: str) -> Dict:
        entry = self._pool.get(model_key)
        if not entry:
            return {"success": False, "reason": "not_in_pool"}
        if priority not in _PRIORITY_MAP:
            return {"success": False, "reason": "invalid_priority"}
        entry.priority = priority
        return {"success": True, "model_key": model_key, "priority": priority}

    def get_running_models(self) -> List[Dict]:
        return [e.to_dict() for e in self._pool.values() if e.running_status == "running"]

    def get_total_estimated_memory_gb(self) -> float:
        total = sum(e.estimated_memory_bytes or 0 for e in self._pool.values() if e.running_status == "running")
        return total / (1024 ** 3)

    def get_pool_stats(self) -> Dict:
        by_status = {}
        by_source = {}
        for e in self._pool.values():
            by_status[e.running_status] = by_status.get(e.running_status, 0) + 1
            by_source[e.source] = by_source.get(e.source, 0) + 1
        return {
            "total_models": len(self._pool),
            "by_running_status": by_status,
            "by_source": by_source,
            "running_memory_gb": round(self.get_total_estimated_memory_gb(), 2),
        }

    def sync_to_config(self) -> bool:
        if not self._config_path:
            return False
        try:
            with open(self._config_path, "r") as f:
                raw = yaml.safe_load(f) or {}
            for key, entry in self._pool.items():
                if entry.download_status == "completed" and entry.config_key is None:
                    if key not in raw.get("models", {}):
                        raw.setdefault("models", {})[key] = {
                            "service": "vllm-aiclient",
                            "port": entry.port or 8000,
                            "required_memory": f"{int(entry.required_gb or 8)}GB",
                            "model_path": entry.local_path,
                            "description": f"Downloaded from {entry.source}",
                            "source": entry.source,
                        }
                        if entry.engine_type:
                            raw["models"][key]["engine_type"] = entry.engine_type
            with open(self._config_path, "w") as f:
                yaml.dump(raw, f, default_flow_style=False)
            logger.info("Synced pool to config %s", self._config_path)
            return True
        except Exception as e:
            logger.error("Failed to sync pool to config: %s", e)
            return False
