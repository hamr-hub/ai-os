import logging
import os
from typing import Dict, Optional, List, Any

from core.gpu_memory_checker import GPUMemoryChecker, GPUMemoryInfo
from core.config import AppConfig, parse_memory_size

logger = logging.getLogger("ai_controller.gpu_memory_manager")

_LOADED_MODEL_MEMORY: Dict[str, int] = {}

_SAFETY_RATIO = 0.85
_HEADROOM_GB = 2.0


class GPUMemoryManager:

    def __init__(self, config: Optional[AppConfig] = None):
        self._config = config
        self._checker = GPUMemoryChecker()
        self._loaded_models: Dict[str, Dict[str, Any]] = {}
        logger.info(
            "GPUMemoryManager initialized, backend=%s, devices=%d",
            self._checker.backend, self._checker.device_count,
        )

    @property
    def checker(self) -> GPUMemoryChecker:
        return self._checker

    @property
    def backend(self) -> str:
        return self._checker.backend

    @property
    def device_count(self) -> int:
        return self._checker.device_count

    def get_gpu_info(self, device_id: int = 0) -> Optional[Dict[str, Any]]:
        info = self._checker.get_device_info(device_id)
        if not info:
            return None
        return info.to_dict()

    def get_all_gpu_info(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._checker.get_all_devices_info()]

    def get_total_free_bytes(self) -> int:
        return self._checker.get_total_free_bytes()

    def get_total_free_gb(self) -> float:
        return self.get_total_free_bytes() / (1024 ** 3)

    def get_effective_free_bytes(self, device_id: int = 0) -> int:
        info = self._checker.get_device_info(device_id)
        if not info:
            return 0
        loaded_mem = sum(
            m["estimated_bytes"] for m in self._loaded_models.values()
            if m.get("device_id", 0) == device_id
        )
        effective = int(info.total_bytes * _SAFETY_RATIO) - info.used_bytes - loaded_mem
        return max(effective, 0)

    def get_effective_free_gb(self, device_id: int = 0) -> float:
        return self.get_effective_free_bytes(device_id) / (1024 ** 3)

    def estimate_model_memory(
        self, model_name: str, size_b: Optional[float] = None,
        quant: Optional[str] = None, model_path: Optional[str] = None,
    ) -> int:
        if model_path and os.path.exists(model_path):
            estimated = self._checker.estimate_model_memory_by_path(model_path)
            if estimated:
                return estimated
        if size_b:
            q = quant or self._checker.parse_model_quant(model_name)
            return self._checker.estimate_model_memory_by_params(size_b, q)
        if self._config:
            model_cfg = self._config.get_model(model_name)
            if model_cfg:
                mem_str = model_cfg.required_memory
                return parse_memory_size(mem_str)
        return int(8 * 1024 ** 3)

    def estimate_model_memory_gb(
        self, model_name: str, size_b: Optional[float] = None,
        quant: Optional[str] = None, model_path: Optional[str] = None,
    ) -> float:
        return self.estimate_model_memory(model_name, size_b, quant, model_path) / (1024 ** 3)

    def check_model_feasibility(
        self, model_name: str, size_b: Optional[float] = None,
        quant: Optional[str] = None, model_path: Optional[str] = None,
        device_id: int = 0,
    ) -> Dict[str, Any]:
        required_bytes = self.estimate_model_memory(model_name, size_b, quant, model_path)
        required_gb = required_bytes / (1024 ** 3)
        info = self._checker.get_device_info(device_id)
        if not info:
            return {
                "feasible": False,
                "reason": "gpu_unavailable",
                "available_gb": 0,
                "required_gb": round(required_gb, 2),
                "gpu_available": False,
            }
        effective_free = self.get_effective_free_bytes(device_id)
        effective_free_gb = effective_free / (1024 ** 3)
        headroom = int(_HEADROOM_GB * 1024 ** 3)
        feasible = effective_free >= required_bytes + headroom
        safety_margin = effective_free - required_bytes - headroom
        reason = None
        if not feasible:
            reason = "insufficient_memory"
            if model_name in self._loaded_models:
                reason = "model_already_loaded"
        return {
            "feasible": feasible,
            "reason": reason,
            "available_gb": round(effective_free_gb, 2),
            "required_gb": round(required_gb, 2),
            "safety_margin_gb": round(max(safety_margin, 0) / (1024 ** 3), 2),
            "gpu_available": True,
            "gpu_name": info.to_dict().get("total_gb", ""),
            "device_id": device_id,
            "backend": self._checker.backend,
            "loaded_models": list(self._loaded_models.keys()),
        }

    def register_loaded_model(
        self, model_name: str, device_id: int = 0,
        size_b: Optional[float] = None, quant: Optional[str] = None,
        model_path: Optional[str] = None,
    ):
        estimated_bytes = self.estimate_model_memory(model_name, size_b, quant, model_path)
        self._loaded_models[model_name] = {
            "device_id": device_id,
            "estimated_bytes": estimated_bytes,
            "estimated_gb": round(estimated_bytes / (1024 ** 3), 2),
            "quant": quant or self._checker.parse_model_quant(model_name),
        }
        logger.info(
            "Registered loaded model '%s' on device %d, estimated %.2f GB",
            model_name, device_id, estimated_bytes / (1024 ** 3),
        )

    def unregister_loaded_model(self, model_name: str):
        if model_name in self._loaded_models:
            info = self._loaded_models.pop(model_name)
            logger.info(
                "Unregistered model '%s', freed ~%.2f GB estimated",
                model_name, info["estimated_gb"],
            )

    def get_loaded_models(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._loaded_models)

    def get_loaded_memory_gb(self, device_id: Optional[int] = None) -> float:
        total = 0
        for m in self._loaded_models.values():
            if device_id is None or m.get("device_id", 0) == device_id:
                total += m["estimated_bytes"]
        return total / (1024 ** 3)

    def find_best_device_for_model(
        self, model_name: str, size_b: Optional[float] = None,
        quant: Optional[str] = None, model_path: Optional[str] = None,
    ) -> Optional[int]:
        required_bytes = self.estimate_model_memory(model_name, size_b, quant, model_path)
        headroom = int(_HEADROOM_GB * 1024 ** 3)
        return self._checker.get_best_device_for_model(required_bytes + headroom)

    def get_memory_summary(self) -> Dict[str, Any]:
        all_info = self._checker.get_all_devices_info()
        devices = []
        for d in all_info:
            dev_id = d.device_id
            eff_free = self.get_effective_free_bytes(dev_id)
            loaded = self.get_loaded_memory_gb(dev_id)
            devices.append({
                "device_id": dev_id,
                "total_gb": round(d.total_gb, 2),
                "used_gb": round(d.used_gb, 2),
                "free_gb": round(d.free_gb, 2),
                "effective_free_gb": round(eff_free / (1024 ** 3), 2),
                "loaded_models_memory_gb": round(loaded, 2),
                "utilization_pct": round(d.utilization_pct, 1),
            })
        return {
            "backend": self._checker.backend,
            "device_count": self._checker.device_count,
            "devices": devices,
            "loaded_models": list(self._loaded_models.keys()),
            "total_loaded_memory_gb": round(self.get_loaded_memory_gb(), 2),
        }
