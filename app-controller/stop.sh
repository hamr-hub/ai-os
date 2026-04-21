#!/bin/bash

echo "Stopping AI Controller service..."

# Try systemd first
if systemctl is-active --quiet aiclient-python 2>/dev/null; then
    echo "Stopping via systemd..."
    sudo systemctl stop aiclient-python
    echo "Service stopped."
    exit 0
fi

# Fallback: kill process directly
PID=$(pgrep -f "python.*main.py" 2>/dev/null | head -1)
if [ -n "$PID" ]; then
    echo "Killing process $PID..."
    kill "$PID"
    sleep 2
    
    # Check if process is still running
    if kill -0 "$PID" 2>/dev/null; then
        echo "Process did not terminate gracefully, forcing kill..."
        kill -9 "$PID"
    fi
    
    echo "Service stopped."
else
    echo "No running AI Controller process found."
fi
