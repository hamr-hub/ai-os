#!/bin/bash
#
# Deployment Setup Script
# Configures the new unified deployment architecture
#

set -e

PROJECT_ROOT="/root/ai-os"
NGINX_SYSTEM="/etc/nginx"

echo "========================================"
echo "  AI-OS Deployment Setup"
echo "========================================"
echo ""

# 1. Install nginx
echo "[1/5] Installing nginx..."
if ! command -v nginx &>/dev/null; then
    apt-get update && apt-get install -y nginx
    echo "  Nginx installed"
else
    echo "  Nginx already installed"
fi

# 2. Copy nginx configuration
echo "[2/5] Configuring nginx..."
cp "$PROJECT_ROOT/nginx.conf.python" "$NGINX_SYSTEM/nginx.conf"
cp "$PROJECT_ROOT/nginx.conf" "$PROJECT_ROOT/nginx.conf.active"
echo "  Nginx configured (Python backend by default)"

# 3. Setup backend switcher
echo "[3/5] Setting up backend switcher..."
chmod +x "$PROJECT_ROOT/scripts/switch_backend.sh"
ln -sf "$PROJECT_ROOT/scripts/switch_backend.sh" /usr/local/bin/switch-backend 2>/dev/null || true
echo "  Backend switcher installed: switch-backend [python|go|status]"

# 4. Install systemd services
echo "[4/5] Installing systemd services..."
cp "$PROJECT_ROOT/systemd/vllm-aiclient.service" /etc/systemd/system/
cp "$PROJECT_ROOT/systemd/ai-controller.service" /etc/systemd/system/
cp "$PROJECT_ROOT/systemd/go-vllm-api.service" /etc/systemd/system/

systemctl daemon-reload

echo "  Services installed:"
echo "    - vllm-aiclient.service (port 8000)"
echo "    - ai-controller.service (port 35000)"
echo "    - go-vllm-api.service (port 35001)"

# 5. Enable and start services
echo "[5/5] Starting services..."

systemctl enable nginx
systemctl restart nginx
echo "  Nginx started on port 80"

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "Architecture:"
echo "  Port 80   -> Nginx (main entry)"
echo "    /       -> aiclient2api (3000)"
echo "    /manage -> frontend (30000)"
echo "    /api/*  -> Python/Go backend"
echo "    /v1/*   -> Go backend (35001)"
echo ""
echo "  Port 8000 -> vLLM (vllm-aiclient.service)"
echo ""
echo "Commands:"
echo "  switch-backend python   # Use Python backend"
echo "  switch-backend go       # Use Go backend"
echo "  switch-backend status   # Check status"
echo ""
echo "  systemctl start/stop/restart vllm-aiclient"
echo "  systemctl start/stop/restart ai-controller"
echo "  systemctl start/stop/restart go-vllm-api"
echo ""
