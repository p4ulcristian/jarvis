#!/bin/bash
# JARVIS - Voice-to-Text System Startup Script

# Get script directory (resolve symlinks)
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$SCRIPT_DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment exists (silent check - errors show in UI)
if [ ! -d "$SCRIPT_DIR/source-code/venv" ]; then
    echo -e "${RED}Error: Virtual environment not found!${NC}"
    echo "Please run: cd source-code && python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Set venv paths
VENV_PYTHON="$SCRIPT_DIR/source-code/venv/bin/python"
VENV_PIP="$SCRIPT_DIR/source-code/venv/bin/pip"

# Check if required packages are installed (silent - errors show in UI)
if ! "$VENV_PYTHON" -c "import nemo.collections.asr" &> /dev/null; then
    echo -e "${YELLOW}Warning: NeMo not found. Installing dependencies...${NC}"
    "$VENV_PIP" install -r "$SCRIPT_DIR/source-code/requirements.txt"
fi

# Run JARVIS (UI starts immediately, all messages appear in UI)
cd "$SCRIPT_DIR/source-code"
exec "$VENV_PYTHON" main.py
