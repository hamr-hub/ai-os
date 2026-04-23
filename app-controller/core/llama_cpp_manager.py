"""
llama_cpp 模型管理模块
- 管理 llama-cpp-python OpenAI 兼容服务器进程（启动/停止/切换）
- 支持多模型并行运行在不同端口
- 提供模型信息（显存需求、路径、支持的功能等）
- 模型切换后自动自测验证
"""

import os
import subprocess
import signal
import asyncio
import httpx
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from core.cache_service import cache_service

logger = logging.getLogger("ai_controller.llama_cpp")

model_switch_lock = asyncio.Lock()

LLAMA_CPP_MODELS_BASE_PATH = "/mnt/pve_models"

LLAMA_CPP_SERVER_BIN = "python"

LLAMA_CPP_SERVER_MODULE = "llama_cpp.server"


class LlamaCppProcessManager:
    def __init__(self):
        self._processes: Dict[int, subprocess.Popen] = {}
        self._model_by_port: Dict[int, str] = {}
        self._port_by_model: Dict[str, int] = {}
        self._configs: Dict[str, Dict] = {}

    def register_model(self, model_name: str, config: Dict):
        self._configs[model_name] = config
        port = config.get("port")
        if port:
            self._port_by_model[model_name] = port
            self._model_by_port[port] = model_name

    def unregister_model(self, model_name: str):
        config = self._configs.pop(model_name, None)
        if config:
            port = config.get("port")
            if port:
                self._port_by_model.pop(model_name, None)
                self._model_by_port.pop(port, None)

    def get_model_port(self, model_name: str) -> Optional[int]:
        return self._port_by_model.get(model_name)

    def get_model_by_port(self, port: int) -> Optional[str]:
        return self._model_by_port.get(port)

    def start_server(self, model_name: str) -> bool:
        config = self._configs.get(model_name)
        if not config:
            logger.error(f"No config registered for model: {model_name}")
            return False

        port = config.get("port")
        model_path = config.get("model_path", os.path.join(LLAMA_CPP_MODELS_BASE_PATH, model_name))

        if port in self._processes:
            proc = self._processes[port]
            if proc.poll() is None:
                logger.info(f"llama_cpp server already running on port {port} for model {model_name}")
                return True
            else:
                self._cleanup_process(port)

        n_gpu_layers = config.get("n_gpu_layers", -1)
        ctx_size = config.get("ctx_size", 4096)
        n_threads = config.get("n_threads", os.cpu_count() or 4)
        host = config.get("host", "0.0.0.0")

        cmd = [
            LLAMA_CPP_SERVER_BIN, "-m", LLAMA_CPP_SERVER_MODULE,
            "--model", model_path,
            "--host", host,
            "--port", str(port),
            "--n_gpu_layers", str(n_gpu_layers),
            "--ctx_size", str(ctx_size),
            "--n_threads", str(n_threads),
        ]

        extra_args = config.get("extra_args", [])
        cmd.extend(extra_args)

        logger.info(f"Starting llama_cpp server for {model_name}: {' '.join(cmd)}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setpgrp if os.name != 'nt' else None,
            )
            self._processes[port] = proc
            logger.info(f"llama_cpp server started for {model_name} on port {port}, PID={proc.pid}")
            return True
        except Exception as e:
            logger.error(f"Failed to start llama_cpp server for {model_name}: {e}")
            return False

    def stop_server(self, model_name: str) -> bool:
        port = self._port_by_model.get(model_name)
        if not port:
            logger.warning(f"No port registered for model: {model_name}")
            return False

        proc = self._processes.get(port)
        if not proc:
            logger.info(f"llama_cpp server not running for model {model_name}")
            return True

        if proc.poll() is not None:
            self._cleanup_process(port)
            logger.info(f"llama_cpp server already stopped for model {model_name}")
            return True

        try:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

            self._cleanup_process(port)
            logger.info(f"llama_cpp server stopped for {model_name} on port {port}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop llama_cpp server for {model_name}: {e}")
            return False

    def is_server_running(self, model_name: str) -> bool:
        port = self._port_by_model.get(model_name)
        if not port:
            return False

        proc = self._processes.get(port)
        if not proc:
            return False

        if proc.poll() is not None:
            self._cleanup_process(port)
            return False

        return True

    def get_server_status(self, model_name: str) -> Dict[str, Any]:
        port = self._port_by_model.get(model_name)
        running = self.is_server_running(model_name)
        proc = self._processes.get(port) if port else None

        return {
            "model": model_name,
            "port": port,
            "running": running,
            "pid": proc.pid if proc and running else None,
            "service": "llama_cpp",
        }

    def get_all_running_models(self) -> List[str]:
        running = []
        for model_name in list(self._configs.keys()):
            if self.is_server_running(model_name):
                running.append(model_name)
        return running

    def _cleanup_process(self, port: int):
        self._processes.pop(port, None)

    def cleanup_all(self):
        for port, proc in list(self._processes.items()):
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
            self._cleanup_process(port)


async def test_llama_cpp_model(model_name: str, port: int, max_retries: int = 5, retry_delay: int = 5) -> Dict[str, Any]:
    url = f"http://localhost:{port}/v1/chat/completions"

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hello, please respond briefly."}],
        "max_tokens": 10,
        "temperature": 0.7,
    }

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=payload, timeout=30)

                if response.status_code == 200:
                    result = response.json()
                    if result.get("choices") and len(result["choices"]) > 0:
                        content = result["choices"][0].get("message", {}).get("content", "")
                        if content.strip():
                            return {
                                "success": True,
                                "message": "Model test passed",
                                "attempt": attempt + 1,
                                "response_content": content.strip(),
                            }
                        else:
                            return {
                                "success": False,
                                "message": "Model returned empty response",
                                "attempt": attempt + 1,
                            }
                    else:
                        return {
                            "success": False,
                            "message": "Invalid response structure",
                            "attempt": attempt + 1,
                        }
                else:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return {
                        "success": False,
                        "message": f"HTTP error {response.status_code}",
                        "attempt": attempt + 1,
                    }
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            return {
                "success": False,
                "message": "Connection failed",
                "attempt": attempt + 1,
                "error": str(e),
            }

    return {
        "success": False,
        "message": "All retry attempts failed",
        "attempt": max_retries,
    }


def scan_gguf_models(base_path: str = LLAMA_CPP_MODELS_BASE_PATH) -> List[Dict[str, Any]]:
    cached = cache_service.get("ai_controller:cache:gguf_model_list")
    if cached is not None:
        return cached

    models = []
    if not os.path.exists(base_path):
        return models

    for model_name in sorted(os.listdir(base_path)):
        model_path = os.path.join(base_path, model_name)
        if not os.path.isdir(model_path):
            continue

        gguf_files = [
            f for f in os.listdir(model_path)
            if f.endswith(".gguf")
        ]

        if not gguf_files:
            continue

        primary_gguf = gguf_files[0]
        full_path = os.path.join(model_path, primary_gguf)

        model_info = {
            "name": model_name,
            "path": model_path,
            "gguf_file": primary_gguf,
            "gguf_path": full_path,
            "size_mb": _get_file_size_mb(full_path),
            "service": "llama_cpp",
        }

        models.append(model_info)

    cache_service.set("ai_controller:cache:gguf_model_list", models, ttl_seconds=60)
    return models


def _get_file_size_mb(filepath: str) -> int:
    try:
        return int(os.path.getsize(filepath) / (1024 * 1024))
    except Exception:
        return 0


llama_cpp_manager = LlamaCppProcessManager()
