#!/bin/bash
#
# Backend Switcher Script
# Usage: ./switch_backend.sh [python|go|status]
#

NGINX_CONF="/root/ai-os/nginx.conf"
SYSTEM_NGINX="/etc/nginx/nginx.conf"

get_current_backend() {
    if [ -f "$NGINX_CONF" ]; then
        if grep -q "location /api/manage/ {" "$NGINX_CONF" 2>/dev/null; then
            if grep -A1 "location /api/manage/ {" "$NGINX_CONF" | grep -q "python_backend"; then
                echo "python"
                return
            fi
        fi
        if grep -q "location /api/manage/.*go_backend" "$NGINX_CONF" 2>/dev/null; then
            echo "go"
            return
        fi
    fi
    echo "unknown"
}

switch_to_python() {
    echo "Switching manage API to Python backend (35000)..."
    
    cat > "${NGINX_CONF}.backend" << 'BACKEND_EOF'
        location /api/manage/ {
            proxy_pass http://python_backend/manage/;
BACKEND_EOF
    
    # Use sed to replace the location block
    sed -i '/location \/api\/manage\/ {/{
        N
        c\        location /api/manage/ {\n            proxy_pass http://python_backend/manage/;
    }' "$NGINX_CONF"
    
    cp "$NGINX_CONF" "$SYSTEM_NGINX" 2>/dev/null
    nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null
    
    echo "Manage API now routes to Python backend (35000)"
}

switch_to_go() {
    echo "Switching manage API to Go backend (35001)..."
    
    sed -i '/location \/api\/manage\/ {/{
        N
        c\        location /api/manage/ {\n            proxy_pass http://go_backend/manage/;
    }' "$NGINX_CONF"
    
    cp "$NGINX_CONF" "$SYSTEM_NGINX" 2>/dev/null
    nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null
    
    echo "Manage API now routes to Go backend (35001)"
}

show_status() {
    echo "=== Backend Status ==="
    echo ""
    
    current=$(get_current_backend)
    echo "Active backend: $current"
    echo ""
    
    echo "Services:"
    printf "  %-30s " "Python (35000):"
    systemctl is-active ai-controller &>/dev/null && echo "Running" || echo "Stopped"
    
    printf "  %-30s " "Go (35001):"
    systemctl is-active go-vllm-api &>/dev/null && echo "Running" || echo "Stopped"
    
    printf "  %-30s " "vLLM (8000):"
    systemctl is-active vllm-aiclient &>/dev/null && echo "Running" || echo "Stopped"
    
    printf "  %-30s " "aiclient2api (3000):"
    docker ps --filter name=ai-os-aiclient --format '{{.Status}}' 2>/dev/null | head -1 || echo "Not running"
    
    printf "  %-30s " "Frontend (30000):"
    docker ps --filter name=ai-os-frontend --format '{{.Status}}' 2>/dev/null | head -1 || echo "Not running"
    
    echo ""
    echo "Port 80 (Nginx):"
    ss -tlnp | grep ':80 ' || echo "  Not listening"
}

case "${1}" in
    python)
        switch_to_python
        ;;
    go)
        switch_to_go
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {python|go|status}"
        echo ""
        echo "Switch backend for manage API:"
        echo "  python  - Use Python FastAPI backend (35000)"
        echo "  go      - Use Go Gin backend (35001)"
        echo "  status  - Show current status"
        exit 1
        ;;
esac
