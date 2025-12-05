#!/bin/bash
# Usage: ./speak.sh "text to speak" [speed]
# Sends text to Iris server for TTS (server plays audio)

SERVER="http://127.0.0.1:8765"

TEXT="$1"
SPEED="${2:-1.0}"

if [ -z "$TEXT" ]; then
    echo "Usage: ./speak.sh 'text to speak' [speed]" >&2
    exit 1
fi

# Use jq to properly escape the text for JSON
JSON=$(jq -n --arg text "$TEXT" --argjson speed "$SPEED" '{text: $text, speed: $speed}')

curl -s -X POST "$SERVER/speak" \
    -H "Content-Type: application/json" \
    -d "$JSON"
