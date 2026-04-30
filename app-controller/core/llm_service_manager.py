import subprocess
import signal
import time
import logging
import os
import asyncio
import httpx
from typing import Dict, Optional, List, Any

from core.config import AppConfig, ModelConfig

logger = logging.getLogger("ai_controller.llm_service_manager")

_MAX_RESTART_ATTEMPTS = 3
_RESTART_COOLDOWN = 60
_GRACEFUL_TIMEOUT = 15
_HEALTH_CHECK_TIMEOUT = 2


class LLMServiceManager:

    def __init__(self, config: Optional[AppConfig] = None):
        self._config = config
        self._processes: Dict[str, subprocess.Popen] = {}
        self._engine_types: Dict[str, str] = {}
        self._ports: Dict[str, int] = {}
        self._models: Dict[str, str] = {}
        self._start_times: Dict[str, float] = {}
        self._restart_counts: Dict[str, int] = {}
        self._health_status: Dict[str, str] = {}
        self._model_paths: Dict[str, str] = {}

    def _get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        if self._config:
            return self._config.get_model(model_name)
        return None

    def _get_model_base_path(self) -> str:
        if self._config and self._config.vllm:
            return self._config.vllm.get("model_base_path", "/mnt/pve_models")
        return "/mnt/pve_models"

    def _get_model_path(self, model_name: str) -> str:
        if model_name in self._model_paths:
            return self._model_paths[model_name]
        model_cfg = self._get_model_config(model_name)
        if model_cfg and model_cfg.model_path:
            return model_cfg.model_path
        return os.path.join(self._get_model_base_path(), model_name)

    def build_command(self, model_name: str, engine_type: str, port: int) -> List[str]:
        model_path = self._get_model_path(model_name)
        model_cfg = self._get_model_config(model_name)
        cfg_dict = model_cfg if model_cfg else {}

        if engine_type == "vllm":
            return self._build_vllm_command(model_path, port, cfg_dict)
        elif engine_type == "sglang":
            return self._build_sglang_command(model_path, port, cfg_dict)
        elif engine_type == "llamacpp":
            return self._build_llamacpp_command(model_path, port, cfg_dict)
        else:
            raise ValueError(f"Unsupported engine type: {engine_type}")

    def _build_vllm_command(self, model_path: str, port: int, cfg: Any) -> List[str]:
        cmd = [
            "python", "-m", "vllm.entrypoints.openai.api_server",
            "--model", model_path,
            "--port", str(port),
        ]

        vllm_params = {}
        if hasattr(cfg, 'vllm_params') and cfg.vllm_params:
            vllm_params = cfg.vllm_params
        elif isinstance(cfg, dict):
            vllm_params = cfg.get("vllm_params", {})

        dtype = vllm_params.get("dtype", "auto")
        if dtype and dtype != "auto":
            cmd.extend(["--dtype", dtype])

        quant = vllm_params.get("quantization")
        if quant:
            cmd.extend(["--quantization", quant])

        max_model_len = vllm_params.get("max_model_len")
        if max_model_len:
            cmd.extend(["--max-model-len", str(max_model_len)])

        tp = vllm_params.get("tensor_parallel_size", 1)
        if tp > 1:
            cmd.extend(["--tensor-parallel-size", str(tp)])

        gpu_util = vllm_params.get(
            "gpu_memory_utilization",
            self._get_gpu_memory_utilization(),
        )
        cmd.extend(["--gpu-memory-utilization", str(gpu_util)])

        if hasattr(cfg, 'supports_tool_calling') and cfg.supports_tool_calling:
            tool_parser = vllm_params.get("tool_call_parser", "hermes")
            cmd.extend(["--tool-call-parser", tool_parser])
            cmd.extend(["--enable-tool-call"])

        if hasattr(cfg, 'supports_images') and cfg.supports_images:
            if "limit-mm-per-prompt" not in str(cmd):
                cmd.extend(["--limit-mm-per-prompt", "10"])

        for key, val in vllm_params.items():
            if val is None or key in (
                "dtype", "quantization", "tensor_parallel_size",
                "gpu_memory_utilization", "tool_call_parser",
                "max_model_len", "limit_mm_per_prompt",
            ):
                continue
            arg_name = "--" + key.replace("_", "-")
            cmd.extend([arg_name, str(val)])

        extra_args = []
        if hasattr(cfg, 'extra_args') and cfg.extra_args:
            extra_args = cfg.extra_args
        elif isinstance(cfg, dict):
            extra_args = cfg.get("extra_args", [])
        cmd.extend(extra_args)

        return cmd

    def _build_sglang_command(self, model_path: str, port: int, cfg: Any) -> List[str]:
        cmd = [
            "python", "-m", "sglang.launch_server",
            "--model-path", model_path,
            "--port", str(port),
        ]

        sglang_params = {}
        if hasattr(cfg, 'sglang_params') and cfg.sglang_params:
            sglang_params = cfg.sglang_params
        elif isinstance(cfg, dict):
            sglang_params = cfg.get("sglang_params", {})

        tp = sglang_params.get("tensor_parallel_size", 1)
        if tp > 1:
            cmd.extend(["--tp", str(tp)])

        gpu_util = sglang_params.get(
            "gpu_memory_utilization",
            self._get_gpu_memory_utilization(),
        )
        cmd.extend(["--mem-fraction-static", str(gpu_util)])

        ctx_len = sglang_params.get("context_length")
        if ctx_len:
            cmd.extend(["--context-length", str(ctx_len)])

        for key, val in sglang_params.items():
            if val is None or key in (
                "tensor_parallel_size", "gpu_memory_utilization", "context_length",
            ):
                continue
            arg_name = "--" + key.replace("_", "-")
            cmd.extend([arg_name, str(val)])

        return cmd

    def _build_llamacpp_command(self, model_path: str, port: int, cfg: Any) -> List[str]:
        cmd = [
            "./llama-server",
            "-m", model_path,
            "--port", str(port),
            "--host", "0.0.0.0",
        ]

        llamacpp_params = {}
        if hasattr(cfg, 'llamacpp_params') and cfg.llamacpp_params:
            llamacpp_params = cfg.llamacpp_params
        elif isinstance(cfg, dict):
            llamacpp_params = cfg.get("llamacpp_params", {})

        n_gpu = llamacpp_params.get("n_gpu_layers", -1)
        if hasattr(cfg, 'n_gpu_layers') and cfg.n_gpu_layers != -1:
            n_gpu = cfg.n_gpu_layers
        cmd.extend(["-ngl", str(n_gpu)])

        ctx = llamacpp_params.get("ctx_size", 4096)
        if hasattr(cfg, 'ctx_size') and cfg.ctx_size:
            ctx = cfg.ctx_size
        cmd.extend(["-c", str(ctx)])

        threads = llamacpp_params.get("n_threads")
        if hasattr(cfg, 'n_threads') and cfg.n_threads:
            threads = cfg.n_threads
        if threads:
            cmd.extend(["-t", str(threads)])

        for key, val in llamacpp_params.items():
            if val is None or key in ("n_gpu_layers", "ctx_size", "n_threads"):
                continue
            cmd.extend([f"--{key.replace('_', '-')}", str(val)])

        return cmd

    def _get_gpu_memory_utilization(self) -> float:
        if self._config:
            return self._config.settings.gpu_memory_utilization
        return 0.9

    def start_service(
        self, service_name: str, model_name: str,
        engine_type: str, port: int,
        model_path: Optional[str] = None,
    ) -> Dict:
        if model_path:
            self._model_paths[model_name] = model_path
        cmd = self.build_command(model_name, engine_type, port)
        logger.info("Starting %s engine for %s: %s", engine_type, model_name, " ".join(cmd))

        env = {**os.environ, "HF_ENDPOINT": os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")}
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            self._processes[service_name] = process
            self._engine_types[service_name] = engine_type
            self._ports[service_name] = port
            self._models[service_name] = model_name
            self._start_times[service_name] = time.time()
            self._restart_counts[service_name] = 0
            self._health_status[service_name] = "starting"

            return {
                "status": "started",
                "pid": process.pid,
                "service_name": service_name,
                "engine_type": engine_type,
                "model": model_name,
                "port": port,
            }
        except Exception as e:
            logger.error("Failed to start %s: %s", service_name, e)
            return {"status": "error", "message": str(e)}

    def stop_service(self, service_name: str, timeout: int = _GRACEFUL_TIMEOUT) -> bool:
        process = self._processes.get(service_name)
        if not process:
            return False

        pid = process.pid
        logger.info("Stopping service %s (pid=%s)", service_name, pid)

        try:
            process.send_signal(signal.SIGINT)
        except OSError:
            pass

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning(
                "Service %s did not exit after SIGINT+%ds, sending SIGKILL",
                service_name, timeout,
            )
            try:
                process.kill()
            except OSError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass

        self._cleanup_service(service_name)
        return True

    def force_stop_service(self, service_name: str) -> bool:
        process = self._processes.get(service_name)
        if not process:
            return False
        try:
            process.kill()
            process.wait(timeout=5)
        except Exception:
            pass
        self._cleanup_service(service_name)
        return True

    def _cleanup_service(self, service_name: str):
        self._processes.pop(service_name, None)
        self._engine_types.pop(service_name, None)
        self._ports.pop(service_name, None)
        self._models.pop(service_name, None)
        self._start_times.pop(service_name, None)
        self._health_status.pop(service_name, None)

    def get_service_status(self, service_name: str) -> Dict:
        process = self._processes.get(service_name)
        if not process:
            return {"status": "not_found", "service_name": service_name}

        poll_result = process.poll()
        if poll_result is not None:
            self._cleanup_service(service_name)
            return {
                "status": "stopped",
                "service_name": service_name,
                "exit_code": poll_result,
            }

        uptime = time.time() - self._start_times.get(service_name, time.time())
        return {
            "status": "running",
            "service_name": service_name,
            "engine_type": self._engine_types.get(service_name, ""),
            "pid": process.pid,
            "port": self._ports.get(service_name, 0),
            "model": self._models.get(service_name, ""),
            "uptime_seconds": round(uptime, 1),
            "health": self._health_status.get(service_name, "unknown"),
        }

    async def check_http_health(self, service_name: str) -> bool:
        port = self._ports.get(service_name)
        if not port:
            return False
        process = self._processes.get(service_name)
        if not process or process.poll() is not None:
            return False

        url = f"http://localhost:{port}/v1/models"
        try:
            async with httpx.AsyncClient(timeout=_HEALTH_CHECK_TIMEOUT) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    self._health_status[service_name] = "healthy"
                    return True
        except Exception:
            pass

        self._health_status[service_name] = "unhealthy"
        return False

    def check_health(self, service_name: str) -> bool:
        process = self._processes.get(service_name)
        if not process:
            return False
        return process.poll() is None

    def auto_restart(self, service_name: str) -> Dict:
        count = self._restart_counts.get(service_name, 0)
        if count >= _MAX_RESTART_ATTEMPTS:
            logger.error(
                "Service %s exceeded max restart attempts (%d)",
                service_name, _MAX_RESTART_ATTEMPTS,
            )
            return {"status": "max_restarts_exceeded", "service_name": service_name}

        model = self._models.get(service_name, "")
        engine = self._engine_types.get(service_name, "vllm")
        port = self._ports.get(service_name, 8000)

        self._restart_counts[service_name] = count + 1
        return self.start_service(service_name, model, engine, port)

    def get_restart_count(self, service_name: str) -> int:
        return self._restart_counts.get(service_name, 0)

    def reset_restart_count(self, service_name: str):
        self._restart_counts[service_name] = 0

    def list_services(self) -> List[Dict]:
        result = []
        for name in list(self._processes.keys()):
            result.append(self.get_service_status(name))
        return result

    def list_services_by_engine(self, engine_type: str) -> List[Dict]:
        result = []
        for name, et in self._engine_types.items():
            if et == engine_type:
                result.append(self.get_service_status(name))
        return result

    def get_service_by_model(self, model_name: str) -> Optional[Dict]:
        for name, model in self._models.items():
            if model == model_name:
                return self.get_service_status(name)
        return None

    def get_service_by_port(self, port: int) -> Optional[Dict]:
        for name, p in self._ports.items():
            if p == port:
                return self.get_service_status(name)
        return None

    async def wait_for_ready(
        self, service_name: str, port: int, timeout: int = 120,
    ) -> bool:
        url = f"http://localhost:{port}/v1/models"
        start_time = time.time()
        while time.time() - start_time < timeout:
            process = self._processes.get(service_name)
            if process and process.poll() is not None:
                logger.error("Service %s process died during readiness wait", service_name)
                return False
            try:
                async with httpx.AsyncClient(timeout=_HEALTH_CHECK_TIMEOUT) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        self._health_status[service_name] = "healthy"
                        return True
            except Exception:
                pass
            await asyncio.sleep(2)
        return False

    def get_process_stderr(self, service_name: str, max_lines: int = 50) -> Optional[str]:
        process = self._processes.get(service_name)
        if not process:
            return None
        try:
            stderr_bytes = process.stderr.read1(8192) if hasattr(process.stderr, 'read1') else b""
            if stderr_bytes:
                lines = stderr_bytes.decode('utf-8', errors='replace').split('\n')
                return '\n'.join(lines[-max_lines:])
        except Exception:
            pass
        return None

    def update_config(
        self, service_name: str,
        engine_type: Optional[str] = None,
        model_path: Optional[str] = None,
        port: Optional[int] = None,
        extra_params: Optional[Dict] = None,
    ) -> Dict:
        changed = {}
        if service_name not in self._processes:
            return {"success": False, "reason": "service_not_found"}
        if engine_type and engine_type != self._engine_types.get(service_name):
            self._engine_types[service_name] = engine_type
            changed["engine_type"] = engine_type
        if port and port != self._ports.get(service_name):
            self._ports[service_name] = port
            changed["port"] = port
        model = self._models.get(service_name, "")
        if model_path:
            self._model_paths[model] = model_path
            changed["model_path"] = model_path
        logger.info("Service %s config updated: %s", service_name, changed)
        return {"success": True, "service_name": service_name, "changes": changed}

    def get_current_config(self, service_name: str) -> Optional[Dict]:
        process = self._processes.get(service_name)
        if not process:
            return None
        model = self._models.get(service_name, "")
        return {
            "service_name": service_name,
            "engine_type": self._engine_types.get(service_name, "vllm"),
            "model": model,
            "model_path": self._get_model_path(model),
            "port": self._ports.get(service_name, 8000),
            "status": "running" if process.poll() is None else "stopped",
            "pid": process.pid,
            "uptime_seconds": round(time.time() - self._start_times.get(service_name, time.time()), 1),
        }

    def update_model_path(self, model_name: str, new_path: str) -> bool:
        self._model_paths[model_name] = new_path
        logger.info("Updated model path for %s: %s", model_name, new_path)
        return True

    def cleanup_all(self):
        for name in list(self._processes.keys()):
            self.stop_service(name)
