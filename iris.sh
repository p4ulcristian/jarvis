#!/bin/bash
# Iris - unified voice assistant server
# Starts the server with STT + TTS, handles PTT via CapsLock

# Resolve symlinks to get the real script location
SCRIPT_PATH="$(readlink -f "$0")"
cd "$(dirname "$SCRIPT_PATH")"

# Log file location
LOG_FILE="$HOME/.local/share/iris/logs.txt"
mkdir -p "$(dirname "$LOG_FILE")"

# Start with timestamp
echo "" >> "$LOG_FILE"
echo "=== Iris started at $(date) ===" >> "$LOG_FILE"

# Run server, logging output
.venv/bin/python -m iris.server 2>&1 | tee -a "$LOG_FILE"
