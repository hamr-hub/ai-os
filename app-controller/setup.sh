#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
LOG_DIR="$SCRIPT_DIR/logs"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"

echo "=== AI Controller Setup Script ==="

# Create virtual environment if not exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create logs directory
mkdir -p "$LOG_DIR"

# Check if config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Warning: config.yaml not found. Please create one before starting the service."
    echo "See README.md for configuration example."
    exit 1
fi

# Check if Redis is running (optional)
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo "Redis is running."
    else
        echo "Warning: Redis is not running. Some features may be limited."
    fi
fi

echo ""
echo "=== Setup Complete ==="
echo "To start the service, run:"
echo "  make run"
echo ""
echo "Or start with systemd:"
echo "  sudo cp systemd/ai-controller.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable ai-controller"
echo "  sudo systemctl start ai-controller"
