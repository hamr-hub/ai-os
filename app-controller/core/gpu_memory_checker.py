"""
gpu_memory_checker.py
精准显存检测模块

优先级链: torch.cuda → pynvml → nvidia-smi
- torch.cuda: 最精准, 能看到 PyTorch 内存分配器的 reserved/allocated
- pynvml: 系统级别, 速度快
- nvidia-smi: 最后兜底, subprocess 开销大
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

logger = logging.getLogger("ai_controller.gpu_memory_checker")


@dataclass
class GPUMemoryInfo:
    device_id: int
    total_bytes: int
    used_bytes: int
    free_bytes: int
    reserved_bytes: int = 0
    allocated_bytes: int = 0
    utilization_pct: float = 0.0
    backend: str = "unknown"

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024 ** 3)

    @property
    def free_gb(self) -> float:
        return self.free_bytes / (1024 ** 3)

    @property
    def used_gb(self) -> float:
        return self.used_bytes / (1024 ** 3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "total_gb": round(self.total_gb, 2),
            "used_gb": round(self.used_gb, 2),
            "free_gb": round(self.free_gb, 2),
            "total_bytes": self.total_bytes,
            "used_bytes": self.used_bytes,
            "free_bytes": self.free_bytes,
            "reserved_bytes": self.reserved_bytes,
            "allocated_bytes": self.allocated_bytes,
            "utilization_pct": round(self.utilization_pct, 1),
            "backend": self.backend,
        }


_QUANT_COEFFICIENTS = {
    "4bit": 0.7, "int4": 0.7, "4b": 0.7,
    "8bit": 1.1, "int8": 1.1, "8b": 1.1,
    "fp16": 2.0, "fp32": 4.0, "bf16": 2.0,
    "gguf": 1.0, "awq": 0.7, "gptq": 0.7,
}

_SIZE_PATTERN = re.compile(r'(\d+(?:\.\d+)?)[xX×]?\s*(B|b)', re.IGNORECASE)


class GPUMemoryChecker:

    def __init__(self):
        self._backend: Optional[str] = None
        self._torch = None
        self._pynvml = None
        self._device_count: int = 0
        self._init_backend()

    def _init_backend(self):
        try:
            import torch
            if torch.cuda.is_available():
                self._torch = torch
                self._device_count = torch.cuda.device_count()
                self._backend = "torch"
                logger.info("GPUMemoryChecker: using torch.cuda backend, devices=%d", self._device_count)
                return
        except ImportError:
            pass
        try:
            import pynvml
            pynvml.nvmlInit()
            self._pynvml = pynvml
            self._device_count = pynvml.nvmlDeviceGetCount()
            self._backend = "pynvml"
            logger.info("GPUMemoryChecker: using pynvml backend, devices=%d", self._device_count)
            return
        except Exception:
            pass
        self._backend = "nvidia-smi"
        logger.warning("GPUMemoryChecker: falling back to nvidia-smi backend")

    @property
    def backend(self) -> str:
        return self._backend or "unknown"

    @property
    def device_count(self) -> int:
        return self._device_count

    def get_device_info(self, device_id: int = 0) -> Optional[GPUMemoryInfo]:
        if self._backend == "torch":
            return self._get_torch_info(device_id)
        elif self._backend == "pynvml":
            return self._get_pynvml_info(device_id)
        else:
            return self._get_nvidiasmi_info(device_id)

    def get_all_devices_info(self) -> List[GPUMemoryInfo]:
        results = []
        count = max(self._device_count, 1)
        for i in range(count):
            info = self.get_device_info(i)
            if info:
                results.append(info)
        return results

    def get_total_free_bytes(self) -> int:
        return sum(d.free_bytes for d in self.get_all_devices_info())

    def can_fit_model(self, required_bytes: int, device_id: int = 0,
                      headroom_bytes: int = 2 * 1024 ** 3) -> bool:
        info = self.get_device_info(device_id)
        if not info:
            return False
        return info.free_bytes >= required_bytes + headroom_bytes

    def check_model_feasibility(self, required_bytes: int, device_id: int = 0) -> Dict[str, Any]:
        info = self.get_device_info(device_id)
        if not info:
            return {"feasible": False, "reason": "gpu_info_unavailable", "available_gb": 0, "required_gb": 0}
        feasible = self.can_fit_model(required_bytes, device_id)
        return {
            "feasible": feasible,
            "available_gb": round(info.free_gb, 2),
            "required_gb": round(required_bytes / (1024 ** 3), 2),
            "safety_margin_gb": round((info.free_bytes - required_bytes) / (1024 ** 3), 2) if feasible else 0,
            "reason": None if feasible else "insufficient_memory",
        }

    def estimate_model_memory_by_params(self, size_b: float, quant: str = "fp16") -> int:
        coefficient = _QUANT_COEFFICIENTS.get(quant.lower(), 2.0)
        required_gb = size_b * coefficient + 1.0
        return int(required_gb * 1024 ** 3)

    def estimate_model_memory_by_path(self, model_path: str) -> Optional[int]:
        total_size = 0
        extensions = ['.safetensors', '.bin', '.pt', '.gguf']
        try:
            if os.path.isfile(model_path):
                return int(os.path.getsize(model_path) * 1.1)
            for root, _, files in os.walk(model_path):
                for f in files:
                    if any(f.endswith(ext) for ext in extensions):
                        total_size += os.path.getsize(os.path.join(root, f))
            if total_size == 0:
                return None
            return int(total_size * 1.1)
        except Exception as e:
            logger.warning("Failed to estimate model memory for %s: %s", model_path, e)
            return None

    @staticmethod
    def parse_model_size(name: str) -> Optional[float]:
        match = _SIZE_PATTERN.search(name)
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def parse_model_quant(name: str) -> str:
        name_lower = name.lower()
        for key in _QUANT_COEFFICIENTS:
            if key in name_lower:
                return key
        if "gguf" in name_lower:
            return "gguf"
        return "fp16"

    def get_best_device_for_model(self, required_bytes: int) -> Optional[int]:
        best_id = None
        best_free = -1
        for info in self.get_all_devices_info():
            if info.free_bytes >= required_bytes and info.free_bytes > best_free:
                best_free = info.free_bytes
                best_id = info.device_id
        return best_id

    def _get_torch_info(self, device_id: int) -> Optional[GPUMemoryInfo]:
        try:
            torch = self._torch
            props = torch.cuda.get_device_properties(device_id)
            total = props.total_memory
            reserved = torch.cuda.memory_reserved(device_id)
            allocated = torch.cuda.memory_allocated(device_id)
            free = total - reserved
            used = reserved
            utilization = self._get_utilization_fallback(device_id)
            return GPUMemoryInfo(
                device_id=device_id,
                total_bytes=total,
                used_bytes=used,
                free_bytes=free,
                reserved_bytes=reserved,
                allocated_bytes=allocated,
                utilization_pct=utilization,
                backend="torch",
            )
        except Exception as e:
            logger.error("torch.cuda info error for device %d: %s", device_id, e)
            return None

    def _get_pynvml_info(self, device_id: int) -> Optional[GPUMemoryInfo]:
        try:
            pynvml = self._pynvml
            handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                utilization = float(util.gpu)
            except Exception:
                utilization = 0.0
            return GPUMemoryInfo(
                device_id=device_id,
                total_bytes=mem_info.total,
                used_bytes=mem_info.used,
                free_bytes=mem_info.free,
                reserved_bytes=0,
                allocated_bytes=0,
                utilization_pct=utilization,
                backend="pynvml",
            )
        except Exception as e:
            logger.error("pynvml info error for device %d: %s", device_id, e)
            return None

    def _get_nvidiasmi_info(self, device_id: int) -> Optional[GPUMemoryInfo]:
        import subprocess
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.total,memory.used,memory.free,utilization.gpu',
                 '--format=csv,noheader,nounits', f'--id={device_id}'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(',')
                total_mb = int(parts[0].strip())
                used_mb = int(parts[1].strip())
                free_mb = int(parts[2].strip())
                util = float(parts[3].strip())
                MB = 1024 * 1024
                return GPUMemoryInfo(
                    device_id=device_id,
                    total_bytes=total_mb * MB,
                    used_bytes=used_mb * MB,
                    free_bytes=free_mb * MB,
                    reserved_bytes=0,
                    allocated_bytes=0,
                    utilization_pct=util,
                    backend="nvidia-smi",
                )
        except Exception as e:
            logger.error("nvidia-smi info error for device %d: %s", device_id, e)
        return None

    def _get_utilization_fallback(self, device_id: int) -> float:
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            return float(util.gpu)
        except Exception:
            return 0.0
