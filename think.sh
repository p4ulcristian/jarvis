#!/bin/bash
# think.sh - Sends user command to Claude CLI and gets response
# Usage: ./think.sh "user command"

USER_COMMAND="$1"

if [ -z "$USER_COMMAND" ]; then
  echo "Error: No command provided" >&2
  exit 1
fi

# Send to Claude CLI and capture response
# Using non-interactive mode with --output-format plain for clean text output
RESPONSE=$(echo "$USER_COMMAND" | claude --dangerously-skip-upgrade-check 2>/dev/null)

# Output the response
echo "$RESPONSE"
