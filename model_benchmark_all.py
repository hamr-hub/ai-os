#!/usr/bin/env python3
"""
模型逐个切换测评脚本
功能:
1. 从后端获取所有模型列表
2. 逐个切换模型并等待就绪
3. 对每个模型运行完整测评（基础对话/流式对话/工具调用/图片理解）
4. 收集性能指标（TPS/延迟/Token数）
5. 生成完整的测评报告（JSON + 可读文本）

用法:
    python3 model_benchmark_all.py [--skip-running] [--model MODEL_NAME] [--output DIR]
"""

import asyncio
import json
import time
import logging
import argparse
import os
import sys
import socket
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict

import httpx

MANAGE_BASE_URL = "http://localhost:35000"
GATEWAY_URL = "http://localhost:3000"
GATEWAY_V1_URL = f"{GATEWAY_URL}/v1"
MODEL_BASE_PATH = "/mnt/pve_models"

SWITCH_TIMEOUT = 660
CHAT_TIMEOUT = 120
POLL_INTERVAL = 5
HEALTH_CHECK_TIMEOUT = 5
VLLM_MAX_WAIT = 300
WARMUP_DELAY = 8

TEST_PROMPTS = {
    "greeting": "Hello! Please respond with a brief greeting message in English.",
    "reasoning": "If a train travels at 60 km/h for 2.5 hours, how far does it go? Show your calculation.",
    "creative": "Write a haiku about artificial intelligence.",
    "factual": "What is the capital of France? Answer in one sentence.",
}

TOOL_TEST_PROMPT = "What is the current weather in Beijing? Use the weather tool if available."

TOOL_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "The city name"}
                },
                "required": ["location"]
            }
        }
    }
]

TEST_IMAGE_BASE64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("model_benchmark")


@dataclass
class ChatTestResult:
    test_name: str
    success: bool
    duration: float = 0.0
    tps: float = 0.0
    token_count: int = 0
    prompt_tokens: int = 0
    response_length: int = 0
    chunks_received: int = 0
    error: str = ""


@dataclass
class ToolTestResult:
    success: bool
    duration: float = 0.0
    tool_calls_count: int = 0
    tool_name: str = ""
    response_has_tool_call: bool = False
    error: str = ""


@dataclass
class ImageTestResult:
    success: bool
    duration: float = 0.0
    tps: float = 0.0
    token_count: int = 0
    error: str = ""


@dataclass
class ModelBenchmarkResult:
    model_name: str
    engine_type: str = ""
    required_memory: str = ""
    supports_images: bool = False
    supports_tool_calling: bool = False
    supports_image_generation: bool = False
    switch_success: bool = False
    switch_time_seconds: float = 0.0
    ready_time_seconds: float = 0.0
    vllm_port: int = 0
    chat_basic_results: List[ChatTestResult] = field(default_factory=list)
    chat_streaming_results: List[ChatTestResult] = field(default_factory=list)
    tool_test_result: Optional[ToolTestResult] = None
    image_test_result: Optional[ImageTestResult] = None
    overall_status: str = "pending"
    avg_tps: float = 0.0
    avg_latency: float = 0.0
    avg_streaming_tps: float = 0.0
    pass_rate: float = 0.0
    error_message: str = ""
    test_timestamp: str = ""


class ModelBenchmarkRunner:
    def __init__(self, output_dir: str = "."):
        self.client = httpx.AsyncClient(timeout=SWITCH_TIMEOUT)
        self.chat_client = httpx.AsyncClient(timeout=CHAT_TIMEOUT)
        self.results: List[ModelBenchmarkResult] = []
        self.current_model: Optional[str] = None
        self.backup_model: Optional[str] = None
        self.output_dir = output_dir
        self._vllm_port_cache: Optional[int] = None

        os.makedirs(output_dir, exist_ok=True)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_handler = logging.FileHandler(
            os.path.join(output_dir, f"benchmark_{ts}.log"),
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logger.addHandler(file_handler)

    async def close(self):
        await self.client.aclose()
        await self.chat_client.aclose()

    def _check_port(self, port: int, timeout: int = 2) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def discover_vllm_port(self) -> int:
        if self._vllm_port_cache is not None and self._check_port(self._vllm_port_cache):
            return self._vllm_port_cache

        for port in range(8000, 8010):
            if self._check_port(port):
                try:
                    with httpx.Client(timeout=2) as c:
                        r = c.get(f"http://localhost:{port}/health")
                        if r.status_code == 200:
                            self._vllm_port_cache = port
                            return port
                except Exception:
                    pass

        for port in [8100, 8001, 8002]:
            if self._check_port(port):
                self._vllm_port_cache = port
                return port

        self._vllm_port_cache = 8000
        return 8000

    async def get_models_list(self) -> List[Dict]:
        logger.info("正在获取模型列表...")
        try:
            response = await self.client.get(f"{MANAGE_BASE_URL}/manage/models")
            response.raise_for_status()
            models_data = response.json()

            config_data = {}
            try:
                import yaml
                with open("/root/ai-os/config.yaml", 'r') as f:
                    config_data = yaml.safe_load(f) or {}
            except Exception:
                pass

            config_models = config_data.get("models", {})

            models = []
            for name, info in models_data.items():
                cfg = config_models.get(name, {})
                model_path = cfg.get("model_path", f"{MODEL_BASE_PATH}/{name}")
                disk_size_mb = self._get_model_disk_size(model_path)

                if disk_size_mb < 100 and disk_size_mb >= 0:
                    logger.info(f"  跳过 {name}: 磁盘大小仅 {disk_size_mb}MB (模型不完整)")
                    continue

                models.append({
                    "name": name,
                    "running": info.get("running", False),
                    "port": info.get("port"),
                    "backend_type": cfg.get("engine_type", info.get("backend_type", "vllm")),
                    "service": info.get("service", "vllm-aiclient"),
                    "required_memory": cfg.get("required_memory", info.get("required_memory", "")),
                    "supports_images": cfg.get("supports_images", info.get("supports_images", False)),
                    "supports_tool_calling": cfg.get("supports_tool_calling", info.get("supports_tool_calling", False)),
                    "supports_image_generation": cfg.get("supports_image_generation", info.get("supports_image_generation", False)),
                    "model_path": model_path,
                    "disk_size_mb": disk_size_mb,
                })

            models.sort(key=lambda x: x["disk_size_mb"] if x["disk_size_mb"] > 0 else 999999)

            logger.info(f"获取到 {len(models)} 个可用模型（已过滤不完整模型）")
            for i, m in enumerate(models):
                running_tag = " [运行中]" if m["running"] else ""
                size_str = f"{m['disk_size_mb']}MB" if m['disk_size_mb'] > 0 else "未知"
                logger.info(f"  {i+1}. {m['name']} ({m['backend_type']}, {size_str}){running_tag}")
            return models

        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return []

    def _get_model_disk_size(self, model_path: str) -> int:
        try:
            result = subprocess.run(
                ["du", "-sm", model_path],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return int(result.stdout.split()[0])
        except Exception:
            pass
        return -1

    async def switch_model_atomic(self, model_name: str, action: str = "switch") -> Tuple[bool, str, float]:
        logger.info(f"正在切换到模型: {model_name} (action={action})")
        start_time = time.time()

        try:
            cancel_resp = await self.client.delete(
                f"{MANAGE_BASE_URL}/manage/switch/cancel",
                timeout=10
            )
            if cancel_resp.status_code == 200:
                logger.info(f"  已取消之前的切换任务")
                await asyncio.sleep(5)
        except Exception:
            pass

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.post(
                    f"{MANAGE_BASE_URL}/manage/switch/atomic",
                    json={
                        "model_name": model_name,
                        "action": action,
                        "set_as_default": False,
                    },
                    timeout=30
                )

                if response.status_code == 409:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("error", str(error_data))
                    except Exception:
                        error_msg = response.text[:500]
                    logger.warning(f"  切换冲突(409): {error_msg}, 等待后重试 ({attempt+1}/{max_retries})...")
                    await asyncio.sleep(30)
                    try:
                        await self.client.delete(f"{MANAGE_BASE_URL}/manage/switch/cancel", timeout=10)
                    except Exception:
                        pass
                    await asyncio.sleep(10)
                    continue

                if response.status_code not in (200, 201):
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("detail", str(error_data))
                    except Exception:
                        error_msg = response.text[:500]
                    elapsed = time.time() - start_time
                    logger.error(f"切换请求失败: {error_msg}")
                    return False, error_msg, elapsed

                data = response.json()
                session_id = data.get("session_id", "")
                status = data.get("status", "")

                logger.info(f"  切换请求已接受: session_id={session_id}, status={status}")

                if session_id:
                    ready, ready_time = await self._poll_switch_status(session_id, model_name)
                    total_time = time.time() - start_time
                    if ready:
                        logger.info(f"模型 {model_name} 切换成功，总耗时: {total_time:.1f}秒")
                        return True, "", total_time
                    else:
                        return False, f"切换超时或失败 (session={session_id})", total_time
                else:
                    elapsed = time.time() - start_time
                    ready, _ = await self._wait_for_model_running(model_name, max_wait=60)
                    total_time = time.time() - start_time
                    if ready:
                        return True, "", total_time
                    return False, "模型未就绪", total_time

            except httpx.TimeoutException:
                elapsed = time.time() - start_time
                return False, f"切换请求超时 ({elapsed:.1f}s)", elapsed
            except Exception as e:
                elapsed = time.time() - start_time
                return False, str(e), elapsed

        elapsed = time.time() - start_time
        return False, f"切换冲突，重试{max_retries}次后仍失败", elapsed

    async def _poll_switch_status(self, session_id: str, model_name: str) -> Tuple[bool, float]:
        start_time = time.time()
        while (time.time() - start_time) < SWITCH_TIMEOUT:
            try:
                resp = await self.client.get(
                    f"{MANAGE_BASE_URL}/manage/switch/status",
                    timeout=10
                )
                if resp.status_code == 200:
                    status_data = resp.json()
                    is_switching = status_data.get("is_switching", False)
                    session = status_data.get("session") or {}
                    session_sid = session.get("session_id", "")
                    progress = session.get("overall_progress", 0)
                    completed = session.get("completed_successfully", False)
                    error = session.get("error")

                    if completed and not is_switching:
                        logger.info(f"  切换完成! progress={progress}%")
                        return True, time.time() - start_time

                    if error and not is_switching:
                        logger.error(f"切换失败: {error}")
                        return False, time.time() - start_time

                    if not is_switching and not completed:
                        if session_sid and session_sid != session_id:
                            logger.warning(f"  session变更: {session_sid} != {session_id}")
                        else:
                            logger.info(f"  切换已结束(非completed状态), 等待模型就绪...")
                            ready, _ = await self._wait_for_model_running(model_name, max_wait=120)
                            return ready, time.time() - start_time

                    if is_switching:
                        phase_name = ""
                        phases = session.get("phases", [])
                        for p in phases:
                            if p.get("status") == "running":
                                phase_name = p.get("name", "")
                                break
                        logger.info(f"  切换中... progress={progress}% phase={phase_name}")
            except Exception as e:
                logger.debug(f"轮询状态异常: {e}")

            await asyncio.sleep(POLL_INTERVAL)

        return False, time.time() - start_time

    async def _wait_for_model_running(self, model_name: str, max_wait: int = VLLM_MAX_WAIT) -> Tuple[bool, float]:
        start_time = time.time()
        while (time.time() - start_time) < max_wait:
            try:
                resp = await self.client.get(f"{MANAGE_BASE_URL}/manage/models", timeout=10)
                if resp.status_code == 200:
                    models = resp.json()
                    if model_name in models and models[model_name].get("running"):
                        port = models[model_name].get("port", 8000)
                        try:
                            health_resp = await self.client.get(
                                f"http://localhost:{port}/health",
                                timeout=HEALTH_CHECK_TIMEOUT
                            )
                            if health_resp.status_code == 200:
                                return True, time.time() - start_time
                        except Exception:
                            pass
            except Exception:
                pass
            await asyncio.sleep(POLL_INTERVAL)
        return False, time.time() - start_time

    async def test_chat_basic(self, model_name: str, port: int, model_path: str = "") -> List[ChatTestResult]:
        results = []
        url = f"http://localhost:{port}/v1/chat/completions"
        model_ids = [model_path, model_name] if model_path else [model_name]

        for prompt_name, prompt_text in TEST_PROMPTS.items():
            result = ChatTestResult(test_name=f"chat_basic_{prompt_name}", success=False)
            start_time = time.time()

            for model_id in model_ids:
                try:
                    response = await self.chat_client.post(
                        url,
                        json={
                            "model": model_id,
                            "messages": [{"role": "user", "content": prompt_text}],
                            "max_tokens": 100,
                            "temperature": 0.7
                        }
                    )
                    if response.status_code != 200:
                        continue
                    response.raise_for_status()
                    data = response.json()

                    duration = time.time() - start_time
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    usage = data.get("usage", {})
                    token_count = usage.get("completion_tokens", 0)
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    tps = token_count / duration if duration > 0 else 0

                    result.success = bool(content.strip())
                    result.duration = duration
                    result.tps = tps
                    result.token_count = token_count
                    result.prompt_tokens = prompt_tokens
                    result.response_length = len(content)

                    if not content.strip():
                        result.error = "Empty response"
                    break

                except Exception as e:
                    result.duration = time.time() - start_time
                    result.error = str(e)

            results.append(result)
            status = "OK" if result.success else "FAIL"
            logger.info(f"    chat_basic_{prompt_name}: {status} | TPS={result.tps:.1f} | tokens={result.token_count} | {result.duration:.2f}s")

        return results

    async def test_chat_streaming(self, model_name: str, port: int, model_path: str = "") -> List[ChatTestResult]:
        results = []
        url = f"http://localhost:{port}/v1/chat/completions"
        model_ids = [model_path, model_name] if model_path else [model_name]

        for prompt_name, prompt_text in TEST_PROMPTS.items():
            result = ChatTestResult(test_name=f"chat_streaming_{prompt_name}", success=False)
            start_time = time.time()

            for model_id in model_ids:
                try:
                    response = await self.chat_client.post(
                        url,
                        json={
                            "model": model_id,
                            "messages": [{"role": "user", "content": prompt_text}],
                            "max_tokens": 100,
                            "temperature": 0.7,
                            "stream": True
                        },
                        timeout=CHAT_TIMEOUT
                    )
                    if response.status_code != 200:
                        continue
                    response.raise_for_status()

                    content = ""
                    token_count = 0
                    chunks_received = 0

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            chunk_data = line[6:]
                            if chunk_data == "[DONE]":
                                break
                            try:
                                json_chunk = json.loads(chunk_data)
                                delta = json_chunk.get("choices", [{}])[0].get("delta", {})
                                if "content" in delta:
                                    content += delta["content"]
                                    token_count += 1
                                chunks_received += 1
                            except Exception:
                                pass

                    duration = time.time() - start_time
                    tps = token_count / duration if duration > 0 else 0

                    result.success = chunks_received > 0 and bool(content.strip())
                    result.duration = duration
                    result.tps = tps
                    result.token_count = token_count
                    result.chunks_received = chunks_received
                    result.response_length = len(content)

                    if chunks_received == 0:
                        result.error = "No streaming chunks received"
                    elif not content.strip():
                        result.error = "Empty streaming content"
                    break

                except Exception as e:
                    result.duration = time.time() - start_time
                    result.error = str(e)

            results.append(result)
            status = "OK" if result.success else "FAIL"
            logger.info(f"    chat_streaming_{prompt_name}: {status} | TPS={result.tps:.1f} | chunks={result.chunks_received} | {result.duration:.2f}s")

        return results

    async def test_tool_calling(self, model_name: str, port: int, model_path: str = "") -> ToolTestResult:
        result = ToolTestResult(success=False)
        url = f"http://localhost:{port}/v1/chat/completions"
        model_ids = [model_path, model_name] if model_path else [model_name]
        start_time = time.time()

        for model_id in model_ids:
            try:
                response = await self.chat_client.post(
                    url,
                    json={
                        "model": model_id,
                        "messages": [{"role": "user", "content": TOOL_TEST_PROMPT}],
                        "tools": TOOL_DEFINITION,
                        "tool_choice": "auto",
                        "max_tokens": 200
                    }
                )
                if response.status_code != 200:
                    continue
                response.raise_for_status()
                data = response.json()

                duration = time.time() - start_time
                message = data.get("choices", [{}])[0].get("message", {})
                tool_calls = message.get("tool_calls", [])

                result.duration = duration
                result.tool_calls_count = len(tool_calls)
                result.response_has_tool_call = len(tool_calls) > 0

                if tool_calls:
                    result.tool_name = tool_calls[0].get("function", {}).get("name", "")
                    result.success = True
                else:
                    content = message.get("content", "")
                    result.success = bool(content.strip())

                status = "OK" if result.success else "FAIL"
                tool_info = f"tool_calls={result.tool_calls_count}" if result.response_has_tool_call else "no_tool_call"
                logger.info(f"    tool_calling: {status} | {tool_info} | {result.duration:.2f}s")
                break

            except Exception as e:
                result.duration = time.time() - start_time
                result.error = str(e)

        if not result.success and not result.error:
            logger.info(f"    tool_calling: FAIL")
        elif result.error:
            logger.info(f"    tool_calling: FAIL | {result.error}")

        return result

    async def test_image_processing(self, model_name: str, port: int, model_path: str = "") -> ImageTestResult:
        result = ImageTestResult(success=False)
        url = f"http://localhost:{port}/v1/chat/completions"
        model_ids = [model_path, model_name] if model_path else [model_name]
        start_time = time.time()

        for model_id in model_ids:
            try:
                response = await self.chat_client.post(
                    url,
                    json={
                        "model": model_id,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Describe the content of this image in detail."},
                                {"type": "image_url", "image_url": {"url": TEST_IMAGE_BASE64}}
                            ]
                        }],
                        "max_tokens": 100,
                        "temperature": 0.7
                    }
                )
                if response.status_code != 200:
                    continue
                response.raise_for_status()
                data = response.json()

                duration = time.time() - start_time
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                token_count = data.get("usage", {}).get("completion_tokens", 0)
                tps = token_count / duration if duration > 0 else 0

                result.success = bool(content.strip())
                result.duration = duration
                result.tps = tps
                result.token_count = token_count

                status = "OK" if result.success else "FAIL"
                logger.info(f"    image_processing: {status} | TPS={result.tps:.1f} | tokens={result.token_count} | {result.duration:.2f}s")
                break

            except Exception as e:
                result.duration = time.time() - start_time
                result.error = str(e)
                logger.info(f"    image_processing: FAIL | {e}")

        return result

    async def test_chat_via_gateway(self, model_name: str) -> Tuple[bool, str]:
        try:
            response = await self.chat_client.post(
                f"{GATEWAY_V1_URL}/chat/completions",
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 20,
                    "temperature": 0.7,
                },
                timeout=CHAT_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content.strip():
                    return True, content.strip()[:200]
            return False, f"HTTP {response.status_code}"
        except Exception as e:
            return False, str(e)

    async def benchmark_model(self, model_info: Dict) -> ModelBenchmarkResult:
        model_name = model_info["name"]
        result = ModelBenchmarkResult(
            model_name=model_name,
            engine_type=model_info.get("backend_type", "vllm"),
            required_memory=model_info.get("required_memory", ""),
            supports_images=model_info.get("supports_images", False),
            supports_tool_calling=model_info.get("supports_tool_calling", False),
            supports_image_generation=model_info.get("supports_image_generation", False),
            test_timestamp=datetime.now().isoformat(),
        )

        logger.info(f"\n{'='*70}")
        logger.info(f"开始测评模型: {model_name}")
        logger.info(f"  引擎: {result.engine_type} | 显存需求: {result.required_memory} | 多模态: {result.supports_images}")
        logger.info(f"{'='*70}")

        switch_ok, switch_error, switch_time = await self.switch_model_atomic(model_name)
        result.switch_success = switch_ok
        result.switch_time_seconds = switch_time

        if not switch_ok:
            result.overall_status = "switch_failed"
            result.error_message = f"切换失败: {switch_error}"
            logger.error(f"模型 {model_name} 切换失败: {switch_error}")
            if self.backup_model:
                logger.info(f"回滚到备份模型: {self.backup_model}")
                await self.switch_model_atomic(self.backup_model)
            return result

        ready, ready_time = await self._wait_for_model_running(model_name)
        result.ready_time_seconds = ready_time

        if not ready:
            result.overall_status = "ready_timeout"
            result.error_message = f"等待就绪超时 ({ready_time:.1f}s)"
            logger.error(f"模型 {model_name} 等待就绪超时")
            if self.backup_model:
                await self.switch_model_atomic(self.backup_model)
            return result

        configured_port = model_info.get("port", 8000)
        port = configured_port
        try:
            health_resp = await self.client.get(f"http://localhost:{port}/health", timeout=5)
            if health_resp.status_code != 200:
                port = self.discover_vllm_port()
        except Exception:
            port = self.discover_vllm_port()

        result.vllm_port = port
        logger.info(f"模型 {model_name} 已就绪 (端口={port}, 切换耗时={switch_time:.1f}s, 就绪耗时={ready_time:.1f}s)")

        logger.info(f"等待 {WARMUP_DELAY} 秒预热...")
        await asyncio.sleep(WARMUP_DELAY)

        gateway_ok, gateway_resp = await self.test_chat_via_gateway(model_name)
        logger.info(f"网关测试: {'OK' if gateway_ok else 'FAIL'} | {gateway_resp[:100]}")

        logger.info(f"运行基础对话测试...")
        result.chat_basic_results = await self.test_chat_basic(model_name, port, model_info.get("model_path", ""))

        logger.info("运行流式对话测试...")
        result.chat_streaming_results = await self.test_chat_streaming(model_name, port, model_info.get("model_path", ""))

        if result.supports_tool_calling:
            logger.info("运行工具调用测试...")
            result.tool_test_result = await self.test_tool_calling(model_name, port, model_info.get("model_path", ""))
        else:
            logger.info("跳过工具调用测试（模型不支持）")
            result.tool_test_result = ToolTestResult(success=False, error="Not supported")

        if result.supports_images:
            logger.info("运行图片理解测试...")
            result.image_test_result = await self.test_image_processing(model_name, port, model_info.get("model_path", ""))
        else:
            logger.info("跳过图片理解测试（模型不支持）")
            result.image_test_result = ImageTestResult(success=False, error="Not supported")

        self._calculate_summary(result)

        self.backup_model = model_name
        self.current_model = model_name

        logger.info(f"\n模型 {model_name} 测评完成: {result.overall_status}")
        logger.info(f"  平均TPS={result.avg_tps:.1f} | 平均延迟={result.avg_latency:.2f}s | 通过率={result.pass_rate:.0f}%")

        return result

    def _calculate_summary(self, result: ModelBenchmarkResult):
        all_basic_tps = [r.tps for r in result.chat_basic_results if r.success]
        all_basic_latency = [r.duration for r in result.chat_basic_results if r.success]
        all_streaming_tps = [r.tps for r in result.chat_streaming_results if r.success]

        result.avg_tps = sum(all_basic_tps) / len(all_basic_tps) if all_basic_tps else 0
        result.avg_latency = sum(all_basic_latency) / len(all_basic_latency) if all_basic_latency else 0
        result.avg_streaming_tps = sum(all_streaming_tps) / len(all_streaming_tps) if all_streaming_tps else 0

        total_tests = 0
        passed_tests = 0

        total_tests += len(result.chat_basic_results)
        passed_tests += sum(1 for r in result.chat_basic_results if r.success)

        total_tests += len(result.chat_streaming_results)
        passed_tests += sum(1 for r in result.chat_streaming_results if r.success)

        if result.tool_test_result:
            total_tests += 1
            if result.tool_test_result.success:
                passed_tests += 1

        if result.image_test_result:
            total_tests += 1
            if result.image_test_result.success:
                passed_tests += 1

        result.pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        if result.pass_rate == 100:
            result.overall_status = "passed"
        elif result.pass_rate >= 50:
            result.overall_status = "degraded"
        elif result.pass_rate > 0:
            result.overall_status = "partial"
        else:
            result.overall_status = "failed"

    async def run_all_benchmarks(self, skip_running: bool = False, target_model: Optional[str] = None):
        logger.info("=" * 70)
        logger.info("模型逐个切换测评 - 开始")
        logger.info(f"时间: {datetime.now().isoformat()}")
        logger.info("=" * 70)

        models = await self.get_models_list()
        if not models:
            logger.error("未找到可用模型，测评终止")
            return

        if target_model:
            models = [m for m in models if m["name"] == target_model]
            if not models:
                logger.error(f"未找到目标模型: {target_model}")
                return

        self.current_model = self._get_current_running_model(models)
        if self.current_model:
            self.backup_model = self.current_model
            logger.info(f"当前运行模型: {self.current_model}")

        for idx, model_info in enumerate(models, 1):
            logger.info(f"\n{'#'*70}")
            logger.info(f"# [{idx}/{len(models)}] 测评模型: {model_info['name']}")
            logger.info(f"{'#'*70}")

            if skip_running and model_info.get("running"):
                logger.info(f"跳过已运行模型: {model_info['name']}")
                continue

            bench_result = await self.benchmark_model(model_info)
            self.results.append(bench_result)

            self._save_intermediate_results()

        self._generate_report()

    def _get_current_running_model(self, models: List[Dict]) -> Optional[str]:
        for m in models:
            if m.get("running"):
                return m["name"]
        return None

    def _save_intermediate_results(self):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = os.path.join(self.output_dir, f"benchmark_intermediate_{ts}.json")
        try:
            data = [self._result_to_dict(r) for r in self.results]
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"保存中间结果失败: {e}")

    def _result_to_dict(self, r: ModelBenchmarkResult) -> Dict:
        d = {
            "model_name": r.model_name,
            "engine_type": r.engine_type,
            "required_memory": r.required_memory,
            "supports_images": r.supports_images,
            "supports_tool_calling": r.supports_tool_calling,
            "supports_image_generation": r.supports_image_generation,
            "switch_success": r.switch_success,
            "switch_time_seconds": round(r.switch_time_seconds, 2),
            "ready_time_seconds": round(r.ready_time_seconds, 2),
            "vllm_port": r.vllm_port,
            "overall_status": r.overall_status,
            "avg_tps": round(r.avg_tps, 2),
            "avg_latency": round(r.avg_latency, 2),
            "avg_streaming_tps": round(r.avg_streaming_tps, 2),
            "pass_rate": round(r.pass_rate, 1),
            "error_message": r.error_message,
            "test_timestamp": r.test_timestamp,
        }

        d["chat_basic_results"] = [
            {
                "test_name": cr.test_name,
                "success": cr.success,
                "duration": round(cr.duration, 3),
                "tps": round(cr.tps, 2),
                "token_count": cr.token_count,
                "prompt_tokens": cr.prompt_tokens,
                "response_length": cr.response_length,
                "error": cr.error,
            }
            for cr in r.chat_basic_results
        ]

        d["chat_streaming_results"] = [
            {
                "test_name": cr.test_name,
                "success": cr.success,
                "duration": round(cr.duration, 3),
                "tps": round(cr.tps, 2),
                "token_count": cr.token_count,
                "chunks_received": cr.chunks_received,
                "response_length": cr.response_length,
                "error": cr.error,
            }
            for cr in r.chat_streaming_results
        ]

        if r.tool_test_result:
            d["tool_test_result"] = {
                "success": r.tool_test_result.success,
                "duration": round(r.tool_test_result.duration, 3),
                "tool_calls_count": r.tool_test_result.tool_calls_count,
                "tool_name": r.tool_test_result.tool_name,
                "response_has_tool_call": r.tool_test_result.response_has_tool_call,
                "error": r.tool_test_result.error,
            }

        if r.image_test_result:
            d["image_test_result"] = {
                "success": r.image_test_result.success,
                "duration": round(r.image_test_result.duration, 3),
                "tps": round(r.image_test_result.tps, 2),
                "token_count": r.image_test_result.token_count,
                "error": r.image_test_result.error,
            }

        return d

    def _generate_report(self):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        json_path = os.path.join(self.output_dir, f"benchmark_report_{ts}.json")
        data = [self._result_to_dict(r) for r in self.results]
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"JSON 报告已保存: {json_path}")

        txt_path = os.path.join(self.output_dir, f"benchmark_report_{ts}.txt")
        report_text = self._format_text_report()
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        logger.info(f"文本报告已保存: {txt_path}")

        print("\n" + report_text)

    def _format_text_report(self) -> str:
        lines = []
        lines.append("=" * 80)
        lines.append("AI OS 模型测评报告")
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"测试模型数: {len(self.results)}")
        lines.append("=" * 80)

        passed = sum(1 for r in self.results if r.overall_status == "passed")
        degraded = sum(1 for r in self.results if r.overall_status == "degraded")
        partial = sum(1 for r in self.results if r.overall_status == "partial")
        failed = sum(1 for r in self.results if r.overall_status in ("failed", "switch_failed", "ready_timeout"))

        lines.append(f"\n总览: 通过={passed} | 降级={degraded} | 部分={partial} | 失败={failed}")

        sorted_by_tps = sorted(self.results, key=lambda r: r.avg_tps, reverse=True)
        if sorted_by_tps and sorted_by_tps[0].avg_tps > 0:
            lines.append(f"最高TPS模型: {sorted_by_tps[0].model_name} ({sorted_by_tps[0].avg_tps:.1f} tok/s)")

        sorted_by_latency = sorted(self.results, key=lambda r: r.avg_latency)
        if sorted_by_latency and sorted_by_latency[0].avg_latency > 0:
            lines.append(f"最低延迟模型: {sorted_by_latency[0].model_name} ({sorted_by_latency[0].avg_latency:.2f}s)")

        lines.append("")
        lines.append("-" * 80)
        lines.append("对比排名 (按平均TPS降序)")
        lines.append("-" * 80)
        lines.append(f"{'排名':<4} {'模型名':<42} {'引擎':<10} {'TPS':>8} {'延迟':>8} {'流式TPS':>8} {'通过率':>7} {'状态'}")
        lines.append("-" * 80)
        for i, r in enumerate(sorted_by_tps, 1):
            status_icon = {"passed": "✅", "degraded": "⚠️", "partial": "🔶", "failed": "❌",
                          "switch_failed": "❌", "ready_timeout": "⏰"}.get(r.overall_status, "?")
            lines.append(
                f"{i:<4} {r.model_name:<42} {r.engine_type:<10} "
                f"{r.avg_tps:>7.1f}  {r.avg_latency:>6.2f}s {r.avg_streaming_tps:>7.1f}  "
                f"{r.pass_rate:>5.0f}%  {status_icon} {r.overall_status}"
            )

        for r in self.results:
            lines.append("")
            lines.append("=" * 80)
            lines.append(f"模型: {r.model_name}")
            lines.append(f"引擎: {r.engine_type} | 显存需求: {r.required_memory} | 端口: {r.vllm_port}")
            lines.append(f"能力: 对话=✅ | 工具={'✅' if r.supports_tool_calling else '❌'} | "
                        f"图片={'✅' if r.supports_images else '❌'} | 图片生成={'✅' if r.supports_image_generation else '❌'}")
            lines.append(f"切换: {'成功' if r.switch_success else '失败'} ({r.switch_time_seconds:.1f}s) | "
                        f"就绪: {r.ready_time_seconds:.1f}s")
            lines.append(f"状态: {r.overall_status} | 通过率: {r.pass_rate:.0f}%")
            if r.error_message:
                lines.append(f"错误: {r.error_message}")
            lines.append("-" * 80)

            if r.chat_basic_results:
                lines.append("  基础对话测试:")
                for cr in r.chat_basic_results:
                    status = "✅" if cr.success else "❌"
                    lines.append(
                        f"    {status} {cr.test_name:<30} TPS={cr.tps:>6.1f} "
                        f"tokens={cr.token_count:>4} prompt={cr.prompt_tokens:>4} "
                        f"耗时={cr.duration:.2f}s"
                    )
                    if cr.error:
                        lines.append(f"       错误: {cr.error}")

            if r.chat_streaming_results:
                lines.append("  流式对话测试:")
                for cr in r.chat_streaming_results:
                    status = "✅" if cr.success else "❌"
                    lines.append(
                        f"    {status} {cr.test_name:<30} TPS={cr.tps:>6.1f} "
                        f"tokens={cr.token_count:>4} chunks={cr.chunks_received:>4} "
                        f"耗时={cr.duration:.2f}s"
                    )
                    if cr.error:
                        lines.append(f"       错误: {cr.error}")

            if r.tool_test_result:
                status = "✅" if r.tool_test_result.success else "❌"
                tool_info = f"tool_calls={r.tool_test_result.tool_calls_count}" if r.tool_test_result.response_has_tool_call else "no_tool_call"
                lines.append(f"  {status} 工具调用测试: {tool_info} | 耗时={r.tool_test_result.duration:.2f}s")
                if r.tool_test_result.error:
                    lines.append(f"     错误: {r.tool_test_result.error}")

            if r.image_test_result:
                status = "✅" if r.image_test_result.success else "❌"
                lines.append(
                    f"  {status} 图片理解测试: TPS={r.image_test_result.tps:.1f} "
                    f"tokens={r.image_test_result.token_count} | 耗时={r.image_test_result.duration:.2f}s"
                )
                if r.image_test_result.error:
                    lines.append(f"     错误: {r.image_test_result.error}")

        lines.append("")
        lines.append("=" * 80)
        lines.append("测评完成")
        lines.append("=" * 80)

        return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="AI OS 模型逐个切换测评")
    parser.add_argument("--skip-running", action="store_true", help="跳过当前已运行的模型")
    parser.add_argument("--model", type=str, default=None, help="只测评指定模型")
    parser.add_argument("--output", type=str, default="./benchmark_results", help="输出目录")
    args = parser.parse_args()

    runner = ModelBenchmarkRunner(output_dir=args.output)
    try:
        await runner.run_all_benchmarks(
            skip_running=args.skip_running,
            target_model=args.model,
        )
    except KeyboardInterrupt:
        logger.info("测评被用户中断")
        if runner.results:
            runner._generate_report()
    except Exception as e:
        logger.error(f"测评异常: {e}")
        logger.exception(e)
        if runner.results:
            runner._generate_report()
    finally:
        await runner.close()


if __name__ == "__main__":
    asyncio.run(main())
