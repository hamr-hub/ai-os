"""
vLLM 模型管理模块
- 扫描 /mnt/pve_models/ 目录下可用的模型
- 管理 vLLM 服务状态（启动/停止/重启/切换）
- 提供模型信息（显存需求、路径、支持的功能等）
- 模型切换后自动自测验证
- 使用互斥锁防止并发切换
"""

import os
import subprocess
import json
import asyncio
import httpx
import logging
import shutil
from typing import Dict, List, Optional, Any
from datetime import datetime
from core.cache_service import cache_service

logger = logging.getLogger("ai_controller.vllm_manager")

SYSTEMCTL_BIN = shutil.which('systemctl') or '/usr/bin/systemctl'

# 模型切换互斥锁，防止并发切换
model_switch_lock = asyncio.Lock()

# 标记是否正在切换中（用于同步函数的检查）
_switching_in_progress = False

def _load_vllm_config() -> Dict[str, Any]:
    try:
        import yaml
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config.get('vllm', {})
    except Exception as exc:
        logger.warning("Failed to load vLLM config: %s", exc)
    return {}


def _resolve_vllm_start_script(configured_path: str, service_name: str) -> str:
    service_file = f"/etc/systemd/system/{service_name}.service"
    if os.path.exists(service_file):
        try:
            import re

            with open(service_file, 'r') as f:
                content = f.read()
            match = re.search(r'^ExecStart=(\S+)', content, re.MULTILINE)
            if match:
                return match.group(1)
        except Exception as exc:
            logger.warning("Failed to resolve ExecStart from service file: %s", exc)
    return configured_path

VLLM_CONFIG = _load_vllm_config()

MODEL_BASE_PATH = VLLM_CONFIG.get('model_base_path', '/mnt/pve_models')
VLLM_SERVICE_NAME = VLLM_CONFIG.get('service_name', 'vllm-aiclient')
VLLM_START_SCRIPT = _resolve_vllm_start_script(
    VLLM_CONFIG.get('start_script', '/root/ai-suite/start_vllm_aiclient.sh'),
    VLLM_SERVICE_NAME,
)
VLLM_DEFAULT_PORT = VLLM_CONFIG.get('default_port', 8000)
VLLM_MODEL_STATE_FILE = VLLM_CONFIG.get(
    'model_state_file',
    os.path.join(os.path.dirname(VLLM_START_SCRIPT), '.vllm_model_path'),
)

# 模型显存估算配置（基于模型参数和量化类型）
# 格式：{"pattern": {"vram_gb": 数值, "multimodal": 布尔值}}
MODEL_MEMORY_ESTIMATES = {
    "Gemma-4-31B": {"vram_gb": 40, "multimodal": False},
    "Qwen3-235B": {"vram_gb": 120, "multimodal": False},
    "Qwen3.6-35B": {"vram_gb": 40, "multimodal": False},
    "deepseek-coder-v2": {"vram_gb": 80, "multimodal": False},
    "deepseek-r1-70b": {"vram_gb": 80, "multimodal": False},
    "llama-3.3-70b": {"vram_gb": 80, "multimodal": False},
    "midnight-miqu-103b": {"vram_gb": 100, "multimodal": False},
    "qwen2.5-72b": {"vram_gb": 80, "multimodal": False},
}


def get_available_models() -> List[Dict[str, Any]]:
    """
    扫描可用模型目录，返回模型列表
    """
    cached = cache_service.get("ai_controller:cache:model_list")
    if cached is not None:
        return cached
    
    models = []
    if not os.path.exists(MODEL_BASE_PATH):
        return models

    for model_name in sorted(os.listdir(MODEL_BASE_PATH)):
        model_path = os.path.join(MODEL_BASE_PATH, model_name)
        if not os.path.isdir(model_path):
            continue
        
        # 跳过非模型目录
        if model_name in ['hf_cache', 'trans_pkg', 'venv']:
            continue
        
        # 估算显存需求
        memory_info = _estimate_memory(model_name)
        
        # 获取模型详情
        model_info = {
            "name": model_name,
            "path": model_path,
            "required_memory_gb": memory_info["vram_gb"],
            "multimodal": memory_info["multimodal"],
            "size_mb": _get_model_size(model_path),
            "running": False,
            "status": "stopped"
        }
        
        models.append(model_info)
    
    cache_service.set("ai_controller:cache:model_list", models, ttl_seconds=60)
    return models


def _find_model_name_from_path(model_path: str) -> Optional[str]:
    """
    根据模型路径从配置中查找对应的模型名称
    """
    try:
        import yaml
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        
        if not os.path.exists(config_path):
            return None
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if not config or 'models' not in config:
            return None
        
        for model_name, model_config in config['models'].items():
            config_model_path = model_config.get('model_path', '')
            if config_model_path == model_path:
                return model_name
        
        # 如果精确匹配失败，尝试基于目录名称匹配
        model_dir_name = os.path.basename(model_path)
        for model_name, model_config in config['models'].items():
            config_model_path = model_config.get('model_path', '')
            if os.path.basename(config_model_path) == model_dir_name:
                return model_name
        
        return None
    except Exception as exc:
        logger.warning("Failed to map model path to configured model name: %s", exc)
        return None


def _estimate_memory(model_name: str) -> Dict[str, Any]:
    """
    根据模型名称估算显存需求
    """
    for pattern, info in MODEL_MEMORY_ESTIMATES.items():
        if pattern.lower() in model_name.lower():
            return info

    # 默认值：基于名称中的参数数量估算
    if "31b" in model_name.lower():
        return {"vram_gb": 40, "multimodal": False}
    elif "70b" in model_name.lower():
        return {"vram_gb": 80, "multimodal": False}
    elif "35b" in model_name.lower():
        return {"vram_gb": 40, "multimodal": False}
    elif "235b" in model_name.lower():
        return {"vram_gb": 120, "multimodal": False}
    else:
        return {"vram_gb": 40, "multimodal": False}


def _get_model_size(model_path: str) -> int:
    """
    获取模型目录大小（MB）
    """
    try:
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(model_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except:
                    pass
        return int(total_size / (1024 * 1024))
    except Exception as exc:
        logger.warning("Failed to calculate model size for %s: %s", model_path, exc)
        return 0


def get_current_model_info() -> Optional[Dict[str, Any]]:
    """
    获取当前运行的 vLLM 模型信息（返回配置文件中的模型名称）
    优先级：systemd 环境变量 > 启动脚本解析
    """
    try:
        import re

        model_path = None

        # 优先读取启动脚本使用的状态文件，避免只读 systemd 环境导致识别漂移。
        if os.path.exists(VLLM_MODEL_STATE_FILE):
            with open(VLLM_MODEL_STATE_FILE, 'r') as f:
                state_model_path = f.read().strip()
            if state_model_path:
                model_path = state_model_path

        # 其次读取 systemd 当前生效的环境变量，兼容 /run runtime override。

        try:
            result = subprocess.run(
                [SYSTEMCTL_BIN, 'show', VLLM_SERVICE_NAME, '--property=Environment', '--value'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if not model_path and result.returncode == 0:
                match = re.search(r'VLLM_MODEL_PATH=([^\s"]+)', result.stdout)
                if match:
                    model_path = match.group(1)
        except Exception as exc:
            logger.warning("Failed to read effective systemd environment: %s", exc)

        # 如果拿不到生效环境，再回退到持久化 service 文件。
        service_file = f"/etc/systemd/system/{VLLM_SERVICE_NAME}.service"
        if not model_path and os.path.exists(service_file):
            with open(service_file, 'r') as f:
                content = f.read()
            match = re.search(r'Environment="VLLM_MODEL_PATH=([^"]*)"', content)
            if match:
                model_path = match.group(1)
        
        # 如果 systemd 环境变量未设置，尝试从启动脚本读取
        if not model_path and os.path.exists(VLLM_START_SCRIPT):
            with open(VLLM_START_SCRIPT, 'r') as f:
                content = f.read()
            
            for line in content.split('\n'):
                if 'vllm serve' in line and not line.strip().startswith('#'):
                    parts = line.strip().split()
                    for i, part in enumerate(parts):
                        if part == 'serve' and i + 1 < len(parts):
                            model_path = parts[i + 1].strip('"').strip("'")
                            if model_path.startswith('$'):
                                var_name = model_path.lstrip('$').strip('{}')
                                model_path = os.environ.get(var_name, '')
                                if not model_path:
                                    for env_line in content.split('\n'):
                                        if 'MODEL_PATH=' in env_line and ':-' in env_line:
                                            match = re.search(r':-([^}]+)\}', env_line)
                                            if match:
                                                model_path = match.group(1).strip('"').strip("'")
                                                break
                            break
                    
                    if model_path:
                        break

        if not model_path:
            return None

        service_running = _is_service_running()
        config_model_name = _find_model_name_from_path(model_path)
        
        return {
            "name": config_model_name or os.path.basename(model_path),
            "path": model_path,
            "service": VLLM_SERVICE_NAME,
            "port": VLLM_DEFAULT_PORT,
            "running": service_running,
            "status": "running" if service_running else "stopped"
        }
    except Exception as e:
        logger.warning("Failed to get current vLLM model info: %s", e)
        return None


def _is_service_running() -> bool:
    """
    检查 vLLM 服务是否运行
    """
    try:
        result = subprocess.run(
            [SYSTEMCTL_BIN, 'is-active', VLLM_SERVICE_NAME],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == 'active'
    except Exception as exc:
        logger.warning("Failed to query vLLM service status: %s", exc)
        return False


def start_vllm_service() -> bool:
    """
    启动 vLLM 服务
    """
    try:
        result = subprocess.run(
            [SYSTEMCTL_BIN, 'start', VLLM_SERVICE_NAME],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        logger.error("Failed to start vLLM service: %s", e)
        return False


def stop_vllm_service() -> bool:
    """
    停止 vLLM 服务
    """
    try:
        result = subprocess.run(
            [SYSTEMCTL_BIN, 'stop', VLLM_SERVICE_NAME],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        logger.error("Failed to stop vLLM service: %s", e)
        return False


def restart_vllm_service() -> bool:
    """
    重启 vLLM 服务
    """
    try:
        result = subprocess.run(
            [SYSTEMCTL_BIN, 'restart', VLLM_SERVICE_NAME],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        logger.error("Failed to restart vLLM service: %s", e)
        return False


def get_vllm_service_status() -> Dict[str, Any]:
    """
    获取 vLLM 服务状态
    """
    try:
        result = subprocess.run(
            [SYSTEMCTL_BIN, 'show', VLLM_SERVICE_NAME, '--property=ActiveState,SubState,MainPID,MemoryCurrent', '--value'],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split('\n')
        
        active_state = "unknown"
        sub_state = "unknown"
        pid = None
        memory_bytes = None
        
        for line in lines:
            line = line.strip()
            if line in ['active', 'inactive', 'failed', 'deactivating', 'activating']:
                active_state = line
            elif line in ['running', 'dead', 'exited', 'failed']:
                sub_state = line
            elif line.isdigit():
                if pid is None:
                    pid = int(line)
                else:
                    memory_bytes = int(line)
        
        return {
            "service": VLLM_SERVICE_NAME,
            "active_state": active_state,
            "sub_state": sub_state,
            "pid": pid,
            "memory_bytes": memory_bytes,
            "running": active_state == "active"
        }
    except Exception as e:
        logger.error("Failed to check vLLM service status: %s", e)
        return {"service": VLLM_SERVICE_NAME, "running": False, "error": str(e)}


def switch_vllm_model(model_name: str) -> Dict[str, Any]:
    """
    切换到指定模型（同步版本）：
    1. 更新启动脚本
    2. 重启 vLLM 服务
    """
    global _switching_in_progress
    
    # 检查是否正在切换中
    if _switching_in_progress:
        return {
            "success": False,
            "error": "Model switch is already in progress, please wait for it to complete",
            "model_path": os.path.join(MODEL_BASE_PATH, model_name)
        }

    _switching_in_progress = True
    
    try:
        model_path = os.path.join(MODEL_BASE_PATH, model_name)

        # 检查模型是否存在
        if not os.path.exists(model_path):
            return {
                "success": False,
                "error": f"Model not found: {model_name}",
                "model_path": model_path
            }

        # 更新启动脚本
        script_updated = _update_vllm_script(model_path)
        if not script_updated:
            return {
                "success": False,
                "error": "Failed to update vLLM start script",
                "model_path": model_path
            }

        # 重启服务
        service_restarted = restart_vllm_service()
        if not service_restarted:
            return {
                "success": False,
                "error": "Failed to restart vLLM service",
                "model_path": model_path
            }

        return {
            "success": True,
            "model": model_name,
            "model_path": model_path,
            "service": VLLM_SERVICE_NAME,
            "status": "restarting"
        }
    finally:
        _switching_in_progress = False


async def switch_vllm_model_with_test(model_name: str, test_enabled: bool = True, model_path: str = None) -> Dict[str, Any]:
    """
    切换到指定模型并进行自测：
    1. 更新启动脚本
    2. 重启 vLLM 服务
    3. 等待服务启动
    4. 执行自测验证模型是否可用
    :param model_name: 模型名称
    :param test_enabled: 是否启用自测
    :param model_path: 模型路径（可选，用于测试场景）
    :return: 切换结果字典，包含自测结果
    """
    global _switching_in_progress
    
    # 使用 acquire() 方法尝试获取锁，避免竞态条件
    try:
        await asyncio.wait_for(model_switch_lock.acquire(), timeout=0.1)
    except asyncio.TimeoutError:
        # 锁已被占用，说明正在切换中
        return {
            "success": False,
            "error": "Model switch is already in progress, please wait for it to complete",
            "model_path": model_path if model_path else os.path.join(MODEL_BASE_PATH, model_name)
        }
    
    # 成功获取锁，执行切换
    _switching_in_progress = True
    try:
        return await _do_switch_vllm_model(model_name, test_enabled, model_path)
    finally:
        _switching_in_progress = False
        model_switch_lock.release()


async def _wait_for_vllm_ready(max_wait: int = 180, check_interval: int = 5) -> bool:
    """
    等待 vLLM 服务就绪（智能等待）
    :param max_wait: 最大等待时间（秒）
    :param check_interval: 检查间隔（秒）
    :return: 是否就绪
    """
    health_url = f"http://localhost:{VLLM_DEFAULT_PORT}/health"
    elapsed = 0
    
    while elapsed < max_wait:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(health_url)
                if response.status_code == 200:
                    logger.info("vLLM service ready after %d seconds", elapsed)
                    return True
        except Exception:
            pass
        
        await asyncio.sleep(check_interval)
        elapsed += check_interval
    
    logger.warning("vLLM service not ready after %d seconds", max_wait)
    return False


async def _do_switch_vllm_model(model_name: str, test_enabled: bool = True, model_path: str = None) -> Dict[str, Any]:
    """
    实际执行模型切换的内部函数
    """
    if model_path is None:
        model_path = os.path.join(MODEL_BASE_PATH, model_name)

    if not os.path.exists(model_path):
        return {
            "success": False,
            "error": f"Model not found: {model_name}",
            "model_path": model_path
        }

    script_updated = _update_vllm_script(model_path)
    if not script_updated:
        return {
            "success": False,
            "error": "Failed to update vLLM start script",
            "model_path": model_path
        }

    service_restarted = restart_vllm_service()
    if not service_restarted:
        return {
            "success": False,
            "error": "Failed to restart vLLM service",
            "model_path": model_path
        }

    # 智能等待服务就绪（最多等待 180 秒）
    service_ready = await _wait_for_vllm_ready(max_wait=180, check_interval=5)
    
    if not service_ready:
        return {
            "success": False,
            "error": "vLLM service failed to start within timeout",
            "model": model_name,
            "model_path": model_path,
            "service": VLLM_SERVICE_NAME,
            "status": "timeout"
        }

    # 执行自测
    test_result = None
    if test_enabled:
        test_result = await _test_vllm_model(model_name)
        
        if not test_result.get("success", False):
            return {
                "success": False,
                "error": f"Model switch failed: {test_result.get('message', 'Unknown error')}",
                "model": model_name,
                "model_path": model_path,
                "service": VLLM_SERVICE_NAME,
                "status": "test_failed",
                "test_result": test_result
            }

    return {
        "success": True,
        "model": model_name,
        "model_path": model_path,
        "service": VLLM_SERVICE_NAME,
        "status": "switched" if not test_enabled else "switched_and_tested",
        "test_result": test_result
    }


async def wait_for_vllm_model_ready_and_test(model_name: str, test_enabled: bool = True) -> Dict[str, Any]:
    """
    对已经发起切换的 vLLM 模型执行后续等待与自测，不再重复改脚本/重启服务。
    """
    model_path = os.path.join(MODEL_BASE_PATH, model_name)
    if not os.path.exists(model_path):
        return {
            "success": False,
            "error": f"Model not found: {model_name}",
            "model": model_name,
            "model_path": model_path,
            "service": VLLM_SERVICE_NAME,
            "status": "missing",
        }

    service_ready = await _wait_for_vllm_ready(max_wait=180, check_interval=5)
    if not service_ready:
        return {
            "success": False,
            "error": "vLLM service failed to start within timeout",
            "model": model_name,
            "model_path": model_path,
            "service": VLLM_SERVICE_NAME,
            "status": "timeout",
        }

    test_result = None
    if test_enabled:
        test_result = await _test_vllm_model(model_name)
        if not test_result.get("success", False):
            return {
                "success": False,
                "error": f"Model switch failed: {test_result.get('message', 'Unknown error')}",
                "model": model_name,
                "model_path": model_path,
                "service": VLLM_SERVICE_NAME,
                "status": "test_failed",
                "test_result": test_result,
            }

    return {
        "success": True,
        "model": model_name,
        "model_path": model_path,
        "service": VLLM_SERVICE_NAME,
        "status": "ready" if not test_enabled else "ready_and_tested",
        "test_result": test_result,
    }


def _write_runtime_service_override(model_path: str) -> bool:
    """Write a writable runtime override so model switching still works when /etc is read-only."""
    try:
        override_dir = f"/run/systemd/system/{VLLM_SERVICE_NAME}.service.d"
        override_file = os.path.join(override_dir, "override.conf")
        os.makedirs(override_dir, exist_ok=True)
        with open(override_file, 'w') as f:
            f.write('[Service]\n')
            f.write(f'Environment="VLLM_MODEL_PATH={model_path}"\n')
        result = subprocess.run([SYSTEMCTL_BIN, 'daemon-reload'], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            logger.warning("daemon-reload failed after runtime override: %s", (result.stderr or '').strip())
            return False
        logger.info("Updated runtime service override: %s", model_path)
        return True
    except Exception as exc:
        logger.warning("Failed to write runtime service override: %s", exc)
        return False


def _write_model_state_file(model_path: str) -> bool:
    try:
        state_dir = os.path.dirname(VLLM_MODEL_STATE_FILE)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
        with open(VLLM_MODEL_STATE_FILE, 'w') as f:
            f.write(model_path)
            f.write('\n')
        logger.info("Updated model state file: %s", model_path)
        return True
    except Exception as exc:
        logger.warning("Failed to write model state file: %s", exc)
        return False


def _update_vllm_script(model_path: str) -> bool:
    """
    更新 vLLM systemd 服务文件和启动脚本中的模型路径
    优先级：systemd 服务文件 > 启动脚本
    """
    try:
        import re

        state_updated = _write_model_state_file(model_path)

        # 再尝试写入 runtime override，兼容 /etc 只读的部署环境。
        runtime_updated = _write_runtime_service_override(model_path)

        # 同时尽量更新持久化 service 文件；失败时不影响 runtime 切换。
        systemd_updated = False
        service_file = f"/etc/systemd/system/{VLLM_SERVICE_NAME}.service"
        if os.path.exists(service_file):
            try:
                with open(service_file, 'r') as f:
                    content = f.read()

                new_content = re.sub(
                    r'Environment="VLLM_MODEL_PATH=[^"]*"',
                    f'Environment="VLLM_MODEL_PATH={model_path}"',
                    content
                )

                if new_content != content:
                    with open(service_file, 'w') as f:
                        f.write(new_content)
                    subprocess.run([SYSTEMCTL_BIN, 'daemon-reload'], capture_output=True, timeout=10)
                    logger.info("Updated systemd service file: %s", model_path)
                    systemd_updated = True
            except OSError as exc:
                logger.warning("Failed to persist systemd service file update: %s", exc)
        
        if not os.path.exists(VLLM_START_SCRIPT):
            logger.warning("Start script not found: %s", VLLM_START_SCRIPT)
            return systemd_updated

        with open(VLLM_START_SCRIPT, 'r') as f:
            content = f.read()

        lines = content.split('\n')
        new_lines = []
        replaced = False

        for line in lines:
            # 匹配 MODEL_PATH="${VLLM_MODEL_PATH:-...}" 或 MODEL_PATH="..." 格式
            if 'MODEL_PATH=' in line and '=' in line and not line.strip().startswith('#'):
                # 处理带默认值的格式：MODEL_PATH="${VLLM_MODEL_PATH:-/path/to/model}"
                if ':-' in line:
                    # 只替换默认值部分
                    new_line = re.sub(
                        r'(:-)[^}]+\}',
                        f':-{model_path}"',
                        line
                    )
                    # 如果正则替换失败，使用原始行
                    if ':-' not in new_line:
                        new_line = line
                    new_lines.append(new_line)
                    replaced = True
                    continue
                # 处理直接赋值的格式：MODEL_PATH="/path/to/model"
                elif 'VLLM_MODEL_PATH' in line:
                    parts = line.split('=', 1)
                    if len(parts) >= 2:
                        new_line = f'{parts[0]}="{model_path}"'
                        new_lines.append(new_line)
                        replaced = True
                        continue
            
            # 匹配 vllm serve 命令（如果存在硬编码路径）
            if 'vllm serve' in line and not line.strip().startswith('#'):
                # 检查是否包含变量引用，如果已经是变量引用则不修改
                if '$MODEL_PATH' in line or '${MODEL_PATH}' in line:
                    new_lines.append(line)
                    continue
                
                # 替换硬编码的模型路径
                parts = line.split('vllm serve')
                if len(parts) >= 2:
                    rest_parts = parts[1].strip().split()
                    if len(rest_parts) >= 1:
                        new_line = f'{parts[0]}vllm serve "{model_path}" {" ".join(rest_parts[1:])}'
                        new_lines.append(new_line)
                        replaced = True
                        continue
            
            new_lines.append(line)

        if not replaced and not systemd_updated and not runtime_updated and not state_updated:
            logger.warning("No model path found in start script to update")
            return False

        if replaced:
            with open(VLLM_START_SCRIPT, 'w') as f:
                f.write('\n'.join(new_lines))
            logger.info("Updated start script: %s", model_path)

        return state_updated or runtime_updated or systemd_updated or replaced
    except Exception as e:
        logger.error("Failed to update vLLM script: %s", e)
        return False


async def _test_vllm_model(model_name: str, max_retries: int = 5, retry_delay: int = 10) -> Dict[str, Any]:
    """
    自测 vLLM 模型是否可用
    :param model_name: 模型名称
    :param max_retries: 最大重试次数
    :param retry_delay: 重试间隔（秒）
    :return: 自测结果字典
    """
    vllm_url = f"http://localhost:{VLLM_DEFAULT_PORT}/v1/chat/completions"
    
    test_payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hello, please respond with a brief message."}],
        "max_tokens": 10,
        "temperature": 0.7
    }
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(vllm_url, json=test_payload, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # 检查响应是否有效
                    if result.get("choices") and len(result["choices"]) > 0:
                        content = result["choices"][0].get("message", {}).get("content", "")
                        if content.strip():
                            return {
                                "success": True,
                                "message": "Model test passed",
                                "attempt": attempt + 1,
                                "response_content": content.strip(),
                                "token_count": result.get("usage", {}).get("completion_tokens", 0)
                            }
                        else:
                            return {
                                "success": False,
                                "message": "Model returned empty response",
                                "attempt": attempt + 1,
                                "error": "Empty response content"
                            }
                    else:
                        return {
                            "success": False,
                            "message": "Invalid response structure from vLLM",
                            "attempt": attempt + 1,
                            "error": "Missing choices in response"
                        }
                else:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return {
                        "success": False,
                        "message": f"vLLM returned HTTP error {response.status_code}",
                        "attempt": attempt + 1,
                        "error": response.text[:200] if response.text else "Unknown error"
                    }
        except httpx.HTTPError as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            return {
                "success": False,
                "message": f"HTTP request failed",
                "attempt": attempt + 1,
                "error": str(e)
            }
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            return {
                "success": False,
                "message": "Request timed out",
                "attempt": attempt + 1,
                "error": "Timeout waiting for response"
            }
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            return {
                "success": False,
                "message": "Unexpected error during test",
                "attempt": attempt + 1,
                "error": str(e)
            }
    
    return {
        "success": False,
        "message": "All retry attempts failed",
        "attempt": max_retries,
        "error": "Max retries exceeded"
    }
