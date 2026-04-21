#!/bin/bash
set -e

echo "=== AI OS Platform Start Script ==="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "1. Checking dependencies..."

# Check Redis
if ! command -v redis-cli &> /dev/null; then
    echo "   Redis not found, starting via docker..."
    docker-compose up -d redis
    sleep 5
else
    if ! redis-cli ping &> /dev/null; then
        echo "   Starting Redis..."
        redis-server --daemonize yes
    else
        echo "   Redis is already running"
    fi
fi

# Check Python controller
echo ""
echo "2. Starting AI Controller..."

if [ -d "./app-controller/.venv" ]; then
    echo "   Activating virtual environment..."
    source ./app-controller/.venv/bin/activate
else
    echo "   Setting up virtual environment..."
    cd app-controller
    ./setup.sh
    cd ..
    source ./app-controller/.venv/bin/activate
fi

# Start controller in background
echo "   Starting FastAPI service..."
python app-controller/main.py &
CONTROLLER_PID=$!
echo "   Controller PID: $CONTROLLER_PID"

# Wait for controller to start
echo "   Waiting for controller to start..."
sleep 3

# Check if controller is running
if ! curl -s http://localhost:5000/health > /dev/null; then
    echo "   ERROR: Failed to start AI Controller"
    kill $CONTROLLER_PID 2>/dev/null || true
    exit 1
fi

echo "   AI Controller started successfully"

# Start AIClient-2-API
echo ""
echo "3. Starting AIClient-2-API..."

if [ -d "./aiclient2api/node_modules" ]; then
    cd aiclient2api
    npm start &
    CLIENT_PID=$!
    echo "   AIClient-2-API PID: $CLIENT_PID"
    cd ..
else
    echo "   Installing AIClient-2-API dependencies..."
    cd aiclient2api
    npm install
    npm start &
    CLIENT_PID=$!
    echo "   AIClient-2-API PID: $CLIENT_PID"
    cd ..
fi

echo ""
echo "=== AI OS Platform Started ==="
echo ""
echo "Services:"
echo "  - AI Controller: http://localhost:5000"
echo "  - AIClient-2-API: http://localhost:3000"
echo "  - Redis: localhost:6379"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for user to stop
trap "echo 'Stopping services...'; kill $CONTROLLER_PID $CLIENT_PID 2>/dev/null || true; exit 0" INT

wait