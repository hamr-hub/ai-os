#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
REDIS_PORT=${REDIS_PORT:-6379}
CONTROLLER_PORT=${CONTROLLER_PORT:-35000}
GO_PORT=${GO_PORT:-35001}
AICLIENT_PORT=${AICLIENT_PORT:-3000}
FRONTEND_PORT=${FRONTEND_PORT:-30000}
USE_DOCKER=${USE_DOCKER:-auto}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    echo "AI OS Platform Startup Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -d, --docker        Force using Docker Compose"
    echo "  -n, --native        Force native mode (Python + Node.js)"
    echo "  --redis-port PORT   Set Redis port (default: 6379)"
    echo "  --controller-port PORT  Set AI Controller port (default: 35000)"
    echo "  --go-port PORT          Set Go VLLM API port (default: 35001)"
    echo "  --aiclient-port PORT    Set AIClient-2-API port (default: 3000)"
    echo "  --frontend-port PORT    Set Frontend port (default: 30000)"
    echo "  --stop              Stop all running services"
    echo "  --status            Show status of services"
    echo "  --restart           Restart all services"
    echo ""
    echo "Environment Variables:"
    echo "  USE_DOCKER=auto|true|false   Override Docker detection"
    echo "  REDIS_URL=redis://...        Redis connection URL"
    echo ""
}

show_status() {
    echo ""
    echo "=== Service Status ==="
    
    # Check Redis
    if command -v redis-cli &> /dev/null && redis-cli -p $REDIS_PORT ping &> /dev/null; then
        log_success "Redis: running on port $REDIS_PORT"
    else
        log_error "Redis: not running"
    fi
    
    # Check AI Controller
    if curl -s http://localhost:$CONTROLLER_PORT/health > /dev/null 2>&1; then
        log_success "AI Controller: running on http://localhost:$CONTROLLER_PORT"
    else
        log_error "AI Controller: not running"
    fi
    
    # Check AIClient-2-API
    if curl -s http://localhost:$AICLIENT_PORT > /dev/null 2>&1; then
        log_success "AIClient-2-API: running on http://localhost:$AICLIENT_PORT"
    else
        log_error "AIClient-2-API: not running"
    fi
    
    # Check Frontend
    if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
        log_success "Frontend: running on http://localhost:$FRONTEND_PORT"
    else
        log_error "Frontend: not running"
    fi
    
    echo ""
}

stop_services() {
    echo ""
    echo "=== Stopping Services ==="
    
    if [ -f "$SCRIPT_DIR/docker-compose.yml" ] && command -v docker-compose &> /dev/null; then
        log_info "Stopping Docker services..."
        docker-compose down
        log_success "Docker services stopped"
    fi
    
    # Kill any orphan Python/Node processes
    pkill -f "python.*main.py" 2>/dev/null || true
    pkill -f "npm.*start" 2>/dev/null || true
    
    log_success "All services stopped"
}

restart_services() {
    stop_services
    sleep 2
    main "$@"
}

detect_docker_mode() {
    if [ "$USE_DOCKER" = "true" ]; then
        return 0
    elif [ "$USE_DOCKER" = "false" ]; then
        return 1
    fi
    
    # Auto detection
    if command -v docker-compose &> /dev/null && [ -f "$SCRIPT_DIR/docker-compose.yml" ]; then
        # Check if nvidia-docker is available for GPU support
        if docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
            return 0
        fi
    fi
    return 1
}

start_docker_mode() {
    echo ""
    echo "=== Starting with Docker Compose ==="
    
    # Check Docker availability
    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose not found. Please install Docker and Docker Compose."
        exit 1
    fi
    
    # Check nvidia-docker for GPU
    if ! docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
        log_warning "nvidia-docker not properly configured. GPU features may not work."
    fi
    
    # Start services
    log_info "Starting all services..."
    docker-compose up -d
    
    # Wait for services to start
    log_info "Waiting for services to initialize..."
    
    # Wait for Redis
    local retries=10
    while [ $retries -gt 0 ]; do
        if docker exec ai-os-redis redis-cli ping &> /dev/null; then
            log_success "Redis is ready"
            break
        fi
        sleep 2
        retries=$((retries - 1))
    done
    
    # Wait for AI Controller
    retries=30
    while [ $retries -gt 0 ]; do
        if curl -s http://localhost:$CONTROLLER_PORT/health > /dev/null; then
            log_success "AI Controller is ready"
            break
        fi
        sleep 2
        retries=$((retries - 1))
    done
    
    # Wait for AIClient-2-API
    retries=30
    while [ $retries -gt 0 ]; do
        if curl -s http://localhost:$AICLIENT_PORT > /dev/null; then
            log_success "AIClient-2-API is ready"
            break
        fi
        sleep 2
        retries=$((retries - 1))
    done
    
    # Wait for Frontend
    retries=15
    while [ $retries -gt 0 ]; do
        if curl -s http://localhost:$FRONTEND_PORT > /dev/null; then
            log_success "Frontend is ready"
            break
        fi
        sleep 2
        retries=$((retries - 1))
    done
    
    show_summary
}

start_native_mode() {
    echo ""
    echo "=== Starting in Native Mode ==="
    
    # Check Redis
    echo ""
    log_info "1. Checking Redis..."
    if ! command -v redis-cli &> /dev/null; then
        log_error "Redis not found. Please install Redis first."
        exit 1
    fi
    
    if ! redis-cli -p $REDIS_PORT ping &> /dev/null; then
        log_info "Starting Redis server..."
        redis-server --port $REDIS_PORT --daemonize yes
        sleep 2
    fi
    log_success "Redis is running on port $REDIS_PORT"
    
    # Start AI Controller
    echo ""
    log_info "2. Starting AI Controller..."
    
    if [ ! -d "./app-controller/.venv" ]; then
        log_info "Setting up virtual environment..."
        cd app-controller
        ./setup.sh
        cd ..
    fi
    
    source ./app-controller/.venv/bin/activate
    cd app-controller
    nohup python main.py > logs/controller.log 2>&1 &
    CONTROLLER_PID=$!
    cd ..
    
    # Wait for controller
    local retries=20
    while [ $retries -gt 0 ]; do
        if curl -s http://localhost:$CONTROLLER_PORT/health > /dev/null; then
            log_success "AI Controller started (PID: $CONTROLLER_PID)"
            break
        fi
        sleep 1
        retries=$((retries - 1))
    done
    
    # Start AIClient-2-API
    echo ""
    log_info "3. Starting AIClient-2-API..."
    cd aiclient2api
    if [ ! -d "node_modules" ]; then
        log_info "Installing dependencies..."
        npm install --production
    fi
    nohup npm start > ../logs/aiclient.log 2>&1 &
    CLIENT_PID=$!
    cd ..
    
    # Wait for AIClient
    retries=30
    while [ $retries -gt 0 ]; do
        if curl -s http://localhost:$AICLIENT_PORT > /dev/null; then
            log_success "AIClient-2-API started (PID: $CLIENT_PID)"
            break
        fi
        sleep 1
        retries=$((retries - 1))
    done
    
    show_summary
    
    # Save PIDs for stopping
    echo "$CONTROLLER_PID" > /tmp/ai-os-controller.pid
    echo "$CLIENT_PID" > /tmp/ai-os-aiclient.pid
    
    echo ""
    echo "Press Ctrl+C to stop all services"
    trap "echo 'Stopping services...'; kill $CONTROLLER_PID $CLIENT_PID 2>/dev/null || true; exit 0" INT
    wait
}

show_summary() {
    echo ""
    echo "=== AI OS Platform Started Successfully ==="
    echo ""
    echo "Services:"
    echo "  ${GREEN}Redis${NC}:           localhost:$REDIS_PORT"
    echo "  ${GREEN}AI Controller${NC}:   http://localhost:$CONTROLLER_PORT"
    echo "  ${GREEN}Go VLLM API${NC}:     http://localhost:$GO_PORT"
    echo "  ${GREEN}AIClient-2-API${NC}:  http://localhost:$AICLIENT_PORT"
    echo "  ${GREEN}Frontend${NC}:        http://localhost:$FRONTEND_PORT"
    echo ""
    echo "API Endpoints:"
    echo "  - ${BLUE}/v1/chat/completions${NC}  - Chat completion API"
    echo "  - ${BLUE}/v1/models${NC}           - Model list (for health checks)"
    echo "  - ${BLUE}/manage/gpu${NC}          - GPU monitoring"
    echo "  - ${BLUE}/manage/models${NC}       - Model management"
    echo "  - ${BLUE}/health${NC}              - Health check"
    echo ""
    echo "Configuration:"
    echo "  - Config file: $SCRIPT_DIR/config.yaml"
    echo "  - Logs: $SCRIPT_DIR/app-controller/logs/"
    echo ""
}

main() {
    echo -e "${GREEN}=== AI OS Platform Startup ===${NC}"
    echo ""
    echo "Date: $(date)"
    echo "Directory: $SCRIPT_DIR"
    echo ""
    
    # Parse command line options
    while [[ "$#" -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -d|--docker)
                USE_DOCKER="true"
                ;;
            -n|--native)
                USE_DOCKER="false"
                ;;
            --redis-port)
                REDIS_PORT="$2"
                shift
                ;;
            --controller-port)
                CONTROLLER_PORT="$2"
                shift
                ;;
            --go-port)
                GO_PORT="$2"
                shift
                ;;
            --aiclient-port)
                AICLIENT_PORT="$2"
                shift
                ;;
            --frontend-port)
                FRONTEND_PORT="$2"
                shift
                ;;
            --stop)
                stop_services
                exit 0
                ;;
            --status)
                show_status
                exit 0
                ;;
            --restart)
                restart_services
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
        shift
    done
    
    # Check config file
    if [ ! -f "$SCRIPT_DIR/config.yaml" ]; then
        log_error "Config file not found: $SCRIPT_DIR/config.yaml"
        log_info "Please create a config.yaml file before starting."
        exit 1
    fi
    
    # Check models directory
    if [ ! -d "/mnt/pve_models" ]; then
        log_warning "Models directory not found: /mnt/pve_models"
        log_info "Some models may not be available."
    fi
    
    # Decide mode
    if detect_docker_mode; then
        log_info "Using Docker Compose mode"
        start_docker_mode
    else
        log_info "Using Native mode"
        start_native_mode
    fi
}

main "$@"