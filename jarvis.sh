#!/bin/bash
# JARVIS - Voice-to-Text System Startup Script

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting JARVIS...${NC}"

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo -e "${RED}Error: Virtual environment not found!${NC}"
    echo "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Check if required packages are installed
if ! python -c "import nemo.collections.asr" &> /dev/null; then
    echo -e "${YELLOW}Warning: NeMo not found. Installing dependencies...${NC}"
    pip install -r "$SCRIPT_DIR/requirements.txt"
fi

# Run JARVIS
cd "$SCRIPT_DIR"
python jarvis.py

# Deactivate virtual environment on exit
deactivate
