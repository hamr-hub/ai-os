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

    _VLLM_ENV_VARS = {
        "VLLM_USE_V1": "1",
        "NCCL_P2P_DISABLE": "1",
        "NCCL_SOCKET_REUSEPORT": "1",
        "NCCL_ASYNC_ERROR_HANDLING": "1",
        "NCCL_IB_DISABLE": "1",
        "CUDA_MANAGED_FORCE_DEVICE_ALLOC": "1",
        "OMP_NUM_THREADS": "16",
        "VLLM_NO_FLASHINFER": "1",
        "FLASHINFER_DISABLE": "1",
    }

    _VLLM_SERVE_FIXED_ARGS = [
        "--trust-remote-code",
        "--host", "0.0.0.0",
        "--enforce-eager",
        "--kv-cache-dtype", "auto",
    ]

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
        self._pgids: Dict[str, int] = {}

    def _get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        if self._config:
            if hasattr(self._config, 'get_model'):
                return self._config.get_model(model_name)
            elif isinstance(self._config, dict):
                return self._config.get('models', {}).get(model_name)
        return None

    def _get_vllm_config(self) -> Dict:
        if not self._config:
            return {}
        if hasattr(self._config, 'vllm'):
            val = self._config.vllm
            if val is None:
                return {}
            return val if isinstance(val, dict) else val.model_dump()
        elif isinstance(self._config, dict):
            return self._config.get('vllm', {})
        return {}

    def _get_settings(self) -> Dict:
        if not self._config:
            return {}
        if hasattr(self._config, 'settings'):
            val = self._config.settings
            if val is None:
                return {}
            return val if isinstance(val, dict) else val.model_dump()
        elif isinstance(self._config, dict):
            return self._config.get('settings', {})
        return {}

    def _get_model_base_path(self) -> str:
        vllm_config = self._get_vllm_config()
        return vllm_config.get("model_base_path", "/mnt/pve_models")

    def _get_model_path(self, model_name: str) -> str:
        if model_name in self._model_paths:
            return self._model_paths[model_name]
        model_cfg = self._get_model_config(model_name)
        if model_cfg:
            if hasattr(model_cfg, 'model_path') and model_cfg.model_path:
                return model_cfg.model_path
            elif isinstance(model_cfg, dict):
                return model_cfg.get("model_path") or os.path.join(self._get_model_base_path(), model_name)
        return os.path.join(self._get_model_base_path(), model_name)

    def _get_vllm_env(self, model_name: str) -> Dict[str, str]:
        env = {**os.environ, **self._VLLM_ENV_VARS}
        vllm_config = self._get_vllm_config()
        env_vars = vllm_config.get("env_vars", {})
        if isinstance(env_vars, dict):
            env.update({str(key): str(value) for key, value in env_vars.items() if value is not None})
        env["HF_ENDPOINT"] = os.environ.get(
            "HF_ENDPOINT",
            vllm_config.get("hf_endpoint", "https://hf-mirror.com"),
        )
        model_cfg = self._get_model_config(model_name)
        vllm_params = {}
        if model_cfg and hasattr(model_cfg, 'vllm_params') and model_cfg.vllm_params:
            vllm_params = model_cfg.vllm_params
        elif isinstance(model_cfg, dict):
            vllm_params = model_cfg.get("vllm_params", {})
        attention_backend = vllm_params.get("attention_backend")
        if attention_backend:
            env["VLLM_ATTENTION_BACKEND"] = attention_backend
        model_env_vars = vllm_params.get("env_vars", {})
        if isinstance(model_env_vars, dict):
            env.update({str(key): str(value) for key, value in model_env_vars.items() if value is not None})
        if "use_flashinfer_moe_fp4" in vllm_params:
            env["VLLM_USE_FLASHINFER_MOE_FP4"] = "1" if vllm_params.get("use_flashinfer_moe_fp4") else "0"
        if vllm_params.get("flashinfer_moe_backend"):
            env["VLLM_FLASHINFER_MOE_BACKEND"] = str(vllm_params["flashinfer_moe_backend"])
        if vllm_params.get("nvfp4_gemm_backend"):
            env["VLLM_NVFP4_GEMM_BACKEND"] = str(vllm_params["nvfp4_gemm_backend"])
        if "use_nvfp4_ct_emulations" in vllm_params:
            env["VLLM_USE_NVFP4_CT_EMULATIONS"] = "1" if vllm_params.get("use_nvfp4_ct_emulations") else "0"
        venv_path = vllm_config.get("venv_path")
        if venv_path and os.path.isfile(os.path.join(venv_path, "bin", "activate")):
            env["VLLM_ENV_PATH"] = venv_path
            env["PATH"] = os.path.join(venv_path, "bin") + ":" + env.get("PATH", "")
        return env

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
        cmd = ["vllm", "serve", model_path, "--port", str(port)]
        cmd.extend(self._VLLM_SERVE_FIXED_ARGS)

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

        moe_backend = vllm_params.get("moe_backend")
        if moe_backend and moe_backend != "auto":
            cmd.extend(["--moe-backend", str(moe_backend)])

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

        max_num_seqs = vllm_params.get("max_num_seqs")
        if max_num_seqs:
            cmd.extend(["--max-num-seqs", str(max_num_seqs)])

        max_num_batched_tokens = vllm_params.get("max_num_batched_tokens")
        if max_num_batched_tokens:
            cmd.extend(["--max-num-batched-tokens", str(max_num_batched_tokens)])

        enable_chunked_prefill = vllm_params.get("enable_chunked_prefill")
        if enable_chunked_prefill:
            cmd.extend(["--enable-chunked-prefill"])

        if hasattr(cfg, 'supports_tool_calling') and cfg.supports_tool_calling:
            tool_parser = vllm_params.get("tool_call_parser", "hermes")
            if tool_parser:
                cmd.extend(["--enable-auto-tool-choice", "--tool-call-parser", tool_parser])

        if hasattr(cfg, 'supports_images') and cfg.supports_images:
            cmd.extend(["--limit-mm-per-prompt", "10"])

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
            "--host", "0.0.0.0",
            "--port", str(port),
        ]

        sglang_params = {}
        if hasattr(cfg, 'sglang_params') and cfg.sglang_params:
            sglang_params = cfg.sglang_params
        elif isinstance(cfg, dict):
            sglang_params = cfg.get("sglang_params", {})

        tp = sglang_params.get("tp_size", sglang_params.get("tensor_parallel_size", 1))
        if tp > 1:
            cmd.extend(["--tp", str(tp)])

        dp = sglang_params.get("dp_size", 1)
        if dp > 1:
            cmd.extend(["--dp-size", str(dp)])

        mem_frac = sglang_params.get(
            "mem_fraction_static",
            sglang_params.get("gpu_memory_utilization", self._get_gpu_memory_utilization()),
        )
        cmd.extend(["--mem-fraction-static", str(mem_frac)])

        ctx_len = sglang_params.get("context_length")
        if ctx_len:
            cmd.extend(["--context-length", str(ctx_len)])

        if sglang_params.get("trust_remote_code", False):
            cmd.extend(["--trust-remote-code"])

        dtype = sglang_params.get("dtype")
        if dtype and dtype != "auto":
            cmd.extend(["--dtype", dtype])

        quant = sglang_params.get("quantization")
        if quant:
            cmd.extend(["--quantization", quant])

        kv_dtype = sglang_params.get("kv_cache_dtype")
        if kv_dtype and kv_dtype != "auto":
            cmd.extend(["--kv-cache-dtype", kv_dtype])

        load_fmt = sglang_params.get("load_format")
        if load_fmt and load_fmt != "auto":
            cmd.extend(["--load-format", load_fmt])

        served_name = sglang_params.get("served_model_name")
        if served_name:
            cmd.extend(["--served-model-name", served_name])

        max_running = sglang_params.get("max_running_requests")
        if max_running:
            cmd.extend(["--max-running-requests", str(max_running)])

        max_total = sglang_params.get("max_total_tokens")
        if max_total:
            cmd.extend(["--max-total-tokens", str(max_total)])

        chunked = sglang_params.get("chunked_prefill_size")
        if chunked is not None:
            cmd.extend(["--chunked-prefill-size", str(chunked)])

        sched = sglang_params.get("schedule_policy")
        if sched and sched != "fcfs":
            cmd.extend(["--schedule-policy", sched])

        if sglang_params.get("disable_radix_cache", False):
            cmd.extend(["--disable-radix-cache"])

        if sglang_params.get("disable_overlap_schedule", False):
            cmd.extend(["--disable-overlap-schedule"])

        if sglang_params.get("enable_torch_compile", False):
            cmd.extend(["--enable-torch-compile"])

        if sglang_params.get("disable_cuda_graph", False):
            cmd.extend(["--disable-cuda-graph"])

        tool_parser = sglang_params.get("tool_call_parser")
        if tool_parser:
            cmd.extend(["--tool-call-parser", tool_parser])

        multimodal = sglang_params.get("enable_multimodal")
        if multimodal is True:
            cmd.extend(["--enable-multimodal"])
        elif multimodal is False:
            cmd.extend(["--enable-multimodal", "false"])

        reasoning = sglang_params.get("reasoning_parser")
        if reasoning:
            cmd.extend(["--reasoning-parser", reasoning])

        log_level = sglang_params.get("log_level")
        if log_level and log_level != "info":
            cmd.extend(["--log-level", log_level])

        watchdog = sglang_params.get("watchdog_timeout")
        if watchdog and watchdog != 300:
            cmd.extend(["--watchdog-timeout", str(watchdog)])

        if sglang_params.get("enable_metrics", False):
            cmd.extend(["--enable-metrics"])

        if sglang_params.get("skip_server_warmup", False):
            cmd.extend(["--skip-server-warmup"])

        lora_paths_val = sglang_params.get("lora_paths")
        if lora_paths_val:
            cmd.extend(["--lora-paths", str(lora_paths_val)])

        max_lora_rank = sglang_params.get("max_lora_rank")
        if max_lora_rank:
            cmd.extend(["--max-lora-rank", str(max_lora_rank)])

        download_dir = sglang_params.get("download_dir")
        if download_dir:
            cmd.extend(["--download-dir", download_dir])

        _HANDLED_KEYS = {
            "tp_size", "tensor_parallel_size", "dp_size",
            "mem_fraction_static", "gpu_memory_utilization",
            "context_length", "trust_remote_code", "dtype",
            "quantization", "kv_cache_dtype", "load_format",
            "served_model_name", "max_running_requests",
            "max_total_tokens", "chunked_prefill_size",
            "schedule_policy", "disable_radix_cache",
            "disable_overlap_schedule", "enable_torch_compile",
            "disable_cuda_graph", "tool_call_parser",
            "enable_multimodal", "reasoning_parser",
            "log_level", "watchdog_timeout", "enable_metrics",
            "skip_server_warmup", "lora_paths", "max_lora_rank",
            "download_dir",
        }

        for key, val in sglang_params.items():
            if val is None or key in _HANDLED_KEYS:
                continue
            if isinstance(val, bool):
                if val:
                    cmd.extend(["--" + key.replace("_", "-")])
            else:
                cmd.extend(["--" + key.replace("_", "-"), str(val)])

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
        settings = self._get_settings()
        if settings:
            return settings.get("gpu_memory_utilization", 0.9)
        return 0.9

    def start_service(
        self, service_name: str, model_name: str,
        engine_type: str, port: int,
        model_path: Optional[str] = None,
    ) -> Dict:
        if model_path:
            self._model_paths[model_name] = model_path

        port_service = self.get_service_by_port(port)
        if port_service and port_service.get("status") == "running":
            existing_name = port_service.get("service_name")
            if existing_name != service_name:
                self.stop_service(existing_name)
                time.sleep(2)

        existing = self.get_service_status(service_name)
        if existing.get("status") == "running":
            self.stop_service(service_name)
            time.sleep(2)

        cmd = self.build_command(model_name, engine_type, port)
        logger.info("Starting %s engine for %s: %s", engine_type, model_name, " ".join(cmd))

        if engine_type == "vllm":
            env = self._get_vllm_env(model_name)
        else:
            env = {**os.environ, "HF_ENDPOINT": os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")}

        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "logs",
            f"vllm-{model_name.split('/')[-1]}",
        )
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, f"{engine_type}_{time.strftime('%Y%m%d_%H%M%S')}.log")
        try:
            log_fd = open(log_file_path, "a")
        except OSError:
            log_fd = subprocess.PIPE

        try:
            process = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=log_fd,
                env=env,
                preexec_fn=os.setsid,
            )
            self._processes[service_name] = process
            self._pgids[service_name] = os.getpgid(process.pid)
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
                "log_file": log_file_path,
            }
        except Exception as e:
            logger.error("Failed to start %s: %s", service_name, e)
            return {"status": "error", "message": str(e)}

    def stop_service(self, service_name: str, timeout: int = _GRACEFUL_TIMEOUT) -> bool:
        process = self._processes.get(service_name)
        if not process:
            return False

        pgid = self._pgids.get(service_name)
        pid = process.pid
        logger.info("Stopping service %s (pid=%s, pgid=%s)", service_name, pid, pgid)

        try:
            if pgid and pgid > 0:
                os.killpg(pgid, signal.SIGINT)
            else:
                process.send_signal(signal.SIGINT)
        except OSError:
            pass

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning(
                "Service %s did not exit after SIGINT+%ds, sending SIGKILL to process group",
                service_name, timeout,
            )
            try:
                if pgid and pgid > 0:
                    os.killpg(pgid, signal.SIGKILL)
                else:
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
        pgid = self._pgids.get(service_name)
        try:
            if pgid and pgid > 0:
                os.killpg(pgid, signal.SIGKILL)
            else:
                process.kill()
            process.wait(timeout=5)
        except Exception:
            pass
        self._cleanup_service(service_name)
        return True

    def _cleanup_service(self, service_name: str, keep_restart_info: bool = False):
        self._processes.pop(service_name, None)
        self._pgids.pop(service_name, None)
        if not keep_restart_info:
            self._engine_types.pop(service_name, None)
            self._ports.pop(service_name, None)
            self._models.pop(service_name, None)
            self._model_paths.pop(service_name, None)
            self._start_times.pop(service_name, None)
            self._health_status.pop(service_name, None)
            self._restart_counts.pop(service_name, None)

    def get_service_status(self, service_name: str) -> Dict:
        process = self._processes.get(service_name)
        if not process:
            return {"status": "not_found", "service_name": service_name}

        poll_result = process.poll()
        if poll_result is not None:
            self._cleanup_service(service_name, keep_restart_info=True)
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
            "pgid": self._pgids.get(service_name, 0),
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
