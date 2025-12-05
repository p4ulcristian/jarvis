#!/bin/bash
# Jarvis - unified voice assistant server
# Starts the server with STT + TTS, handles PTT via keyd signals

cd "$(dirname "$0")"
.venv/bin/python -m jarvis.server
