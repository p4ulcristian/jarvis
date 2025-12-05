#!/bin/bash
# Launch Jarvis bubble overlay
# Uses system Python for GTK4 bindings (not in venv)
# LD_PRELOAD fixes layer-shell linking order issue
cd "$(dirname "$0")"
LD_PRELOAD=/usr/lib/libgtk4-layer-shell.so python3 jarvis/bubble.py
