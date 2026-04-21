#!/usr/bin/env python3
"""
vLLM 模型切换脚本 (AIClient)
- 列出可用模型
- 切换 vLLM 服务运行的模型
- 通过 systemctl 管理服务
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

SCRIPTS_DIR = Path(__file__).parent.resolve()
AI_SUITE_DIR = Path("/root/ai-suite")
MODEL_BASE = "/mnt/pve_models"
VLLM_SERVICE = "vllm-aiclient"


def get_available_models():
    """列出可用模型"""
    models_path = Path(MODEL_BASE)
    if not models_path.exists():
        print(f"错误: 模型目录不存在 {MODEL_BASE}")
        return []
    
    models = []
    for item in sorted(models_path.iterdir()):
        if item.is_dir() and item.name not in ['hf_cache', 'trans_pkg', 'venv', '__pycache__']:
            models.append(item.name)
    return models


def get_current_model():
    """获取当前运行的模型"""
    try:
        result = subprocess.run(
            ['systemctl', 'show', VLLM_SERVICE, '--property=Environment', '--value'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for env in result.stdout.split():
                if env.startswith('VLLM_MODEL_PATH='):
                    return env.split('=', 1)[1]
    except:
        pass
    
    # 尝试从启动脚本读取
    start_script = AI_SUITE_DIR / "start_vllm_aiclient.sh"
    if start_script.exists():
        try:
            content = start_script.read_text()
            for line in content.split('\n'):
                if 'MODEL_PATH="${VLLM_MODEL_PATH:-' in line:
                    start = line.find(':-') + 2
                    end = line.rfind('}"')
                    if start > 1 and end > start:
                        return line[start:end]
        except:
            pass
    return None


def get_service_status():
    """获取服务状态"""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', VLLM_SERVICE],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except:
        return "unknown"


def switch_model(model_name: str, restart: bool = True):
    """切换模型"""
    model_path = f"{MODEL_BASE}/{model_name}"
    
    if not Path(model_path).exists():
        print(f"❌ 模型不存在: {model_path}")
        return False
    
    print(f"🔄 切换模型到: {model_name}")
    print(f"   路径: {model_path}")
    
    try:
        subprocess.run([
            'systemctl', 'set-environment',
            f'VLLM_MODEL_PATH={model_path}'
        ], check=True)
        
        if restart:
            print("   重启服务...")
            subprocess.run(['systemctl', 'restart', VLLM_SERVICE], check=True)
        
        print(f"✓ 模型切换完成: {model_name}")
        print(f"   查看日志: journalctl -u {VLLM_SERVICE} -f")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 切换失败: {e}")
        return False


def watch_logs():
    """实时查看日志"""
    os.execvp('journalctl', ['journalctl', '-u', VLLM_SERVICE, '-f'])


def main():
    parser = argparse.ArgumentParser(
        description='vLLM 模型切换工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --list                    # 列出可用模型
  %(prog)s Gemma-4-31B-Abliterated   # 切换到指定模型
  %(prog)s Qwen2.5-72B --no-restart  # 切换模型但不重启服务
  %(prog)s --logs                    # 查看实时日志
  %(prog)s --status                  # 查看服务状态
        """
    )
    parser.add_argument('model', nargs='?', help='要切换的模型名称')
    parser.add_argument('--list', '-l', action='store_true', help='列出可用模型')
    parser.add_argument('--status', '-s', action='store_true', help='查看服务状态')
    parser.add_argument('--logs', action='store_true', help='查看实时日志')
    parser.add_argument('--no-restart', action='store_true', help='切换模型但不重启服务')
    
    args = parser.parse_args()
    
    if args.list:
        models = get_available_models()
        if not models:
            print("未找到可用模型")
            return 1
        print("可用模型:")
        current = get_current_model()
        for m in models:
            prefix = "* " if current and m in current else "  "
            print(f"{prefix}{m}")
        return 0
    
    if args.status:
        status = get_service_status()
        current = get_current_model()
        print(f"服务名称: {VLLM_SERVICE}")
        print(f"服务状态: {status}")
        print(f"当前模型: {current or '未知'}")
        print(f"安装目录: {AI_SUITE_DIR}")
        return 0
    
    if args.logs:
        watch_logs()
        return 0
    
    if args.model:
        return 0 if switch_model(args.model, restart=not args.no_restart) else 1
    
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
