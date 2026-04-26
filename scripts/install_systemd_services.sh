#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SYSTEMD_DIR="/etc/systemd/system"
ENABLE_SERVICES=false
GO_BINARY_PATH="$PROJECT_ROOT/go-vllm-api/bin/go-vllm-api"

usage() {
    cat <<'EOF'
用法:
  sudo ./scripts/install_systemd_services.sh [--enable]

说明:
  - 同步仓库中的 systemd unit 到 /etc/systemd/system
  - 执行 systemctl daemon-reload
  - 可选执行 enable
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --enable)
            ENABLE_SERVICES=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "未知参数: $1" >&2
            usage
            exit 1
            ;;
    esac
    shift
done

if [[ $EUID -ne 0 ]]; then
    echo "请使用 root 或 sudo 运行此脚本" >&2
    exit 1
fi

mkdir -p "$PROJECT_ROOT/go-vllm-api/bin" "$PROJECT_ROOT/go-vllm-api/logs"

if command -v go >/dev/null 2>&1; then
    echo "构建 Go 服务二进制..."
    (
        cd "$PROJECT_ROOT/go-vllm-api"
        export GOSUMDB="${GOSUMDB:-sum.golang.org}"
        go build -o "$GO_BINARY_PATH" ./cmd/server
    )
else
    if [[ ! -x "$GO_BINARY_PATH" ]]; then
        echo "未找到 go 命令，且缺少已构建二进制: $GO_BINARY_PATH" >&2
        exit 1
    fi
    echo "未检测到 go 命令，复用现有二进制: $GO_BINARY_PATH"
fi

install -D -m 0644 "$PROJECT_ROOT/systemd/ai-controller.service" "$SYSTEMD_DIR/ai-controller.service"
install -D -m 0644 "$PROJECT_ROOT/systemd/go-vllm-api.service" "$SYSTEMD_DIR/go-vllm-api.service"
install -D -m 0644 "$PROJECT_ROOT/systemd/vllm-aiclient.service" "$SYSTEMD_DIR/vllm-aiclient.service"

systemctl daemon-reload

if [[ "$ENABLE_SERVICES" == "true" ]]; then
    systemctl enable ai-controller.service
    systemctl enable go-vllm-api.service
    systemctl enable vllm-aiclient.service
fi

echo "systemd 单元已同步:"
echo "  - $SYSTEMD_DIR/ai-controller.service"
echo "  - $SYSTEMD_DIR/go-vllm-api.service"
echo "  - $SYSTEMD_DIR/vllm-aiclient.service"
echo ""
echo "后续可执行:"
echo "  systemctl restart ai-controller.service"
echo "  systemctl restart go-vllm-api.service"
echo "  systemctl restart vllm-aiclient.service"
