#!/bin/bash
# Usage: ./speak.sh "text to speak"
# Uses local FastPitch + HiFi-GAN via NeMo (no API needed)

cd "$(dirname "$0")"

TEXT="$1"
if [ -z "$TEXT" ]; then
    echo "Usage: ./speak.sh 'text to speak'" >&2
    exit 1
fi

.venv/bin/python -m jarvis.tts "$TEXT"
