#!/bin/bash
# Iris - unified voice assistant server
# Starts the server with STT + TTS, handles PTT via CapsLock

# Resolve symlinks to get the real script location
SCRIPT_PATH="$(readlink -f "$0")"
IRIS_DIR="$(dirname "$SCRIPT_PATH")"

# PID and log file locations
PID_FILE="/tmp/iris.pid"
LOG_FILE="$HOME/.local/share/iris/logs.txt"
mkdir -p "$(dirname "$LOG_FILE")"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Iris is already running (PID: $PID)"
        echo "Use 'iris stop' to stop it, or 'iris logs' to view logs"
        exit 0
    fi
fi

# Handle commands
case "${1:-start}" in
    stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            kill "$PID" 2>/dev/null && echo "Iris stopped" || echo "Iris not running"
            rm -f "$PID_FILE"
        else
            echo "Iris not running"
        fi
        exit 0
        ;;
    logs)
        tail -f "$LOG_FILE"
        exit 0
        ;;
    status)
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "Iris is running (PID: $(cat "$PID_FILE"))"
        else
            echo "Iris is not running"
        fi
        exit 0
        ;;
    start|"")
        # Continue to start
        ;;
    *)
        echo "Usage: iris [start|stop|logs|status]"
        exit 1
        ;;
esac

# Start in background
echo "Starting Iris..."
cd "$IRIS_DIR"

echo "" >> "$LOG_FILE"
echo "=== Iris started at $(date) ===" >> "$LOG_FILE"

nohup .venv/bin/python -m iris.server >> "$LOG_FILE" 2>&1 &

echo "Iris running in background (PID: $!)"
echo "Use 'iris logs' to view logs, 'iris stop' to stop"
