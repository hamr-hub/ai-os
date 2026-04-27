#!/usr/bin/env python3
"""
模型切换测试脚本 (V2 - 修复版)
功能:
1. 从后端获取模型列表并按大小排序（从小到大）
2. 逐个切换模型并验证 3000 端口对话是否正常
3. 切换失败则回滚到上一个可用模型
4. 探测哪些模型可以成功切换
5. 分析前后端服务日志，诊断切换失败原因

修复:
- 动态发现 vLLM 端口（不再硬编码 8000）
- 使用模型完整路径进行 vLLM 对话测试
- 增加健康检查重试次数和超时时间
- 改进模型就绪检测逻辑

用法:
    python3 model_switch_test.py
"""

import asyncio
import json
import time
import logging
import subprocess
import re
import socket
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

import httpx

# ============================================
# 配置
# ============================================
MANAGE_BASE_URL = "http://localhost:35000"
GATEWAY_URL = "http://localhost:3000"
GATEWAY_V1_URL = f"{GATEWAY_URL}/v1"
MODEL_BASE_PATH = "/mnt/pve_models"

# 等待超时配置
SWITCH_TIMEOUT = 300    # 模型切换最大等待时间（秒）
CHAT_TIMEOUT = 60       # 对话请求超时时间（秒）
POLL_INTERVAL = 5       # 轮询间隔（秒）
HEALTH_CHECK_TIMEOUT = 5 # 单次健康检查超时（秒）
VLLM_MAX_WAIT = 240      # vLLM最大等待时间（秒）

# 测试对话内容
TEST_MESSAGES = [
    {"role": "user", "content": "hi"},
]

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("model_switch_test")

# 文件日志 handler
file_handler = logging.FileHandler(f"model_switch_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(file_handler)


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    size_mb: int = 0
    running: bool = False
    port: Optional[int] = None
    backend_type: str = "vllm"
    required_memory: Optional[str] = None
    description: str = ""
    model_path: str = ""
    supports_images: bool = False
    supports_tool_calling: bool = False
    supports_image_generation: bool = False


@dataclass
class TestResult:
    """单个模型的测试结果"""
    model_name: str
    success: bool
    switch_success: bool
    chat_gateway_success: bool
    chat_vllm_success: bool
    switch_time_seconds: float = 0.0
    ready_time_seconds: float = 0.0
    chat_response: str = ""
    vllm_port: Optional[int] = None
    error_message: str = ""
    logs_before: Dict[str, str] = field(default_factory=dict)
    logs_after: Dict[str, str] = field(default_factory=dict)


# ============================================
# 核心功能类
# ============================================
class ModelSwitchTester:
    """模型切换测试器"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=SWITCH_TIMEOUT)
        self.chat_client = httpx.AsyncClient(timeout=CHAT_TIMEOUT)
        self.results: List[TestResult] = []
        self.current_model: Optional[str] = None
        self.backup_model: Optional[str] = None
        self.successful_models: List[str] = []
        self.failed_models: List[str] = []
        self._vllm_port_cache: Optional[int] = None

    async def close(self):
        await self.client.aclose()
        await self.chat_client.aclose()

    # ============================================
    # vLLM 端口发现
    # ============================================
    def _check_port(self, port: int, timeout: int = 2) -> bool:
        """检查端口是否开放"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def discover_vllm_port(self) -> int:
        """发现 vLLM 服务实际监听的端口"""
        # 优先使用缓存
        if self._vllm_port_cache is not None and self._check_port(self._vllm_port_cache):
            return self._vllm_port_cache

        # 从 systemd 服务文件读取
        for svc_file in ["/etc/systemd/system/vllm-aiclient.service"]:
            try:
                if os.path.exists(svc_file):
                    with open(svc_file, 'r') as f:
                        content = f.read()
                    match = re.search(r'--port\s+(\d+)', content)
                    if match:
                        port = int(match.group(1))
                        if self._check_port(port):
                            self._vllm_port_cache = port
                            return port
            except Exception:
                pass

        # 从启动脚本读取
        for script in ["/root/ai-suite/start_vllm_aiclient.sh"]:
            try:
                if os.path.exists(script):
                    with open(script, 'r') as f:
                        content = f.read()
                    match = re.search(r'--port\s+(\d+)', content)
                    if match:
                        port = int(match.group(1))
                        if self._check_port(port):
                            self._vllm_port_cache = port
                            return port
            except Exception:
                pass

        # 扫描常见端口
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

        # 默认端口
        self._vllm_port_cache = 8000
        return 8000

    async def wait_for_vllm_health(self, port: int, max_wait: int = VLLM_MAX_WAIT, poll_interval: int = POLL_INTERVAL) -> bool:
        """等待 vLLM 健康检查通过"""
        start = time.time()
        elapsed = 0
        while elapsed < max_wait:
            try:
                resp = await self.client.get(f"http://localhost:{port}/health", timeout=HEALTH_CHECK_TIMEOUT)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(poll_interval)
            elapsed = time.time() - start
        return False

    # ============================================
    # 模型信息获取
    # ============================================
    async def get_models_list(self) -> List[ModelInfo]:
        """从后端获取模型列表（按大小排序，从小到大）"""
        logger.info("正在获取模型列表...")
        try:
            response = await self.client.get(f"{MANAGE_BASE_URL}/manage/models")
            response.raise_for_status()
            models_data = response.json()

            models = []
            for name, info in models_data.items():
                model_path = f"{MODEL_BASE_PATH}/{name}"
                size_mb = await self._get_model_size_mb(name)
                model = ModelInfo(
                    name=name,
                    size_mb=size_mb,
                    running=info.get("running", False),
                    port=info.get("port"),
                    backend_type=info.get("backend_type", "vllm"),
                    required_memory=info.get("required_memory"),
                    description=info.get("description", ""),
                    model_path=model_path,
                    supports_images=info.get("supports_images", False),
                    supports_tool_calling=info.get("supports_tool_calling", False),
                    supports_image_generation=info.get("supports_image_generation", False),
                )
                models.append(model)

            # 按大小排序（从小到大）
            sorted_models = sorted(models, key=lambda x: x.size_mb if x.size_mb > 0 else 999999)

            logger.info(f"获取到 {len(sorted_models)} 个模型，已按大小排序")
            for i, m in enumerate(sorted_models):
                size_str = f"{m.size_mb}MB" if m.size_mb > 0 else "未知"
                running_tag = " (运行中)" if m.running else ""
                logger.info(f"  {i+1}. {m.name} [{size_str}]{running_tag}")

            return sorted_models

        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return []

    async def _get_model_size_mb(self, model_name: str) -> int:
        """获取模型目录大小（MB）"""
        try:
            result = await asyncio.create_subprocess_exec(
                "du", "-sm", f"{MODEL_BASE_PATH}/{model_name}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            if result.returncode == 0:
                return int(stdout.decode().split()[0])
        except Exception:
            pass
        return 0

    # ============================================
    # 模型切换
    # ============================================
    async def switch_model(self, model_name: str, test_enabled: bool = True) -> Tuple[bool, str]:
        """切换到指定模型"""
        logger.info(f"正在切换到模型: {model_name}")
        start_time = time.time()

        try:
            response = await self.client.post(
                f"{MANAGE_BASE_URL}/manage/models/{model_name}/switch",
                params={"test_enabled": test_enabled},
                timeout=SWITCH_TIMEOUT
            )

            elapsed = time.time() - start_time
            logger.info(f"切换请求完成，耗时: {elapsed:.1f}秒, HTTP状态: {response.status_code}")

            if response.status_code == 200:
                return True, ""
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("detail", str(error_data))
                except:
                    error_msg = response.text[:500]
                logger.error(f"模型切换失败: {error_msg}")
                return False, error_msg

        except httpx.TimeoutException:
            elapsed = time.time() - start_time
            logger.error(f"模型切换超时 (已等待 {elapsed:.1f}秒)")
            return False, f"Timeout after {elapsed:.1f}s"
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"模型切换异常: {e}")
            return False, str(e)

    async def wait_for_model_ready(self, model_name: str, model_info: ModelInfo) -> Tuple[bool, float]:
        """
        等待模型就绪 - 三重检查：
        1. 后端API报告模型running
        2. vLLM健康检查通过
        3. vLLM端口可访问
        返回: (是否就绪, 等待时间)
        """
        logger.info(f"等待模型 {model_name} 就绪...")
        start_time = time.time()
        backend_reported_ready = False
        vllm_port = None

        while (time.time() - start_time) < VLLM_MAX_WAIT:
            elapsed = time.time() - start_time

            # 检查1: 后端API是否报告模型running
            if not backend_reported_ready:
                try:
                    response = await self.client.get(f"{MANAGE_BASE_URL}/manage/models")
                    if response.status_code == 200:
                        models = response.json()
                        if model_name in models and models[model_name].get("running"):
                            backend_reported_ready = True
                            vllm_port = models[model_name].get("port", 8000)
                            logger.info(f"  [{elapsed:.0f}s] 后端报告模型 running, 端口={vllm_port}")
                except Exception as e:
                    logger.debug(f"检查模型状态失败: {e}")

            # 检查2+3: 如果后端报告running，检查vLLM健康
            if backend_reported_ready and vllm_port:
                try:
                    health_resp = await self.client.get(f"http://localhost:{vllm_port}/health", timeout=HEALTH_CHECK_TIMEOUT)
                    if health_resp.status_code == 200:
                        total_time = time.time() - start_time
                        logger.info(f"模型 {model_name} 完全就绪（后端报告+vLLM健康检查通过），总等待时间: {total_time:.1f}秒")
                        return True, total_time
                except Exception:
                    pass

            await asyncio.sleep(POLL_INTERVAL)

        total_time = time.time() - start_time
        if backend_reported_ready:
            logger.warning(f"模型 {model_name} 后端报告running但vLLM健康检查未通过（等待{total_time:.1f}秒）")
        else:
            logger.warning(f"等待模型 {model_name} 就绪超时（{total_time:.1f}秒）")
        return False, total_time

    # ============================================
    # 对话测试
    # ============================================
    async def test_chat_via_gateway(self, model_name: str) -> Tuple[bool, str]:
        """通过 3000 端口网关发起对话测试"""
        logger.info(f"通过网关 ({GATEWAY_V1_URL}) 测试模型 {model_name} 对话...")

        for msg in TEST_MESSAGES:
            try:
                response = await self.chat_client.post(
                    f"{GATEWAY_V1_URL}/chat/completions",
                    json={
                        "model": model_name,
                        "messages": [msg],
                        "max_tokens": 20,
                        "temperature": 0.7,
                    },
                    timeout=CHAT_TIMEOUT
                )

                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content.strip():
                        logger.info(f"网关对话成功，响应: {content.strip()[:100]}")
                        return True, content.strip()
                    else:
                        logger.warning("网关返回空响应")
                else:
                    error_text = response.text[:500]
                    logger.warning(f"网关对话失败, HTTP {response.status_code}: {error_text}")
                    return False, f"HTTP {response.status_code}: {error_text}"

            except httpx.TimeoutException:
                logger.error(f"网关对话超时 ({CHAT_TIMEOUT}秒)")
                return False, f"Timeout after {CHAT_TIMEOUT}s"
            except Exception as e:
                logger.error(f"网关对话异常: {e}")
                return False, str(e)

        return False, "All test messages failed"

    async def test_chat_direct_vllm(self, model_name: str, model_path: str, port: int) -> Tuple[bool, str]:
        """直接通过 vLLM 端口测试（使用模型完整路径）"""
        logger.info(f"直接通过 vLLM 端口 {port} 测试对话 (模型路径: {model_path})...")

        # vLLM 通常使用完整路径作为模型标识符
        test_models = [model_path, model_name]
        
        for test_model in test_models:
            try:
                response = await self.chat_client.post(
                    f"http://localhost:{port}/v1/chat/completions",
                    json={
                        "model": test_model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 10,
                        "temperature": 0.7,
                    },
                    timeout=CHAT_TIMEOUT
                )

                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content.strip():
                        logger.info(f"直接 vLLM 测试成功 (model={test_model}): {content.strip()[:100]}")
                        return True, content.strip()
                else:
                    logger.debug(f"直接 vLLM 测试失败 (model={test_model}): HTTP {response.status_code}")
            except Exception as e:
                logger.debug(f"直接 vLLM 测试异常 (model={test_model}): {e}")

        logger.warning("直接 vLLM 测试失败（所有模型标识符均失败）")
        return False, "vLLM direct test failed"

    # ============================================
    # 日志收集与分析
    # ============================================
    def collect_service_logs(self, service_name: str, lines: int = 50) -> str:
        """收集服务日志"""
        try:
            result = subprocess.run(
                ["journalctl", "-u", service_name, "-n", str(lines), "--no-pager", "--output=short-iso"],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout
        except Exception as e:
            return f"Failed: {e}"

    def collect_app_controller_logs(self, lines: int = 50) -> str:
        """收集 app-controller 日志"""
        return self.collect_service_logs("aiclient-python", lines)

    def collect_vllm_logs(self, lines: int = 100) -> str:
        """收集 vLLM 日志"""
        return self.collect_service_logs("vllm-aiclient", lines)

    def analyze_switch_failure_logs(self, logs_before: str, logs_after: str) -> List[str]:
        """分析切换前后的日志差异，找出失败原因"""
        issues = []
        error_patterns = [
            ("OOM", "out of memory"),
            ("CUDA", "CUDA error"),
            ("memory", "insufficient memory"),
            ("vram", "VRAM"),
            ("timeout", "timeout"),
            ("failed", "failed to"),
            ("error", "error"),
            ("exception", "exception"),
        ]

        before_lines = set(logs_before.strip().split('\n')) if logs_before else set()
        after_lines = logs_after.strip().split('\n') if logs_after else []

        for line in after_lines:
            if line in before_lines:
                continue
            line_lower = line.lower()
            for pattern, desc in error_patterns:
                if pattern.lower() in line_lower:
                    issues.append(f"[{desc}] {line.strip()}")
                    break

        return issues

    def analyze_gateway_logs(self) -> str:
        """分析网关日志"""
        try:
            result = subprocess.run(
                ["docker", "logs", "aiclient2api", "--tail", "50"],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout + result.stderr
        except Exception:
            try:
                result = subprocess.run(
                    ["journalctl", "-u", "aiclient2api", "-n", "50", "--no-pager"],
                    capture_output=True, text=True, timeout=10
                )
                return result.stdout
            except Exception:
                return "无法获取网关日志"

    # ============================================
    # 主测试流程
    # ============================================
    async def run_full_test(self):
        """运行完整的模型切换测试"""
        logger.info("=" * 80)
        logger.info("模型切换测试开始")
        logger.info("=" * 80)

        # 1. 获取模型列表
        models = await self.get_models_list()
        if not models:
            logger.error("未找到可用模型，测试终止")
            return

        # 2. 记录初始状态
        self.current_model = self._get_current_running_model()
        if self.current_model:
            logger.info(f"当前运行模型: {self.current_model}")
            self.backup_model = self.current_model

        # 3. 逐个测试
        logger.info(f"\n开始测试 {len(models)} 个模型...")
        for idx, model in enumerate(models, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"[{idx}/{len(models)}] 测试模型: {model.name} (大小: {model.size_mb}MB, 后端: {model.backend_type})")
            logger.info(f"{'='*60}")

            # 跳过非 vLLM 模型（如果需要测试 llama_cpp 可以移除）
            if model.backend_type != 'vllm':
                logger.info(f"跳过非 vLLM 模型: {model.name}")
                continue

            # 收集切换前日志
            logs_before_app = self.collect_app_controller_logs(lines=20)
            logs_before_vllm = self.collect_vllm_logs(lines=20)

            test_result = TestResult(
                model_name=model.name,
                success=False,
                switch_success=False,
                chat_gateway_success=False,
                chat_vllm_success=False,
            )

            try:
                # 执行切换
                switch_ok, switch_error = await self.switch_model(model.name, test_enabled=False)
                test_result.switch_success = switch_ok

                if not switch_ok:
                    test_result.error_message = f"切换失败: {switch_error}"
                    logger.error(f"模型 {model.name} 切换失败: {switch_error}")
                    if self.backup_model:
                        logger.info(f"尝试回滚到模型: {self.backup_model}")
                        await self._rollback_model(self.backup_model)
                    self.failed_models.append(model.name)
                    continue

                # 等待模型就绪
                ready, ready_time = await self.wait_for_model_ready(model.name, model)
                test_result.ready_time_seconds = ready_time

                if not ready:
                    test_result.error_message = f"等待模型就绪超时 ({ready_time:.1f}秒)"
                    logger.error(f"模型 {model.name} 等待就绪超时")
                    if self.backup_model:
                        await self._rollback_model(self.backup_model)
                    self.failed_models.append(model.name)
                    continue

                # 获取 vLLM 实际端口
                vllm_port = self.discover_vllm_port()
                test_result.vllm_port = vllm_port
                logger.info(f"vLLM 实际端口: {vllm_port}")

                # 测试对话（通过 3000 端口网关）
                chat_ok, chat_response = await self.test_chat_via_gateway(model.name)
                test_result.chat_gateway_success = chat_ok
                test_result.chat_response = chat_response[:500] if chat_response else ""

                if not chat_ok:
                    # 如果网关失败，尝试直接 vLLM 测试
                    logger.info(f"网关对话失败，尝试直接通过 vLLM 端口 {vllm_port} 测试...")
                    direct_ok, direct_resp = await self.test_chat_direct_vllm(model.name, model.model_path, vllm_port)
                    test_result.chat_vllm_success = direct_ok

                    if direct_ok:
                        test_result.error_message = f"网关失败，但直接vLLM成功: {direct_resp[:200]}"
                        logger.warning(f"直接 vLLM 成功但网关失败，问题可能在网关配置")
                    else:
                        test_result.error_message = f"网关和直接vLLM均失败: {chat_response}"

                    if self.backup_model:
                        await self._rollback_model(self.backup_model)
                    self.failed_models.append(model.name)
                else:
                    # 网关成功，也试试直接 vLLM
                    direct_ok, direct_resp = await self.test_chat_direct_vllm(model.name, model.model_path, vllm_port)
                    test_result.chat_vllm_success = direct_ok
                    
                    test_result.success = True
                    self.current_model = model.name
                    self.backup_model = model.name
                    self.successful_models.append(model.name)
                    logger.info(f"模型 {model.name} 测试成功! (网关OK, vLLM直接={'OK' if direct_ok else 'FAIL'})")

            except Exception as e:
                test_result.error_message = str(e)
                logger.error(f"测试 {model.name} 时发生异常: {e}")
                if self.backup_model:
                    await self._rollback_model(self.backup_model)
                self.failed_models.append(model.name)

            finally:
                # 收集切换后日志
                test_result.logs_after = {
                    "app_controller": self.collect_app_controller_logs(lines=30),
                    "vllm": self.collect_vllm_logs(lines=30)
                }

                # 分析失败原因
                if not test_result.success:
                    issues = self.analyze_switch_failure_logs(
                        test_result.logs_before.get("vllm", ""),
                        test_result.logs_after.get("vllm", "")
                    )
                    if issues:
                        logger.info(f"从日志中发现的潜在问题:")
                        for issue in issues[:5]:
                            logger.info(f"  - {issue}")

                self.results.append(test_result)

        # 4. 输出汇总结果
        self._print_summary()
        self._analyze_all_failures()

    async def _rollback_model(self, model_name: str):
        """回滚到指定模型"""
        logger.info(f"正在回滚到模型: {model_name}")
        try:
            ok, err = await self.switch_model(model_name, test_enabled=False)
            if ok:
                logger.info(f"回滚到 {model_name} 成功")
                ready, _ = await self.wait_for_model_ready(model_name, ModelInfo(name=model_name, model_path=f"{MODEL_BASE_PATH}/{model_name}"))
                if ready:
                    self.current_model = model_name
                    self.backup_model = model_name
                else:
                    logger.error(f"回滚后模型 {model_name} 未就绪")
            else:
                logger.error(f"回滚到 {model_name} 失败: {err}")
        except Exception as e:
            logger.error(f"回滚异常: {e}")

    def _get_current_running_model(self) -> Optional[str]:
        """获取当前运行的模型"""
        try:
            result = subprocess.run(
                ["systemctl", "show", "vllm-aiclient", "--property=Environment", "--value"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                match = re.search(r'VLLM_MODEL_PATH=([^\s"]+)', result.stdout)
                if match:
                    path = match.group(1)
                    return path.split("/")[-1]
        except Exception:
            pass
        return None

    def _print_summary(self):
        """打印测试汇总"""
        logger.info("\n" + "=" * 80)
        logger.info("测试汇总")
        logger.info("=" * 80)

        if self.successful_models:
            logger.info(f"\n切换成功的模型 ({len(self.successful_models)}):")
            for name in self.successful_models:
                logger.info(f"  {name}")

        if self.failed_models:
            logger.info(f"\n切换失败的模型 ({len(self.failed_models)}):")
            for name in self.failed_models:
                result = next((r for r in self.results if r.model_name == name), None)
                if result:
                    details = f"切换={'OK' if result.switch_success else 'FAIL'}, "
                    details += f"网关={'OK' if result.chat_gateway_success else 'FAIL'}, "
                    details += f"vLLM直接={'OK' if result.chat_vllm_success else 'FAIL'}"
                    details += f", 端口={result.vllm_port}"
                    details += f", 就绪时间={result.ready_time_seconds:.1f}s"
                    logger.info(f"  {name}: {details}")
                    logger.info(f"    错误: {result.error_message[:200]}")

        total_vllm = len(self.results)
        logger.info(f"\n成功率: {len(self.successful_models)}/{max(total_vllm,1)} ({len(self.successful_models)/max(total_vllm,1)*100:.1f}%)")

    def _analyze_all_failures(self):
        """分析所有失败的模型"""
        logger.info("\n" + "=" * 80)
        logger.info("失败原因深度分析")
        logger.info("=" * 80)

        for result in self.results:
            if result.success:
                continue

            logger.info(f"\n--- {result.model_name} ---")
            logger.info(f"错误: {result.error_message}")

            # 分析日志
            app_logs = result.logs_after.get("app_controller", "")
            vllm_logs = result.logs_after.get("vllm", "")

            for log_source, log_content in [("app-controller", app_logs), ("vllm", vllm_logs)]:
                if not log_content:
                    continue

                lines = log_content.strip().split('\n')
                error_lines = [l for l in lines if any(kw in l.lower() for kw in ['error', 'exception', 'fail', 'oom', 'memory'])]

                if error_lines:
                    logger.info(f"  {log_source} 关键日志:")
                    for line in error_lines[-5:]:
                        logger.info(f"    {line.strip()}")

    # ============================================
    # 健康检查
    # ============================================
    async def check_services_health(self):
        """检查所有服务是否健康"""
        logger.info("检查服务健康状态...")

        # 检查 app-controller
        try:
            resp = await self.client.get(f"{MANAGE_BASE_URL}/manage/models")
            logger.info(f"  app-controller (35000): {'OK' if resp.status_code == 200 else 'FAIL'}")
        except Exception as e:
            logger.info(f"  app-controller (35000): FAIL - {e}")

        # 检查 gateway
        try:
            resp = await self.client.get(f"{GATEWAY_URL}/health")
            logger.info(f"  gateway (3000): {'OK' if resp.status_code == 200 else 'FAIL'}")
        except Exception as e:
            logger.info(f"  gateway (3000): FAIL - {e}")

        # 检查 vLLM (动态端口)
        try:
            port = self.discover_vllm_port()
            resp = await self.client.get(f"http://localhost:{port}/health")
            logger.info(f"  vLLM (port {port}): {'OK' if resp.status_code == 200 else 'FAIL'}")
        except Exception as e:
            logger.info(f"  vLLM: FAIL - {e}")


# 需要 import os for file operations
import os


# ============================================
# 入口
# ============================================
async def main():
    tester = ModelSwitchTester()
    try:
        # 1. 检查服务健康
        await tester.check_services_health()

        # 2. 运行完整测试
        await tester.run_full_test()

    except KeyboardInterrupt:
        logger.info("测试被用户中断")
    except Exception as e:
        logger.error(f"测试过程中发生异常: {e}")
        logger.exception(e)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
