#!/bin/bash
# Usage: ./speak.sh "text to speak"
# Sends text to Jarvis server for TTS (server plays audio)

SERVER="http://127.0.0.1:8765"

TEXT="$1"
if [ -z "$TEXT" ]; then
    echo "Usage: ./speak.sh 'text to speak'" >&2
    exit 1
fi

curl -s -X POST "$SERVER/speak" \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"$TEXT\"}"
