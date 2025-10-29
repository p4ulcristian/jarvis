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
MISSING_DEPS=0

# Check for essential packages
if ! "$VENV_PYTHON" -c "import textual" &> /dev/null; then
    MISSING_DEPS=1
fi

if ! "$VENV_PYTHON" -c "import evdev" &> /dev/null; then
    MISSING_DEPS=1
fi

if ! "$VENV_PYTHON" -c "import torch" &> /dev/null; then
    MISSING_DEPS=1
fi

if ! "$VENV_PYTHON" -c "import nemo.collections.asr" &> /dev/null; then
    MISSING_DEPS=1
fi

# Install dependencies if any are missing
if [ $MISSING_DEPS -eq 1 ]; then
    echo -e "${YELLOW}Warning: Missing dependencies. Installing...${NC}"

    # Install torch/torchaudio first (CPU version to avoid conflicts)
    if ! "$VENV_PYTHON" -c "import torch" &> /dev/null; then
        echo -e "${YELLOW}Installing PyTorch (CPU version)...${NC}"
        "$VENV_PIP" install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
    fi

    # Install other basic dependencies
    "$VENV_PIP" install textual evdev sounddevice scipy librosa numpy pynput python-dotenv pyyaml requests rich prometheus-client

    # Try to install NeMo (may have conflicts, but will work with already-installed torch)
    "$VENV_PIP" install nemo_toolkit[asr] || echo -e "${YELLOW}Note: Some NeMo dependencies may have version conflicts, but core functionality should work${NC}"
fi

# Run JARVIS (UI starts immediately, all messages appear in UI)
cd "$SCRIPT_DIR/source-code"
exec "$VENV_PYTHON" main.py
