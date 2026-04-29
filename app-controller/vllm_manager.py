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
VLLM_BACKEND_BASE_URL = VLLM_CONFIG.get('backend_base_url', '').rstrip('/')
VLLM_HEALTH_URL = VLLM_CONFIG.get('health_url', '').rstrip('/')
VLLM_MODEL_STATE_FILE = VLLM_CONFIG.get(
    'model_state_file',
    os.path.join(os.path.dirname(VLLM_START_SCRIPT), '.vllm_model_path'),
)

_cached_vllm_port = None
_port_discovery_time = None

def _build_vllm_base_url(port: int) -> str:
    if VLLM_BACKEND_BASE_URL:
        return VLLM_BACKEND_BASE_URL
    return f"http://localhost:{port}"


def _build_vllm_health_url(port: int) -> str:
    if VLLM_HEALTH_URL:
        return VLLM_HEALTH_URL
    return f"{_build_vllm_base_url(port)}/health"


def discover_vllm_port() -> int:
    global _cached_vllm_port, _port_discovery_time
    
    if _cached_vllm_port is not None:
        logger.debug("Using cached vLLM port: %d", _cached_vllm_port)
        return _cached_vllm_port
    
    import re
    
    def check_port(port, timeout=2):
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def check_health(port, timeout=2):
        health_url = _build_vllm_health_url(port)
        try:
            import httpx
            with httpx.Client(timeout=timeout) as client:
                response = client.get(health_url)
                return response.status_code == 200
        except Exception:
            return False
    
    try:
        with open(VLLM_START_SCRIPT, 'r') as f:
            script_content = f.read()
        
        port_match = re.search(r'--port\s+(\d+)', script_content)
        if port_match:
            port = int(port_match.group(1))
            if check_port(port) and check_health(port):
                logger.info("Discovered vLLM port from start script: %d", port)
                _cached_vllm_port = port
                _port_discovery_time = datetime.now()
                return port
    except Exception as exc:
        logger.debug("Failed to parse port from start script: %s", exc)
    
    try:
        service_file = f"/etc/systemd/system/{VLLM_SERVICE_NAME}.service"
        if os.path.exists(service_file):
            with open(service_file, 'r') as f:
                service_content = f.read()
            
            exec_start_match = re.search(r'^ExecStart=(.+)$', service_content, re.MULTILINE)
            if exec_start_match:
                exec_start_line = exec_start_match.group(1)
                port_match = re.search(r'--port\s+(\d+)', exec_start_line)
                if port_match:
                    port = int(port_match.group(1))
                    if check_port(port) and check_health(port):
                        logger.info("Discovered vLLM port from systemd service: %d", port)
                        _cached_vllm_port = port
                        _port_discovery_time = datetime.now()
                        return port
    except Exception as exc:
        logger.debug("Failed to parse port from systemd service: %s", exc)
    
    scan_ports = [8000, 8001, 8002, 8003, 8004, 8005, 8006, 8007, 8008, 8009, 8010]
    for port in scan_ports:
        if check_port(port):
            health_url = f"http://localhost:{port}/health"
            try:
                import httpx
                with httpx.Client(timeout=2) as client:
                    response = client.get(health_url)
                    if response.status_code == 200:
                        logger.info("Discovered vLLM port by scanning: %d", port)
                        _cached_vllm_port = port
                        _port_discovery_time = datetime.now()
                        return port
            except Exception:
                continue
    
    logger.warning("Failed to discover vLLM port, using default: %d", VLLM_DEFAULT_PORT)
    _cached_vllm_port = VLLM_DEFAULT_PORT
    _port_discovery_time = datetime.now()
    return VLLM_DEFAULT_PORT

def refresh_vllm_port_cache():
    global _cached_vllm_port, _port_discovery_time
    _cached_vllm_port = None
    _port_discovery_time = None
    logger.info("vLLM port cache refreshed")


def get_configured_vllm_port() -> int:
    import re
    try:
        with open(VLLM_START_SCRIPT, 'r') as f:
            script_content = f.read()
        port_match = re.search(r'VLLM_PORT="\$\{VLLM_PORT:-(\d+)\}"', script_content)
        if port_match:
            return int(port_match.group(1))
        port_match = re.search(r'--port\s+(\d+)', script_content)
        if port_match:
            return int(port_match.group(1))
    except Exception as exc:
        logger.debug("Failed to parse port from start script: %s", exc)
    return VLLM_DEFAULT_PORT
    discover_vllm_port()

# 模型显存估算配置（基于模型参数和量化类型）
# 格式：{"pattern": {"vram_gb": 数值, "multimodal": 布尔值}}
MODEL_MEMORY_ESTIMATES = {
    "Gemma-4-31B": {"vram_gb": 40, "multimodal": False},
    "Qwen3-235B": {"vram_gb": 48, "multimodal": False},
    "Qwen3.6-35B": {"vram_gb": 40, "multimodal": False},
    "deepseek-coder-v2": {"vram_gb": 80, "multimodal": False},
    "deepseek-r1-70b": {"vram_gb": 80, "multimodal": False},
    "llama-3.3-70b": {"vram_gb": 70, "multimodal": False},
    "midnight-miqu-103b": {"vram_gb": 100, "multimodal": False},
    "qwen2.5-72b": {"vram_gb": 70, "multimodal": False},
}


def get_available_models() -> List[Dict[str, Any]]:
    """
    扫描可用模型目录，返回模型列表。
    config.yaml 中的 required_memory 优先于硬编码估算。
    """
    cached = cache_service.get("ai_controller:cache:model_list")
    if cached is not None:
        return cached

    models_config = _load_models_config()

    models = []
    if not os.path.exists(MODEL_BASE_PATH):
        return models

    for model_name in sorted(os.listdir(MODEL_BASE_PATH)):
        model_path = os.path.join(MODEL_BASE_PATH, model_name)
        if not os.path.isdir(model_path):
            continue

        if model_name in ['hf_cache', 'trans_pkg', 'venv']:
            continue

        memory_info = _estimate_memory(model_name)
        config = models_config.get(model_name, {})
        config_required_memory = _parse_config_memory(config.get('required_memory', ''))
        if config_required_memory > 0:
            memory_info = {
                "vram_gb": config_required_memory,
                "multimodal": config.get('supports_images', memory_info["multimodal"]),
            }

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


def _load_models_config() -> Dict[str, Any]:
    try:
        import yaml
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config.get('models', {})
    except Exception as exc:
        logger.warning("Failed to load models config: %s", exc)
    return {}


def _parse_config_memory(value) -> int:
    if not value:
        return 0
    s = str(value).strip().upper()
    for suffix, factor in [('GB', 1), ('TB', 1024), ('MB', 0)]:
        if s.endswith(suffix):
            try:
                return int(float(s[:-len(suffix)].strip()) * factor)
            except ValueError:
                return 0
    try:
        return int(s)
    except ValueError:
        return 0


def _load_model_groups_config() -> Dict[str, str]:
    try:
        import yaml
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            groups = config.get('model_groups', {})
            if groups:
                return groups
    except Exception as exc:
        logger.warning("Failed to load model_groups config: %s", exc)
    return {}


def extract_base_model_name(model_name: str) -> str:
    """
    从模型名称中提取基础模型名称，用于聚合分组。
    策略优先级：
    1. config.yaml 的 model_groups 显式规则
    2. 去除量化/变体后缀（-Instruct/-AWQ/-GGUF/-mini 等）
    3. 按参数量(B)截断（如 Qwen3.6-35B-xxx -> Qwen3.6-35B）
    4. fallback 取前两段
    """
    import re

    config_groups = _load_model_groups_config()
    for group_name, pattern in config_groups.items():
        if re.match(pattern, model_name, re.IGNORECASE):
            return group_name

    variant_suffixes = [
        '-Instruct', '-Chat', '-Uncensored', '-Abliterated',
        '-AWQ', '-GPTQ', '-GGUF', '-EXL2', '-ExL2',
        '-NVFP4', '-FP8', '-FP16', '-BF16',
        '-Q4', '-Q4_K_M', '-Q5', '-Q5_K_M', '-Q8', '-Q8_0',
        '-mini', '-base', '-it', '-vision',
        '-5\\.0bpw', '-6\\.5bpw', '-8\\.0bpw', '-8_0',
    ]
    stripped = model_name
    for suffix_pattern in variant_suffixes:
        m = re.search(suffix_pattern, stripped, re.IGNORECASE)
        if m and m.start() > 0:
            stripped = stripped[:m.start()]
            break

    if stripped != model_name:
        return stripped

    if '-' in model_name:
        parts = model_name.split('-')
        for i, part in enumerate(parts):
            if re.search(r'\d+[Bb]', part, re.IGNORECASE):
                return '-'.join(parts[:i + 1])

        if len(parts) >= 3 and not re.search(r'\d', parts[1], re.IGNORECASE):
            return '-'.join(parts[:2])

        if len(parts) >= 2:
            return '-'.join(parts[:2])

    return model_name


def get_aggregated_models() -> List[Dict[str, Any]]:
    """
    获取聚合后的模型列表，按基础模型名称分组，每组内按文件大小排序
    包含每个模型的 vLLM 配置参数
    """
    cached = cache_service.get("ai_controller:cache:model_list:aggregated")
    if cached is not None:
        return cached

    try:
        import yaml
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        models_config = {}
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            models_config = config.get('models', {})
    except Exception as exc:
        logger.warning("Failed to load models config: %s", exc)
        models_config = {}

    models = get_available_models()

    aggregated = {}
    for model in models:
        base_name = extract_base_model_name(model["name"])
        if base_name not in aggregated:
            aggregated[base_name] = {
                "base_name": base_name,
                "variants": []
            }
        
        model_name = model["name"]
        config = models_config.get(model_name, {})
        vllm_params = config.get('vllm_params', {})
        
        if not vllm_params:
            vllm_params = _recommend_vllm_params(model_name, model.get("required_memory_gb", 40))
        
        variant = {
            **model,
            "backend_type": config.get('service', 'vllm').replace('-aiclient', '') if config.get('service') else 'vllm',
            "vllm_params": vllm_params,
            "port": config.get('port'),
            "description": config.get('description', ''),
            "required_memory": config.get('required_memory', ''),
            "supports_images": config.get('supports_images', False),
            "supports_tool_calling": config.get('supports_tool_calling', False),
            "supports_image_generation": config.get('supports_image_generation', False),
            "preloaded": config.get('preload', False),
        }
        
        aggregated[base_name]["variants"].append(variant)

    result = []
    for base_name, group in sorted(aggregated.items()):
        variants = sorted(group["variants"], key=lambda x: x.get("size_mb", 0))
        total_size_mb = sum(v.get("size_mb", 0) for v in variants)
        result.append({
            "base_name": base_name,
            "variant_count": len(variants),
            "total_size_mb": total_size_mb,
            "variants": variants
        })

    result.sort(key=lambda x: x["base_name"].lower())

    cache_service.set("ai_controller:cache:model_list:aggregated", result, ttl_seconds=60)
    return result


def _recommend_vllm_params(model_name: str, required_memory_gb: int, gpu_memory_gb: int = 96) -> Dict[str, Any]:
    """
    根据模型显存需求和GPU显存大小推荐 vLLM 启动参数
    
    :param model_name: 模型名称
    :param required_memory_gb: 模型所需显存（GB）
    :param gpu_memory_gb: GPU总显存（GB），默认96G
    :return: vLLM参数配置字典
    """
    available_memory_gb = gpu_memory_gb - required_memory_gb
    
    available_ratio = available_memory_gb / gpu_memory_gb
    
    if available_ratio < 0.15:
        params = {
            "max_num_seqs": 32,
            "gpu_memory_utilization": 0.80,
            "max_model_len": 8192,
            "max_num_batched_tokens": 4096,
            "enable_chunked_prefill": True,
        }
    elif available_ratio < 0.25:
        params = {
            "max_num_seqs": 64,
            "gpu_memory_utilization": 0.85,
            "max_model_len": 16384,
            "max_num_batched_tokens": 8192,
            "enable_chunked_prefill": True,
        }
    elif available_ratio < 0.40:
        params = {
            "max_num_seqs": 128,
            "gpu_memory_utilization": 0.88,
            "max_model_len": 32768,
            "max_num_batched_tokens": 16384,
            "enable_chunked_prefill": True,
        }
    elif available_ratio < 0.60:
        params = {
            "max_num_seqs": 256,
            "gpu_memory_utilization": 0.90,
            "max_model_len": 40960,
            "max_num_batched_tokens": 16384,
            "enable_chunked_prefill": True,
        }
    else:
        params = {
            "max_num_seqs": 512,
            "gpu_memory_utilization": 0.92,
            "max_model_len": 65536,
            "max_num_batched_tokens": 32768,
            "enable_chunked_prefill": True,
        }
    
    if "31b" in model_name.lower() or "35b" in model_name.lower():
        params["max_num_seqs"] = min(params["max_num_seqs"], 256)
        params["max_model_len"] = min(params["max_model_len"], 40960)
    elif "70b" in model_name.lower() or "72b" in model_name.lower():
        params["max_num_seqs"] = min(params["max_num_seqs"], 64)
        params["gpu_memory_utilization"] = min(params["gpu_memory_utilization"], 0.85)
        params["max_model_len"] = min(params["max_model_len"], 16384)
    elif "103b" in model_name.lower():
        params["max_num_seqs"] = min(params["max_num_seqs"], 32)
        params["gpu_memory_utilization"] = min(params["gpu_memory_utilization"], 0.80)
        params["max_model_len"] = min(params["max_model_len"], 8192)
    elif "235b" in model_name.lower():
        params["max_num_seqs"] = min(params["max_num_seqs"], 32)
        params["gpu_memory_utilization"] = min(params["gpu_memory_utilization"], 0.75)
        params["max_model_len"] = min(params["max_model_len"], 8192)
    
    return params


def save_model_vllm_params(model_name: str, vllm_params: Dict[str, Any]) -> bool:
    """
    保存模型的 vLLM 参数配置到 config.yaml
    """
    try:
        import yaml
        
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        if not os.path.exists(config_path):
            return False
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if 'models' not in config:
            config['models'] = {}
        
        if model_name not in config['models']:
            config['models'][model_name] = {}
        
        config['models'][model_name]['vllm_params'] = vllm_params
        
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        cache_service.delete("ai_controller:cache:model_list:aggregated")
        logger.info("Saved vLLM params for model %s", model_name)
        return True
    except Exception as exc:
        logger.error("Failed to save vLLM params for %s: %s", model_name, exc)
        return False


def get_model_vllm_params(model_name: str) -> Dict[str, Any]:
    """
    获取模型的 vLLM 参数配置
    """
    try:
        import yaml
        
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        if not os.path.exists(config_path):
            return {}
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        model_config = config.get('models', {}).get(model_name, {})
        vllm_params = model_config.get('vllm_params', {})
        
        if not vllm_params:
            required_memory_gb = 40
            for pattern, info in MODEL_MEMORY_ESTIMATES.items():
                if pattern.lower() in model_name.lower():
                    required_memory_gb = info["vram_gb"]
                    break
            vllm_params = _recommend_vllm_params(model_name, required_memory_gb)
        
        return vllm_params
    except Exception as exc:
        logger.error("Failed to get vLLM params for %s: %s", model_name, exc)
        return {}


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
    优先级：systemd 当前生效环境变量 > runtime override > 状态文件 > service 文件 > 启动脚本
    systemd 环境变量最权威，因为它反映了服务实际启动时使用的配置（含 override），
    状态文件可能因写入失败或进程崩溃而过期。
    """
    try:
        import re

        model_path = None

        # 1. 最高优先级：systemd 当前生效的环境变量（含 runtime override）
        try:
            result = subprocess.run(
                [SYSTEMCTL_BIN, 'show', VLLM_SERVICE_NAME, '--property=Environment', '--value'],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                match = re.search(r'VLLM_MODEL_PATH=([^\s"]+)', result.stdout)
                if match:
                    candidate = match.group(1)
                    if candidate and os.path.exists(candidate):
                        model_path = candidate
        except Exception as exc:
            logger.debug("Failed to read effective systemd environment: %s", exc)

        # 2. 读取 runtime override 文件（/run/systemd/system/...）
        if not model_path:
            override_file = f"/run/systemd/system/{VLLM_SERVICE_NAME}.service.d/override.conf"
            if os.path.exists(override_file):
                try:
                    with open(override_file, 'r') as f:
                        content = f.read()
                    match = re.search(r'VLLM_MODEL_PATH=([^\s"]+)', content)
                    if match:
                        candidate = match.group(1).strip('"').strip("'")
                        if candidate and os.path.exists(candidate):
                            model_path = candidate
                except Exception as exc:
                    logger.debug("Failed to read runtime override: %s", exc)

        # 3. 读取状态文件（可能过期，作为回退）
        if not model_path and os.path.exists(VLLM_MODEL_STATE_FILE):
            with open(VLLM_MODEL_STATE_FILE, 'r') as f:
                state_model_path = f.read().strip()
            if state_model_path and os.path.exists(state_model_path):
                model_path = state_model_path

        # 4. 回退到持久化 service 文件
        service_file = f"/etc/systemd/system/{VLLM_SERVICE_NAME}.service"
        if not model_path and os.path.exists(service_file):
            with open(service_file, 'r') as f:
                content = f.read()
            match = re.search(r'Environment="VLLM_MODEL_PATH=([^"]*)"', content)
            if match:
                candidate = match.group(1)
                if os.path.exists(candidate):
                    model_path = candidate
        
        # 5. 从启动脚本读取
        if not model_path and os.path.exists(VLLM_START_SCRIPT):
            with open(VLLM_START_SCRIPT, 'r') as f:
                content = f.read()
            
            for line in content.split('\n'):
                if 'vllm serve' in line and not line.strip().startswith('#'):
                    parts = line.strip().split()
                    for i, part in enumerate(parts):
                        if part == 'serve' and i + 1 < len(parts):
                            candidate = parts[i + 1].strip('"').strip("'")
                            if candidate.startswith('$'):
                                var_name = candidate.lstrip('$').strip('{}')
                                candidate = os.environ.get(var_name, '')
                                if not candidate:
                                    for env_line in content.split('\n'):
                                        if 'MODEL_PATH=' in env_line and ':-' in env_line:
                                            match = re.search(r':-([^}]+)\}', env_line)
                                            if match:
                                                candidate = match.group(1).strip('"').strip("'")
                                                break
                            
                            if candidate and os.path.exists(candidate):
                                model_path = candidate
                            break
                    
                    if model_path:
                        break

        if not model_path:
            return None

        service_running = _is_service_running()
        config_model_name = _find_model_name_from_path(model_path)
        vllm_port = discover_vllm_port()
        
        result_name = config_model_name or os.path.basename(model_path)
        logger.info("Current model detected: %s (path=%s, running=%s)", result_name, model_path, service_running)
        
        return {
            "name": result_name,
            "path": model_path,
            "service": VLLM_SERVICE_NAME,
            "port": vllm_port,
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
        script_updated = _update_vllm_script(model_path, model_name)
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


async def _wait_for_vllm_ready(max_wait: int = 600, check_interval: int = 5) -> bool:
    """
    等待 vLLM 服务就绪（动态端口发现 + 健康检查）
    :param max_wait: 最大等待时间（秒），默认600秒以适应大模型加载
    :param check_interval: 检查间隔（秒）
    :return: 是否就绪
    """
    start_time = time.time()
    attempt_count = 0
    while (time.time() - start_time) < max_wait:
        attempt_count += 1
        elapsed = int(time.time() - start_time)
        # 每次循环都动态发现端口（因为端口可能会变化）
        vllm_port = discover_vllm_port()
        health_url = _build_vllm_health_url(vllm_port)
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(health_url)
                if response.status_code == 200:
                    logger.info("vLLM service ready after %d seconds (port=%d, attempts=%d)", elapsed, vllm_port, attempt_count)
                    return True
        except Exception:
            pass
        
        logger.info("waiting for vLLM readiness... (elapsed=%ds, remaining=%ds, attempt=%d)", 
                     elapsed, max_wait - elapsed, attempt_count)
        await asyncio.sleep(check_interval)
    
    elapsed = int(time.time() - start_time)
    logger.warning("vLLM service not ready after %d seconds (attempts=%d)", elapsed, attempt_count)
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

    script_updated = _update_vllm_script(model_path, model_name)
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
    """Write a runtime override to /run/systemd so model switching works even when /etc is read-only.
    /run is always writable (tmpfs), while /etc may be read-only on some systems.
    """
    try:
        override_dir = f"/run/systemd/system/{VLLM_SERVICE_NAME}.service.d"
        override_file = os.path.join(override_dir, "override.conf")
        os.makedirs(override_dir, exist_ok=True)
        with open(override_file, 'w') as f:
            f.write('[Service]\n')
            f.write(f'Environment="VLLM_MODEL_PATH={model_path}"\n')
        result = subprocess.run([SYSTEMCTL_BIN, 'daemon-reload'], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            logger.warning("daemon-reload failed after override: %s", (result.stderr or '').strip())
            return False
        logger.info("Updated runtime service override: %s", model_path)
        return True
    except Exception as exc:
        logger.warning("Failed to write runtime service override: %s", exc)
        return False


def _cleanup_runtime_override() -> bool:
    """Remove the runtime override file and reload systemd to prevent stale overrides."""
    try:
        override_dir = f"/run/systemd/system/{VLLM_SERVICE_NAME}.service.d"
        override_file = os.path.join(override_dir, "override.conf")
        if os.path.exists(override_file):
            os.remove(override_file)
            logger.info("Removed runtime service override file")
            result = subprocess.run([SYSTEMCTL_BIN, 'daemon-reload'], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.warning("daemon-reload failed after cleanup: %s", (result.stderr or '').strip())
                return False
        return True
    except Exception as exc:
        logger.warning("Failed to cleanup runtime override: %s", exc)
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


def _write_vllm_params_file(model_name: str) -> bool:
    """
    根据模型名称从 config.yaml 读取 vLLM 参数并写入参数文件
    供启动脚本读取使用
    """
    try:
        params_file = os.path.join(os.path.dirname(VLLM_START_SCRIPT), '.vllm_model_params.json')
        
        vllm_params = get_model_vllm_params(model_name)
        
        if not vllm_params:
            required_memory_gb = 40
            for pattern, info in MODEL_MEMORY_ESTIMATES.items():
                if pattern.lower() in model_name.lower():
                    required_memory_gb = info["vram_gb"]
                    break
            vllm_params = _recommend_vllm_params(model_name, required_memory_gb)
        
        import json
        params_dir = os.path.dirname(params_file)
        if params_dir:
            os.makedirs(params_dir, exist_ok=True)
        
        with open(params_file, 'w') as f:
            json.dump(vllm_params, f, indent=2)
        
        logger.info("Wrote vLLM params file for model %s: %s", model_name, params_file)
        return True
    except Exception as exc:
        logger.warning("Failed to write vLLM params file for %s: %s", model_name, exc)
        return False


def _update_vllm_script(model_path: str, model_name: str = None) -> bool:
    """
    更新 vLLM 模型配置
    通过 systemd runtime override 设置环境变量来切换模型，不修改启动脚本
    同时更新状态文件和参数文件，确保即使 runtime override 失败，
    get_current_model_info() 也能通过其他优先级获取正确的模型路径
    """
    try:
        if not model_name:
            model_name = _find_model_name_from_path(model_path)
            if not model_name:
                model_name = os.path.basename(model_path)
        
        params_written = _write_vllm_params_file(model_name)
        if params_written:
            logger.info("Wrote vLLM params for model: %s", model_name)

        state_updated = _write_model_state_file(model_path)
        if not state_updated:
            logger.warning("Failed to update model state file, but continuing with runtime override")

        runtime_updated = _write_runtime_service_override(model_path)

        if not runtime_updated:
            logger.warning("Runtime service override failed, attempting systemctl set-environment as fallback")
            try:
                result = subprocess.run(
                    [SYSTEMCTL_BIN, 'set-environment',
                     f'VLLM_MODEL_PATH={model_path}'],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    logger.info("Fallback: set-environment succeeded for %s", model_path)
                    runtime_updated = True
                else:
                    logger.warning("Fallback set-environment also failed: %s", result.stderr)
            except Exception as fallback_exc:
                logger.warning("Fallback set-environment exception: %s", fallback_exc)

        if not runtime_updated:
            logger.error("All methods to update model path failed, but state file and params file were updated")

        return runtime_updated or state_updated
    except Exception as e:
        logger.error("Failed to update vLLM config: %s", e)
        return False


async def _test_vllm_model(model_name: str, max_retries: int = 5, retry_delay: int = 10) -> Dict[str, Any]:
    """
    自测 vLLM 模型是否可用
    :param model_name: 模型名称
    :param max_retries: 最大重试次数
    :param retry_delay: 重试间隔（秒）
    :return: 自测结果字典
    """
    vllm_port = discover_vllm_port()
    vllm_url = f"{_build_vllm_base_url(vllm_port)}/v1/chat/completions"

    model_path = os.path.join(MODEL_BASE_PATH, model_name)

    for attempt in range(max_retries):
        for model_id in [model_path, model_name]:
            test_payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": "Hello, please respond with a brief message."}],
                "max_tokens": 10,
                "temperature": 0.7
            }
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(vllm_url, json=test_payload, timeout=30)

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
                                    "token_count": result.get("usage", {}).get("completion_tokens", 0),
                                    "matched_model_id": model_id,
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
                    elif response.status_code == 404:
                        continue
                    else:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            break
                        return {
                            "success": False,
                            "message": f"vLLM returned HTTP error {response.status_code}",
                            "attempt": attempt + 1,
                            "error": response.text[:200] if response.text else "Unknown error"
                        }
            except httpx.HTTPError as e:
                pass
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                pass

        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)
            continue
        return {
            "success": False,
            "message": f"Model test failed after {max_retries} retries",
            "attempt": max_retries,
            "error": f"Neither model_name={model_name} nor model_path={model_path} was accepted by vLLM"
        }
