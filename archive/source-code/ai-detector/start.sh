#!/bin/bash
# Startup script for AI Detection System

cd "$(dirname "$0")"

echo "Starting AI Detection System..."
echo

./venv/bin/python log_watcher.py
