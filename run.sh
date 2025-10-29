#!/bin/bash
# run.sh - Start JARVIS voice assistant

# Check for OPENAI_API_KEY
if [ -z "$OPENAI_API_KEY" ]; then
  echo "Error: OPENAI_API_KEY not set"
  echo "Please run: export OPENAI_API_KEY='your-key-here'"
  exit 1
fi

# Activate venv and run
source venv/bin/activate
python3 hear.py
