#!/bin/bash
# Usage: ./listen.sh [audio_file]
# Records audio (or uses provided file) and sends to Iris server for transcription

cd "$(dirname "$0")"

SERVER="http://127.0.0.1:8765"

if [ -n "$1" ]; then
    # Use provided audio file
    curl -s -X POST "$SERVER/listen" -F "audio=@$1" | jq -r '.text'
else
    # Record until Enter is pressed
    TMPFILE=$(mktemp --suffix=.wav)
    trap "rm -f $TMPFILE" EXIT

    echo "Recording... Press Enter to stop" >&2
    # Record in background
    arecord -f cd -t wav -q "$TMPFILE" &
    PID=$!
    read -r
    kill $PID 2>/dev/null
    wait $PID 2>/dev/null

    curl -s -X POST "$SERVER/listen" -F "audio=@$TMPFILE" | jq -r '.text'
fi
