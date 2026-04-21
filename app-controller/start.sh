#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-5000}

# Check virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Virtual environment not found. Run setup.sh first."
    exit 1
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Check config
if [ ! -f "$SCRIPT_DIR/config.yaml" ]; then
    echo "Error: config.yaml not found. Please create one before starting."
    exit 1
fi

# Create logs directory
mkdir -p "$SCRIPT_DIR/logs"

echo "Starting AI Controller on http://$HOST:$PORT"
echo "Press Ctrl+C to stop"

# Start the application
exec python main.py
