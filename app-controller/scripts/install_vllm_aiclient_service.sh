#!/bin/bash
# vLLM 服务安装脚本

set -e

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPTS_DIR")"
ROOT_DIR="$(dirname "$PROJECT_DIR")"
INSTALL_DIR="/root/ai-suite"
SYSTEMD_DIR="/etc/systemd/system"

SERVICE_NAME="vllm-aiclient"

echo "=== vLLM AIClient 服务安装 ==="
echo "项目目录: $PROJECT_DIR"
echo "安装目录: $INSTALL_DIR"
echo "服务名称: $SERVICE_NAME"
echo ""

# 1. 创建安装目录
echo "[1/4] 创建安装目录..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"

# 2. 复制脚本文件
echo "[2/4] 复制脚本文件..."
cp "$SCRIPTS_DIR/start_vllm_aiclient.sh" "$INSTALL_DIR/"
cp "$SCRIPTS_DIR/switch_vllm_model_aiclient.py" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/start_vllm_aiclient.sh"
chmod +x "$INSTALL_DIR/switch_vllm_model_aiclient.py"

# 3. 安装 systemd 服务
echo "[3/4] 安装 systemd 服务..."
cp "$ROOT_DIR/systemd/vllm-aiclient.service" "$SYSTEMD_DIR/vllm-aiclient.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# 4. 提示虚拟环境
echo "[4/4] 检查虚拟环境..."
if [ ! -d "$INSTALL_DIR/vllm_env" ]; then
    echo ""
    echo "⚠️  虚拟环境不存在: $INSTALL_DIR/vllm_env"
    echo "请先创建虚拟环境:"
    echo "  python3 -m venv $INSTALL_DIR/vllm_env"
    echo "  source $INSTALL_DIR/vllm_env/bin/activate"
    echo "  pip install vllm"
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "安装目录: $INSTALL_DIR"
echo "服务名称: $SERVICE_NAME"
echo ""
echo "使用方法:"
echo "  启动服务:   systemctl start $SERVICE_NAME"
echo "  停止服务:   systemctl stop $SERVICE_NAME"
echo "  重启服务:   systemctl restart $SERVICE_NAME"
echo "  查看状态:   systemctl status $SERVICE_NAME"
echo "  查看日志:   journalctl -u $SERVICE_NAME -f"
echo ""
echo "切换模型:"
echo "  python3 $INSTALL_DIR/switch_vllm_model_aiclient.py --list"
echo "  python3 $INSTALL_DIR/switch_vllm_model_aiclient.py Gemma-4-31B-Abliterated"
echo ""
