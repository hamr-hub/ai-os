#!/bin/bash

set -euo pipefail

PROJECT_ROOT="/root/ai-os"
VLLM_ENV_PATH="$PROJECT_ROOT/vllm_env"
SGLANG_ENV_PATH="$PROJECT_ROOT/sglang_env"
LLAMACPP_ENV_PATH="$PROJECT_ROOT/llamacpp_env"

REDIS_URL="redis://localhost:6379"
MODEL_BASE_PATH="/mnt/pve_models"

log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
}

log_warn() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" >&2
}

check_prerequisites() {
    log_info "=== 检查前置条件 ==="
    
    if ! command -v python3 &>/dev/null; then
        log_error "Python3 未安装"
        exit 1
    fi
    
    if ! command -v go &>/dev/null; then
        log_error "Go 未安装"
        exit 1
    fi
    
    if ! command -v docker &>/dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi
    
    if ! command -v docker-compose &>/dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi
    
    if ! command -v nvidia-smi &>/dev/null; then
        log_warn "NVIDIA GPU 未检测到，将以CPU模式运行"
    fi
    
    log_info "前置条件检查通过"
}

setup_venv() {
    log_info "=== 设置虚拟环境 ==="
    
    if [ ! -d "$VLLM_ENV_PATH" ]; then
        log_info "创建 vLLM 虚拟环境: $VLLM_ENV_PATH"
        python3 -m venv "$VLLM_ENV_PATH"
    fi
    
    if [ ! -d "$SGLANG_ENV_PATH" ]; then
        log_info "创建 SGLang 虚拟环境: $SGLANG_ENV_PATH"
        python3 -m venv "$SGLANG_ENV_PATH"
    fi
    
    if [ ! -d "$LLAMACPP_ENV_PATH" ]; then
        log_info "创建 llama.cpp 虚拟环境: $LLAMACPP_ENV_PATH"
        python3 -m venv "$LLAMACPP_ENV_PATH"
    fi
    
    log_info "安装 vLLM 依赖"
    source "$VLLM_ENV_PATH/bin/activate"
    pip install --upgrade pip
    pip install vllm torch transformers accelerate sentencepiece protobuf
    
    log_info "安装 SGLang 依赖"
    source "$SGLANG_ENV_PATH/bin/activate"
    pip install --upgrade pip
    pip install sglang torch transformers accelerate
    
    log_info "安装 llama.cpp 依赖"
    source "$LLAMACPP_ENV_PATH/bin/activate"
    pip install --upgrade pip
    pip install llama-cpp-python
    
    deactivate
    log_info "虚拟环境设置完成"
}

setup_redis() {
    log_info "=== 设置 Redis ==="
    
    if ! docker ps --format '{{.Names}}' | grep -q "ai-os-redis"; then
        log_info "启动 Redis 容器"
        docker run -d \
            --name ai-os-redis \
            -p 6379:6379 \
            -v redis_data:/data \
            --restart unless-stopped \
            redis:7.2-alpine
        
        log_info "等待 Redis 启动..."
        sleep 5
    else
        log_info "Redis 容器已运行"
    fi
    
    if redis-cli ping &>/dev/null; then
        log_info "Redis 连接测试通过"
    else
        log_error "Redis 连接失败"
        exit 1
    fi
}

build_go_service() {
    log_info "=== 构建 Go vLLM API 服务 ==="
    
    cd "$PROJECT_ROOT/go-vllm-api"
    
    if [ ! -f "go.mod" ]; then
        log_error "go.mod 不存在"
        exit 1
    fi
    
    log_info "下载 Go 依赖"
    go mod download
    
    log_info "构建 Go 服务"
    go build -o bin/go-vllm-api cmd/server/main.go
    
    if [ -f "bin/go-vllm-api" ]; then
        log_info "Go 服务构建成功"
    else
        log_error "Go 服务构建失败"
        exit 1
    fi
    
    cd "$PROJECT_ROOT"
}

build_python_service() {
    log_info "=== 设置 Python 服务 ==="
    
    cd "$PROJECT_ROOT/app-controller"
    
    if [ ! -f "requirements.txt" ]; then
        log_error "requirements.txt 不存在"
        exit 1
    fi
    
    log_info "安装 Python 依赖"
    pip install -r requirements.txt
    
    log_info "检查配置文件"
    if [ ! -f "config.yaml" ]; then
        log_warn "config.yaml 不存在，将使用默认配置"
    fi
    
    cd "$PROJECT_ROOT"
    log_info "Python 服务设置完成"
}

build_frontend() {
    log_info "=== 构建前端 ==="
    
    cd "$PROJECT_ROOT/frontend"
    
    if [ ! -f "package.json" ]; then
        log_error "package.json 不存在"
        exit 1
    fi
    
    log_info "安装前端依赖"
    if ! command -v pnpm &>/dev/null; then
        log_warn "pnpm 未安装，使用 npm"
        npm install
    else
        pnpm install
    fi
    
    log_info "构建前端"
    if command -v pnpm &>/dev/null; then
        pnpm build
    else
        npm run build
    fi
    
    cd "$PROJECT_ROOT"
    log_info "前端构建完成"
}

start_services() {
    log_info "=== 启动服务 ==="
    
    log_info "启动 Redis..."
    setup_redis
    
    log_info "启动 Go vLLM API 服务 (后台运行)"
    cd "$PROJECT_ROOT/go-vllm-api"
    nohup ./bin/go-vllm-api --port 35001 > logs/go-vllm-api.log 2>&1 &
    GO_PID=$!
    log_info "Go 服务 PID: $GO_PID"
    sleep 3
    
    log_info "启动 Python 控制器服务 (后台运行)"
    cd "$PROJECT_ROOT/app-controller"
    nohup python main.py --port 35000 > logs/app-controller.log 2>&1 &
    PYTHON_PID=$!
    log_info "Python 服务 PID: $PYTHON_PID"
    sleep 5
    
    log_info "启动 vLLM 推理服务 (后台运行)"
    source "$VLLM_ENV_PATH/bin/activate"
    nohup bash "$PROJECT_ROOT/app-controller/scripts/start_vllm_aiclient.sh" > logs/vllm.log 2>&1 &
    VLLM_PID=$!
    log_info "vLLM 服务 PID: $VLLM_PID"
    deactivate
    sleep 10
    
    cd "$PROJECT_ROOT"
}

start_docker_services() {
    log_info "=== 使用 Docker Compose 启动服务 ==="

    log_info "检查并更新 .env 文件"
    if [ ! -f ".env" ]; then
        cp .env.example .env
    fi

    log_info "拉取最新 Docker 镜像"
    docker-compose pull aiclient

    log_info "启动所有服务"
    docker-compose up -d

    log_info "等待服务启动..."
    sleep 15

    log_info "检查服务状态"
    docker-compose ps
}

check_health() {
    log_info "=== 健康检查 ==="
    
    local all_healthy=true
    
    if curl -s http://localhost:35000/health | grep -q "ok"; then
        log_info "✓ Python 控制器服务正常"
    else
        log_error "✗ Python 控制器服务异常"
        all_healthy=false
    fi
    
    if curl -s http://localhost:35001/health | grep -q "ok"; then
        log_info "✓ Go vLLM API 服务正常"
    else
        log_error "✗ Go vLLM API 服务异常"
        all_healthy=false
    fi
    
    if curl -s http://localhost:8000/v1/models | grep -q "model"; then
        log_info "✓ vLLM 推理服务正常"
    else
        log_warn "⚠ vLLM 推理服务可能尚未就绪，正在启动中..."
    fi
    
    if curl -s http://localhost:6379 -X PING | grep -q "PONG"; then
        log_info "✓ Redis 服务正常"
    else
        log_error "✗ Redis 服务异常"
        all_healthy=false
    fi
    
    if [ "$all_healthy" = true ]; then
        log_info "=== 所有服务启动成功 ==="
        log_info "前端: http://localhost:30000"
        log_info "Python API: http://localhost:35000"
        log_info "Go API: http://localhost:35001"
        log_info "vLLM: http://localhost:8000"
    else
        log_error "=== 部分服务启动失败 ==="
        exit 1
    fi
}

stop_services() {
    log_info "=== 停止服务 ==="
    
    log_info "停止 Docker 服务"
    docker-compose down 2>/dev/null || true
    
    log_info "停止后台进程"
    pkill -f "go-vllm-api" 2>/dev/null || true
    pkill -f "python main.py" 2>/dev/null || true
    pkill -f "vllm serve" 2>/dev/null || true
    
    log_info "服务已停止"
}

show_help() {
    echo "AI OS 部署脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --all           执行完整部署（前置检查→虚拟环境→构建→启动→健康检查）"
    echo "  --check         仅检查前置条件"
    echo "  --venv          仅设置虚拟环境"
    echo "  --redis         仅启动 Redis"
    echo "  --build-go      仅构建 Go 服务"
    echo "  --build-python  仅设置 Python 服务"
    echo "  --build-frontend 仅构建前端"
    echo "  --start         启动所有服务（本地模式）"
    echo "  --docker        使用 Docker Compose 启动服务（含拉取最新 aiclient 镜像）"
    echo "  --stop          停止所有服务"
    echo "  --health        执行健康检查"
    echo "  --update-plugin 更新 aiclient 插件（同步插件文件后重启容器）"
    echo "  --help          显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 --all            # 完整部署"
    echo "  $0 --docker         # 使用 Docker 部署（自动拉取最新 aiclient 镜像）"
    echo "  $0 --update-plugin  # 热更新插件代码"
    echo "  $0 --stop           # 停止服务"
}

update_plugin() {
    log_info "=== 更新 aiclient 插件 ==="

    log_info "重启 aiclient 容器以加载最新插件"
    docker-compose restart aiclient

    sleep 5
    log_info "插件更新完成"
}

main() {
    case "${1:-}" in
        --all)
            check_prerequisites
            setup_venv
            setup_redis
            build_go_service
            build_python_service
            build_frontend
            start_docker_services
            check_health
            ;;
        --check)
            check_prerequisites
            ;;
        --venv)
            setup_venv
            ;;
        --redis)
            setup_redis
            ;;
        --build-go)
            build_go_service
            ;;
        --build-python)
            build_python_service
            ;;
        --build-frontend)
            build_frontend
            ;;
        --start)
            start_services
            check_health
            ;;
        --docker)
            check_prerequisites
            start_docker_services
            check_health
            ;;
        --stop)
            stop_services
            ;;
        --health)
            check_health
            ;;
        --update-plugin)
            update_plugin
            ;;
        --help)
            show_help
            ;;
        *)
            show_help
            exit 1
            ;;
    esac
}

main "$@"