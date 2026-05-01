import subprocess
import json
import os
import asyncio
import httpx
import logging
import warnings
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from core.cache_service import cache_service
from core.vllm_metrics import VLLMMetricsScraper

_THROTTLE_REASON_MAP = {
    0x00000001: "gpu_idle",
    0x00000002: "applications_clocks_setting",
    0x00000004: "sw_power_cap",
    0x00000008: "hw_thermal_slowdown",
    0x00000010: "sw_thermal_slowdown",
    0x00000020: "hw_power_brake_slowdown",
    0x00000040: "sw_power_brake_slowdown",
    0x00000080: "display_clocks_setting",
    0x00000100: "sw_power_sliding_window_slowdown",
    0x00000200: "hw_thermal_slowdown_vmin",
    0x00000400: "hw_thermal_slowdown_vrel",
}

logger = logging.getLogger("ai_controller.monitor")


def _decode_throttle_reasons(reasons_bits: int) -> List[str]:
    if reasons_bits == 0:
        return []
    result = []
    for bit, name in _THROTTLE_REASON_MAP.items():
        if reasons_bits & bit:
            result.append(name)
    return result


class NVMLCollector:
    def __init__(self):
        self._initialized = False
        self._device_count = 0
        self._handles = []
        self._driver_version = ""
        self._nvml_init_result = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                import pynvml
            self._pynvml = pynvml
            self._nvml_init_result = pynvml.nvmlInit()
            self._initialized = True
            self._device_count = pynvml.nvmlDeviceGetCount()
            self._handles = [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(self._device_count)]
            try:
                self._driver_version = pynvml.nvmlDeviceGetDriverVersion()
            except Exception:
                pass
        except ImportError:
            logger.info("pynvml not available, GPU monitor will fall back to nvidia-smi")
        except Exception as exc:
            try:
                self._pynvml.nvmlShutdown()
            except Exception:
                pass
            self._initialized = False
            logger.warning("Failed to initialize NVML collector: %s", exc)

    @property
    def is_available(self) -> bool:
        return self._initialized and self._device_count > 0

    def shutdown(self):
        if self._initialized:
            try:
                self._pynvml.nvmlShutdown()
            except Exception as exc:
                logger.warning("Failed to shutdown NVML cleanly: %s", exc)
            self._initialized = False

    def collect_all(self) -> Optional[Dict]:
        if not self._initialized:
            return None
        gpus = []
        for i, handle in enumerate(self._handles):
            info = self._collect_single(handle, i)
            if info:
                gpus.append(info)
        if not gpus:
            return None
        primary_gpu = gpus[0]
        return {
            "status": "available",
            "gpu_count": len(gpus),
            "name": primary_gpu["name"],
            "total_memory": primary_gpu["total_memory"],
            "used_memory": primary_gpu["used_memory"],
            "available_memory": primary_gpu["available_memory"],
            "temperature": primary_gpu["temperature"],
            "utilization": primary_gpu["utilization"],
            "power_draw": primary_gpu["power_draw"],
            "power_limit": primary_gpu["power_limit"],
            "power_percent": primary_gpu["power_percent"],
            "fan_speed": primary_gpu["fan_speed"],
            "clock_sm": primary_gpu["clock_sm"],
            "clock_mem": primary_gpu["clock_mem"],
            "memory_utilization": primary_gpu["memory_utilization"],
            "primary": primary_gpu,
            "all_gpus": gpus,
            "driver_version": self._driver_version,
        }

    def _collect_single(self, handle, index: int) -> Optional[Dict]:
        pynvml = self._pynvml
        try:
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode('utf-8', errors='replace')
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            total_mem = mem.total
            used_mem = mem.used
            free_mem = mem.free

            temperature = 0
            try:
                temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                pass

            utilization = 0
            try:
                util_rates = pynvml.nvmlDeviceGetUtilizationRates(handle)
                utilization = util_rates.gpu
            except Exception:
                pass

            power_draw_mw = 0
            power_limit_mw = 0
            try:
                power_draw_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
            except Exception:
                pass
            try:
                power_limit_mw = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
            except Exception:
                pass
            power_draw_w = int(power_draw_mw / 1000)
            power_limit_w = int(power_limit_mw / 1000)
            power_percent = int(power_draw_mw / power_limit_mw * 100) if power_limit_mw > 0 else 0

            fan_speed = 0
            try:
                fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
            except Exception:
                pass

            clock_sm = 0
            try:
                clock_sm = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
            except Exception:
                pass

            clock_mem = 0
            try:
                clock_mem = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
            except Exception:
                pass

            ecc_errors = 0
            try:
                ecc_errors = pynvml.nvmlDeviceGetTotalEccErrors(handle, pynvml.NVML_SINGLE_BIT_ECC_ERROR_TYPE)
            except Exception:
                pass

            throttle_reasons_bits = 0
            try:
                throttle_reasons_bits = pynvml.nvmlDeviceGetCurrentClocksThrottleReasons(handle)
            except Exception:
                pass
            throttle_reasons = _decode_throttle_reasons(throttle_reasons_bits)

            persistence_mode = False
            try:
                persistence_mode = pynvml.nvmlDeviceGetPersistenceMode(handle) == pynvml.NVML_FEATURE_ENABLED
            except Exception:
                pass

            pcie_rx_throughput = 0
            pcie_tx_throughput = 0
            try:
                pcie_rx_throughput = pynvml.nvmlDeviceGetPcieThroughput(handle, pynvml.NVML_PCIE_UTIL_RX_BYTES)
            except Exception:
                pass
            try:
                pcie_tx_throughput = pynvml.nvmlDeviceGetPcieThroughput(handle, pynvml.NVML_PCIE_UTIL_TX_BYTES)
            except Exception:
                pass

            bar1_total = 0
            bar1_used = 0
            try:
                bar1_info = pynvml.nvmlDeviceGetBAR1MemoryInfo(handle)
                bar1_total = bar1_info.bar1Total
                bar1_used = bar1_info.bar1Used
            except Exception:
                pass

            processes = []
            try:
                proc_list = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                for proc in proc_list:
                    proc_name = self._get_process_name(proc.pid)
                    used_gpu_mem = proc.usedGpuMemory if hasattr(proc, 'usedGpuMemory') else proc.usedGpuMemory
                    processes.append({
                        "pid": proc.pid,
                        "name": proc_name,
                        "used_gpu_memory": used_gpu_mem,
                    })
            except Exception:
                pass

            vbios_version = ""
            try:
                vbios_version = pynvml.nvmlDeviceGetVbiosVersion(handle)
                if isinstance(vbios_version, bytes):
                    vbios_version = vbios_version.decode('utf-8', errors='replace')
            except Exception:
                pass

            perf_state = ""
            try:
                perf_state = pynvml.nvmlDeviceGetPerformanceState(handle)
            except Exception:
                pass

            encoder_util = 0
            try:
                encoder_util = pynvml.nvmlDeviceGetEncoderUtilization(handle)
            except Exception:
                pass

            decoder_util = 0
            try:
                decoder_util = pynvml.nvmlDeviceGetDecoderUtilization(handle)
            except Exception:
                pass

            total_mb = total_mem // (1024 ** 2)
            used_mb = used_mem // (1024 ** 2)
            memory_utilization = int(used_mb / total_mb * 100) if total_mb > 0 else 0

            return {
                "name": name,
                "index": index,
                "total_memory": total_mem,
                "used_memory": used_mem,
                "available_memory": free_mem,
                "temperature": temperature,
                "utilization": utilization,
                "power_draw": power_draw_w,
                "power_limit": power_limit_w,
                "power_percent": power_percent,
                "fan_speed": fan_speed,
                "clock_sm": clock_sm,
                "clock_mem": clock_mem,
                "memory_utilization": memory_utilization,
                "ecc_errors": ecc_errors,
                "throttle_reasons": throttle_reasons,
                "persistence_mode": persistence_mode,
                "pcie_rx_throughput": pcie_rx_throughput,
                "pcie_tx_throughput": pcie_tx_throughput,
                "bar1_total_memory": bar1_total,
                "bar1_used_memory": bar1_used,
                "processes": processes,
                "vbios_version": vbios_version,
                "performance_state": perf_state,
                "encoder_utilization": encoder_util,
                "decoder_utilization": decoder_util,
            }
        except Exception as exc:
            logger.warning("Failed to collect NVML metrics for GPU %s: %s", index, exc)
            return None

    def _get_process_name(self, pid: int) -> str:
        try:
            cmdline_path = f"/proc/{pid}/cmdline"
            with open(cmdline_path, 'rb') as f:
                cmdline = f.read().decode('utf-8', errors='replace').replace('\x00', ' ').strip()
                return cmdline[:100] if cmdline else f"pid-{pid}"
        except Exception:
            return f"pid-{pid}"


class GPUMonitor:
    def __init__(self):
        self._last_flush_time = datetime.now()
        self._flush_interval = 300
        self._memory_strategy = "balanced"
        self._fragmentation_history: List[float] = []
        self._redis_client = None
        self._history_enabled = True
        self._max_history_days = 30
        self._status_cache: Optional[Dict] = None
        self._status_cache_time: Optional[datetime] = None
        self._last_history_cleanup = datetime.min
        self._history_cleanup_interval = timedelta(minutes=5)
        self._cache_update_task: Optional[asyncio.Task] = None
        self._cache_update_interval = 2.0

        self._nvml_collector = NVMLCollector()
        self._nvidia_smi_available = False
        self._use_nvml = self._nvml_collector.is_available
        self._vllm_scraper = VLLMMetricsScraper()
        self._vllm_metrics_cache: Optional[Dict] = None

        if not self._use_nvml:
            self._nvidia_smi_available = self._check_nvidia_smi()

    def _check_nvidia_smi(self) -> bool:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--version"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _cache_valid(self) -> bool:
        if self._status_cache is None or self._status_cache_time is None:
            return False
        # Cache is valid for 5 seconds
        return (datetime.now() - self._status_cache_time).total_seconds() < 5.0

    async def refresh_cache(self):
        """Manually refresh the GPU status cache."""
        await self._refresh_cache()
        return self._status_cache

    async def _update_cache_loop(self):
        while True:
            try:
                await self._refresh_cache()
                await self._refresh_vllm_metrics()
            except Exception:
                logger.exception("GPU cache updater loop failed")
            await asyncio.sleep(self._cache_update_interval)

    async def _refresh_cache(self):
        if self._use_nvml:
            try:
                status = self._nvml_collector.collect_all()
                if status:
                    self._status_cache = status
                    self._status_cache_time = datetime.now()
                    return
            except Exception as exc:
                logger.warning("NVML cache refresh failed, falling back to nvidia-smi: %s", exc)

        if not self._nvidia_smi_available:
            self._status_cache = None
            self._status_cache_time = None
            return

        await self._refresh_cache_nvidia_smi()

    async def _refresh_cache_nvidia_smi(self):
        try:
            process = await asyncio.create_subprocess_exec(
                "nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu,power.draw,power.limit,fan.speed,clocks.sm,clocks.mem", "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode('utf-8').strip() if stdout else ''

            if process.returncode != 0 or not stdout_str:
                stderr_str = stderr.decode('utf-8', errors='replace').strip() if stderr else ''
                if process.returncode != 0:
                    logger.warning("nvidia-smi refresh failed with code %s: %s", process.returncode, stderr_str[:200])
                self._status_cache = None
                self._status_cache_time = None
                return

            gpus = []
            for line in stdout_str.split('\n'):
                gpu_info = self._parse_gpu_line(line)
                if gpu_info:
                    gpus.append(gpu_info)

            if gpus:
                primary_gpu = gpus[0]
                status = {
                    "status": "available",
                    "gpu_count": len(gpus),
                    "name": primary_gpu["name"],
                    "total_memory": primary_gpu["total_memory"],
                    "used_memory": primary_gpu["used_memory"],
                    "available_memory": primary_gpu["available_memory"],
                    "temperature": primary_gpu["temperature"],
                    "utilization": primary_gpu["utilization"],
                    "power_draw": primary_gpu["power_draw"],
                    "power_limit": primary_gpu["power_limit"],
                    "power_percent": primary_gpu["power_percent"],
                    "fan_speed": primary_gpu["fan_speed"],
                    "clock_sm": primary_gpu["clock_sm"],
                    "clock_mem": primary_gpu["clock_mem"],
                    "memory_utilization": primary_gpu["memory_utilization"],
                    "primary": primary_gpu,
                    "all_gpus": gpus,
                }
                self._status_cache = status
                self._status_cache_time = datetime.now()
            else:
                self._status_cache = None
                self._status_cache_time = None
        except Exception:
            logger.exception("Failed to refresh GPU cache using nvidia-smi")
            self._status_cache = None
            self._status_cache_time = None

    def start_cache_updater(self):
        if self._cache_update_task is None or self._cache_update_task.done():
            self._cache_update_task = asyncio.create_task(self._update_cache_loop())

    def stop_cache_updater(self):
        if self._cache_update_task and not self._cache_update_task.done():
            self._cache_update_task.cancel()
        self._nvml_collector.shutdown()

    def _parse_gpu_line(self, line: str) -> Optional[Dict]:
        parts = [part.strip() for part in line.split(',')]
        if len(parts) < 6:
            return None
        try:
            total_mb = int(parts[1])
            used_mb = int(parts[2])
            free_mb = int(parts[3])
        except (ValueError, IndexError):
            return None
        temperature = 0
        if len(parts) > 4 and parts[4].isdigit():
            temperature = int(parts[4])
        utilization = 0
        if len(parts) > 5 and parts[5].replace('%', '').isdigit():
            utilization = int(parts[5].replace('%', ''))
        power_draw = 0.0
        if len(parts) > 6:
            try:
                power_draw = float(parts[6])
            except ValueError:
                power_draw = 0.0
        power_limit = 0.0
        if len(parts) > 7:
            try:
                power_limit = float(parts[7])
            except ValueError:
                power_limit = 0.0
        fan_speed = int(parts[8]) if len(parts) > 8 and parts[8].isdigit() else 0
        clock_sm = int(parts[9]) if len(parts) > 9 and parts[9].isdigit() else 0
        clock_mem = int(parts[10]) if len(parts) > 10 and parts[10].isdigit() else 0
        return {
            "name": parts[0],
            "total_memory": total_mb * 1024 ** 2,
            "used_memory": used_mb * 1024 ** 2,
            "available_memory": free_mb * 1024 ** 2,
            "temperature": temperature,
            "utilization": utilization,
            "power_draw": int(power_draw),
            "power_limit": int(power_limit),
            "power_percent": int(power_draw / power_limit * 100) if power_limit > 0 else 0,
            "fan_speed": fan_speed,
            "clock_sm": clock_sm,
            "clock_mem": clock_mem,
            "memory_utilization": int(used_mb / total_mb * 100) if total_mb > 0 else 0,
        }

    def _get_gpu_status_sync(self) -> Optional[Dict]:
        if self._use_nvml:
            try:
                status = self._nvml_collector.collect_all()
                if status:
                    return status
            except Exception as exc:
                logger.warning("Synchronous NVML status collection failed: %s", exc)

        if not self._nvidia_smi_available:
            return None

        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu,power.draw,power.limit,fan.speed,clocks.sm,clocks.mem", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0 or not result.stdout.strip():
                return None
            gpus = []
            for line in result.stdout.strip().split('\n'):
                gpu_info = self._parse_gpu_line(line)
                if gpu_info:
                    gpus.append(gpu_info)
            if gpus:
                primary_gpu = gpus[0]
                return {
                    "status": "available",
                    "gpu_count": len(gpus),
                    "name": primary_gpu["name"],
                    "total_memory": primary_gpu["total_memory"],
                    "used_memory": primary_gpu["used_memory"],
                    "available_memory": primary_gpu["available_memory"],
                    "temperature": primary_gpu["temperature"],
                    "utilization": primary_gpu["utilization"],
                    "power_draw": primary_gpu["power_draw"],
                    "power_limit": primary_gpu["power_limit"],
                    "power_percent": primary_gpu["power_percent"],
                    "fan_speed": primary_gpu["fan_speed"],
                    "clock_sm": primary_gpu["clock_sm"],
                    "clock_mem": primary_gpu["clock_mem"],
                    "memory_utilization": primary_gpu["memory_utilization"],
                    "primary": primary_gpu,
                    "all_gpus": gpus,
                }
            return None
        except Exception:
            logger.exception("Synchronous GPU status collection failed")
            return None

    def get_gpu_status(self) -> Optional[Dict]:
        if self._cache_valid():
            return self._status_cache

        if self._status_cache is not None:
            cache_age = (datetime.now() - self._status_cache_time).total_seconds() if self._status_cache_time else float('inf')
            if cache_age < 300:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    try:
                        asyncio.create_task(self._refresh_cache())
                    except RuntimeError as exc:
                        logger.debug("Failed to schedule GPU cache refresh task: %s", exc)
                return self._status_cache

        return None

    async def _refresh_vllm_metrics(self):
        try:
            metrics = await self._vllm_scraper.scrape_and_cache()
            self._vllm_metrics_cache = metrics
            if self._status_cache and metrics:
                self._status_cache["vllm_metrics"] = metrics
        except Exception:
            logger.exception("Failed to refresh vLLM metrics cache")

    def get_vllm_metrics(self) -> Optional[Dict]:
        if self._vllm_metrics_cache:
            return self._vllm_metrics_cache
        return self._vllm_scraper.get_default_metrics()

    def get_gpu_processes(self) -> List[Dict]:
        status = self.get_gpu_status()
        if status and status.get("primary"):
            return status["primary"].get("processes", [])
        return []

    def get_gpu_enhanced_info(self) -> Optional[Dict]:
        status = self.get_gpu_status()
        if not status:
            return None
        enhanced = {
            "driver_version": status.get("driver_version", ""),
            "gpu_count": status.get("gpu_count", 0),
            "gpus": [],
        }
        for gpu in status.get("all_gpus", []):
            gpu_enhanced = {
                "index": gpu.get("index", 0),
                "name": gpu.get("name", ""),
                "ecc_errors": gpu.get("ecc_errors", 0),
                "throttle_reasons": gpu.get("throttle_reasons", []),
                "persistence_mode": gpu.get("persistence_mode", False),
                "pcie_rx_throughput": gpu.get("pcie_rx_throughput", 0),
                "pcie_tx_throughput": gpu.get("pcie_tx_throughput", 0),
                "bar1_total_memory": gpu.get("bar1_total_memory", 0),
                "bar1_used_memory": gpu.get("bar1_used_memory", 0),
                "vbios_version": gpu.get("vbios_version", ""),
                "processes": gpu.get("processes", []),
                "performance_state": gpu.get("performance_state", ""),
                "encoder_utilization": gpu.get("encoder_utilization", 0),
                "decoder_utilization": gpu.get("decoder_utilization", 0),
            }
            enhanced["gpus"].append(gpu_enhanced)
        return enhanced

    def get_memory_usage(self) -> Optional[Dict[str, int]]:
        status = self.get_gpu_status()
        if status:
            return {
                "total": status["total_memory"],
                "used": status["used_memory"],
                "available": status["available_memory"]
            }
        return None

    def get_gpu_summary(self) -> Dict:
        status = self.get_gpu_status()
        if status:
            current = {
                "name": status.get("name"),
                "gpu_count": status.get("gpu_count"),
                "utilization": status.get("utilization"),
                "temperature": status.get("temperature"),
                "power_draw": status.get("power_draw"),
                "power_limit": status.get("power_limit"),
                "power_percent": status.get("power_percent"),
                "memory_utilization": status.get("memory_utilization"),
                "used_memory": status.get("used_memory"),
                "available_memory": status.get("available_memory"),
                "total_memory": status.get("total_memory"),
                "fan_speed": status.get("fan_speed"),
                "clock_sm": status.get("clock_sm"),
                "clock_mem": status.get("clock_mem"),
            }
            primary = status.get("primary", {})
            if primary:
                for k in ["ecc_errors", "throttle_reasons", "persistence_mode",
                           "pcie_rx_throughput", "pcie_tx_throughput", "vbios_version",
                           "performance_state", "encoder_utilization", "decoder_utilization"]:
                    if k in primary:
                        current[k] = primary[k]
            
            health_score = self.get_health_score(status)
            
            return {
                "status": status.get("status", "unavailable"),
                "current": current,
                "health_score": health_score,
                "history": [],
            }
        return {
            "status": "unavailable",
            "current": None,
            "health_score": 0.0,
            "history": [],
        }

    def get_health_score(self, status: Optional[Dict] = None) -> float:
        """Calculate a health score based on GPU metrics."""
        if status is None:
            status = self.get_gpu_status()
            
        if not status or status.get("status") != "available":
            return 0.0
            
        primary = status.get("primary", {})
        temp = primary.get("temperature", 0)
        mem_util = primary.get("memory_utilization", 0)
        
        # Temperature score: 100 below 85C, drops to 0 at 105C
        temp_score = max(0, 100 - max(0, temp - 85) * 5)
        
        # Memory score: 100 below 90%, drops to 0 at 100%
        mem_score = max(0, 100 - max(0, mem_util - 90) * 10)
        
        # Throttling penalty
        throttle_reasons = primary.get("throttle_reasons", [])
        throttle_penalty = 0
        if any(r in ["hw_thermal_slowdown", "sw_thermal_slowdown"] for r in throttle_reasons):
            throttle_penalty = 50
        elif throttle_reasons:
            throttle_penalty = 10
            
        score = (temp_score * 0.5 + mem_score * 0.5) - throttle_penalty
        return round(max(0, min(100, score)), 2)

    def is_memory_available(self, required_bytes: int) -> bool:
        mem_info = self.get_memory_usage()
        if mem_info and mem_info.get("available", 0) >= required_bytes:
            return True
        return False

    def detect_fragmentation(self) -> float:
        status = self.get_gpu_status()
        if not status:
            return 0.0
        total = status["primary"]["total_memory"]
        used = status["primary"]["used_memory"]
        available = status["primary"]["available_memory"]
        fragmentation = (total - used - available) / total if total > 0 else 0.0
        self._fragmentation_history.append(fragmentation)
        if len(self._fragmentation_history) > 60:
            self._fragmentation_history = self._fragmentation_history[-60:]
        return fragmentation

    def get_average_fragmentation(self) -> float:
        if not self._fragmentation_history:
            return 0.0
        return sum(self._fragmentation_history) / len(self._fragmentation_history)

    def set_memory_strategy(self, strategy: str):
        valid_strategies = ["conservative", "balanced", "aggressive"]
        if strategy in valid_strategies:
            self._memory_strategy = strategy

    def get_memory_strategy(self) -> str:
        return self._memory_strategy

    def get_recommended_utilization(self) -> float:
        strategies = {
            "conservative": 0.80,
            "balanced": 0.90,
            "aggressive": 0.95
        }
        return strategies.get(self._memory_strategy, 0.90)

    async def optimize_memory(self, vllm_port: int = 8000) -> bool:
        if (datetime.now() - self._last_flush_time).total_seconds() < self._flush_interval:
            return False
        fragmentation = self.detect_fragmentation()
        avg_fragmentation = self.get_average_fragmentation()
        if fragmentation > 0.1 or avg_fragmentation > 0.05:
            await self._perform_memory_cleanup(vllm_port)
            self._last_flush_time = datetime.now()
            return True
        return False

    async def _flush_vllm_cache(self, port: int):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"http://localhost:{port}/v1/cache/flush")
        except Exception as exc:
            logger.warning("Failed to flush vLLM cache on port %s: %s", port, exc)

    async def _clear_vllm_kv_cache(self, port: int):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"http://localhost:{port}/v1/clear_cache")
        except Exception as exc:
            logger.warning("Failed to clear vLLM KV cache on port %s: %s", port, exc)

    async def _adjust_gpu_utilization(self, port: int, utilization: float):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"http://localhost:{port}/v1/control",
                    json={"gpu_memory_utilization": utilization}
                )
        except Exception as exc:
            logger.warning("Failed to adjust GPU utilization on port %s to %.2f: %s", port, utilization, exc)

    async def _perform_memory_cleanup(self, vllm_port: int = 8000):
        await self._flush_vllm_cache(vllm_port)
        await asyncio.sleep(1)
        await self._clear_vllm_kv_cache(vllm_port)
        await asyncio.sleep(1)
        await self._adjust_gpu_utilization(vllm_port, 0.9)

    async def optimize_memory_for_model(self, required_memory: int, vllm_port: int = 8000) -> bool:
        mem_info = self.get_memory_usage()
        if not mem_info:
            return False
        available = mem_info.get("available", 0)
        if available >= required_memory:
            return True
        await self._perform_memory_cleanup(vllm_port)
        await asyncio.sleep(3)
        self._status_cache = None
        self._status_cache_time = None
        await asyncio.sleep(1)
        mem_info = self.get_memory_usage()
        return mem_info and mem_info.get("available", 0) >= required_memory

    async def force_memory_cleanup(self, vllm_port: int = 8000) -> bool:
        await self._perform_memory_cleanup(vllm_port)
        await asyncio.sleep(5)
        self._status_cache = None
        self._status_cache_time = None
        return True

    def get_memory_optimization_status(self) -> Dict:
        return {
            "strategy": self._memory_strategy,
            "fragmentation": self.detect_fragmentation(),
            "avg_fragmentation": self.get_average_fragmentation(),
            "recommended_utilization": self.get_recommended_utilization(),
            "last_flush": self._last_flush_time.isoformat(),
            "flush_interval": self._flush_interval,
        }

    def set_redis_client(self, redis_client):
        self._redis_client = redis_client

    def _calculate_max_history_points(self, interval_seconds: int = 5) -> int:
        seconds_per_day = 24 * 60 * 60
        total_seconds = self._max_history_days * seconds_per_day
        return int(total_seconds / interval_seconds)

    def save_gpu_history(self, max_points: Optional[int] = None):
        if not self._history_enabled:
            return False
        if self._redis_client is None:
            return False
        try:
            status = self._get_gpu_status_sync()
            if not status:
                return False
            if max_points is None:
                max_points = self._calculate_max_history_points()
            timestamp = datetime.now().isoformat()
            history_entry = {
                "timestamp": timestamp,
                "utilization": status.get("utilization", 0),
                "temperature": status.get("temperature", 0),
                "power_draw": status.get("power_draw", 0),
                "power_percent": status.get("power_percent", 0),
                "memory_utilization": status.get("memory_utilization", 0),
                "used_memory": status.get("used_memory", 0),
                "available_memory": status.get("available_memory", 0),
                "total_memory": status.get("total_memory", 0),
                "fan_speed": status.get("fan_speed", 0),
                "clock_sm": status.get("clock_sm", 0),
                "clock_mem": status.get("clock_mem", 0),
            }
            primary = status.get("primary", {})
            if primary:
                for k in ["ecc_errors", "throttle_reasons"]:
                    if k in primary:
                        history_entry[k] = primary[k]
            
            vllm_metrics = self.get_vllm_metrics()
            if vllm_metrics and vllm_metrics.get("vllm_available"):
                history_entry["vllm_running_requests"] = int(vllm_metrics.get("running_requests", 0))
                history_entry["vllm_waiting_requests"] = int(vllm_metrics.get("waiting_requests", 0))
                history_entry["vllm_gpu_cache_usage"] = float(vllm_metrics.get("gpu_cache_usage", 0))
            
            health_score = self.get_health_score(status)
            history_entry["health_score"] = health_score
            
            self._redis_client.lpush("gpu:history", json.dumps(history_entry))
            self._redis_client.ltrim("gpu:history", 0, max_points - 1)
            ttl_30_days = 30 * 24 * 60 * 60
            self._redis_client.expire("gpu:history", ttl_30_days)
            summary_data = {
                "status": "available",
                "current": {
                    "name": status.get("name"),
                    "gpu_count": status.get("gpu_count"),
                    "utilization": status.get("utilization"),
                    "temperature": status.get("temperature"),
                    "power_draw": status.get("power_draw"),
                    "power_limit": status.get("power_limit"),
                    "power_percent": status.get("power_percent"),
                    "memory_utilization": status.get("memory_utilization"),
                    "used_memory": status.get("used_memory"),
                    "available_memory": status.get("available_memory"),
                    "total_memory": status.get("total_memory"),
                    "fan_speed": status.get("fan_speed"),
                    "clock_sm": status.get("clock_sm"),
                    "clock_mem": status.get("clock_mem"),
                }
            }
            ttl_1_hour = 60 * 60
            self._redis_client.set("gpu:summary", json.dumps(summary_data), expire=ttl_1_hour)
            if datetime.now() - self._last_history_cleanup >= self._history_cleanup_interval:
                self._clean_old_history()
                self._last_history_cleanup = datetime.now()
            return True
        except Exception:
            logger.exception("Failed to save GPU history")
            return False

    def _clean_old_history(self):
        try:
            if self._redis_client is None:
                return
            history_data = self._redis_client.lrange("gpu:history", 0, -1)
            if not history_data:
                return
            cutoff_time = datetime.now() - timedelta(days=self._max_history_days)
            valid_entries = []
            for item in history_data:
                try:
                    entry = json.loads(item)
                    entry_time = datetime.fromisoformat(entry.get("timestamp", ""))
                    if entry_time >= cutoff_time:
                        valid_entries.append(item)
                except Exception:
                    valid_entries.append(item)
            if len(valid_entries) < len(history_data):
                self._redis_client.delete("gpu:history")
                for entry in reversed(valid_entries):
                    self._redis_client.rpush("gpu:history", entry)
        except Exception:
            logger.exception("Failed to clean old GPU history")

    def set_history_enabled(self, enabled: bool):
        self._history_enabled = enabled

    def get_history_enabled(self) -> bool:
        return self._history_enabled

    def set_max_history_days(self, days: int):
        if days > 0:
            self._max_history_days = days

    def get_max_history_days(self) -> int:
        return self._max_history_days

    def get_gpu_history(self, count: int = 60, time_range: str = None) -> List[Dict]:
        if self._redis_client is None:
            return []
        try:
            max_counts = {
                'hour': 720,
                'day': 1000,
                'week': 1000,
                None: count
            }
            actual_count = min(count, max_counts.get(time_range, count))
            history_data = self._redis_client.lrange("gpu:history", 0, actual_count - 1)
            history = []
            for item in history_data:
                try:
                    history.append(json.loads(item))
                except Exception:
                    logger.debug("Skipping invalid GPU history entry")
            return history[::-1]
        except Exception:
            logger.exception("Failed to load GPU history")
            return []


class SystemMonitor:
    def __init__(self, redis_client=None):
        self._redis_client = redis_client
        self._max_history_days = 7
        self._history_enabled = True

    def set_redis_client(self, redis_client):
        self._redis_client = redis_client

    def _calculate_max_history_points(self, interval_seconds: int = 5) -> int:
        seconds_per_day = 24 * 60 * 60
        total_seconds = self._max_history_days * seconds_per_day
        return int(total_seconds / interval_seconds)

    def save_system_history(self):
        if not self._history_enabled or self._redis_client is None:
            return False
        try:
            import psutil
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            history_entry = {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used // (1024 ** 2),
                "memory_available_mb": memory.available // (1024 ** 2)
            }
            max_points = self._calculate_max_history_points()
            self._redis_client.lpush("system:history", json.dumps(history_entry))
            self._redis_client.ltrim("system:history", 0, max_points - 1)
            ttl_30_days = 30 * 24 * 60 * 60
            self._redis_client.expire("system:history", ttl_30_days)
            return True
        except Exception:
            logger.exception("Failed to save system history")
            return False

    def get_system_history(self, count: int = 60) -> List[Dict]:
        if self._redis_client is None:
            return []
        try:
            history_data = self._redis_client.lrange("system:history", 0, count - 1)
            history = [json.loads(item) for item in history_data]
            return history[::-1]
        except Exception:
            logger.exception("Failed to load system history")
            return []

    def set_history_enabled(self, enabled: bool):
        self._history_enabled = enabled

    def get_history_enabled(self) -> bool:
        return self._history_enabled

    def set_max_history_days(self, days: int):
        if days > 0:
            self._max_history_days = days

    def get_max_history_days(self) -> int:
        return self._max_history_days
