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
from typing import Dict, List, Optional, Any
from datetime import datetime
from core.cache_service import cache_service

# 模型切换互斥锁，防止并发切换
model_switch_lock = asyncio.Lock()

# 标记是否正在切换中（用于同步函数的检查）
_switching_in_progress = False

# 模型扫描路径
MODEL_BASE_PATH = "/mnt/pve_models"

# vLLM 服务名称
VLLM_SERVICE_NAME = "vllm"

# vLLM 启动脚本路径
VLLM_START_SCRIPT = "/root/ai-suite/start_vllm.sh"

# vLLM API 默认端口
VLLM_DEFAULT_PORT = 8000

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
    except Exception:
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
    except:
        return 0


def get_current_model_info() -> Optional[Dict[str, Any]]:
    """
    获取当前运行的 vLLM 模型信息（返回配置文件中的模型名称）
    """
    try:
        # 读取启动脚本获取当前运行的模型路径
        if not os.path.exists(VLLM_START_SCRIPT):
            return None

        with open(VLLM_START_SCRIPT, 'r') as f:
            content = f.read()

        # 解析模型路径
        model_path = None
        for line in content.split('\n'):
            if 'vllm serve' in line and not line.strip().startswith('#'):
                # 提取模型路径
                parts = line.strip().split()
                for i, part in enumerate(parts):
                    if part == 'serve' and i + 1 < len(parts):
                        model_path = parts[i + 1].strip('"').strip("'")
                        break

        if not model_path:
            return None

        # 获取服务状态
        service_running = _is_service_running()

        # 从配置中查找匹配的模型名称（而不是直接使用路径中的名称）
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
        return None


def _is_service_running() -> bool:
    """
    检查 vLLM 服务是否运行
    """
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', VLLM_SERVICE_NAME],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == 'active'
    except:
        return False


def start_vllm_service() -> bool:
    """
    启动 vLLM 服务
    """
    try:
        result = subprocess.run(
            ['systemctl', 'start', VLLM_SERVICE_NAME],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        return False


def stop_vllm_service() -> bool:
    """
    停止 vLLM 服务
    """
    try:
        result = subprocess.run(
            ['systemctl', 'stop', VLLM_SERVICE_NAME],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        return False


def restart_vllm_service() -> bool:
    """
    重启 vLLM 服务
    """
    try:
        result = subprocess.run(
            ['systemctl', 'restart', VLLM_SERVICE_NAME],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        return False


def get_vllm_service_status() -> Dict[str, Any]:
    """
    获取 vLLM 服务状态
    """
    try:
        result = subprocess.run(
            ['systemctl', 'show', VLLM_SERVICE_NAME, '--property=ActiveState,SubState,MainPID,MemoryCurrent', '--value'],
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
    
    # 尝试获取锁，如果正在切换则立即返回
    if not model_switch_lock.locked():
        async with model_switch_lock:
            _switching_in_progress = True
            try:
                return await _do_switch_vllm_model(model_name, test_enabled, model_path)
            finally:
                _switching_in_progress = False
    else:
        return {
            "success": False,
            "error": "Model switch is already in progress, please wait for it to complete",
            "model_path": model_path if model_path else os.path.join(MODEL_BASE_PATH, model_name)
        }


async def _do_switch_vllm_model(model_name: str, test_enabled: bool = True, model_path: str = None) -> Dict[str, Any]:
    """
    实际执行模型切换的内部函数
    """
    if model_path is None:
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

    # 等待服务启动（至少等待5秒）
    await asyncio.sleep(5)

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


def _update_vllm_script(model_path: str) -> bool:
    """
    更新 vLLM 启动脚本中的模型路径
    """
    try:
        if not os.path.exists(VLLM_START_SCRIPT):
            return False

        with open(VLLM_START_SCRIPT, 'r') as f:
            content = f.read()

        # 替换模型路径
        lines = content.split('\n')
        new_lines = []
        replaced = False

        for line in lines:
            if 'vllm serve' in line and not line.strip().startswith('#'):
                # 替换模型路径
                parts = line.split('vllm serve')
                if len(parts) >= 2:
                    rest_parts = parts[1].strip().split()
                    if len(rest_parts) >= 1:
                        new_line = f'{parts[0]}vllm serve "{model_path}" {" ".join(rest_parts[1:])}'
                        new_lines.append(new_line)
                        replaced = True
                        continue
            new_lines.append(line)

        if not replaced:
            return False

        # 写回文件
        with open(VLLM_START_SCRIPT, 'w') as f:
            f.write('\n'.join(new_lines))

        return True
    except Exception as e:
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
