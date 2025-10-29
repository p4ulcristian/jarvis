#!/bin/bash
# JARVIS Installation Script
# Installs JARVIS as a systemd service

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}JARVIS Installation Script${NC}"
echo "=================================="

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"
cd "$SCRIPT_DIR"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo -e "${RED}Error: Do not run this script as root${NC}"
   echo "It will use sudo when needed"
   exit 1
fi

# Check system dependencies
echo -e "\n${YELLOW}Checking system dependencies...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Python3 found"

# Check for audio libraries
if ! ldconfig -p | grep -q libportaudio; then
    echo -e "${YELLOW}Warning: portaudio not found. Installing...${NC}"
    sudo pacman -S --needed portaudio || true
fi

if ! command -v mpv &> /dev/null; then
    echo -e "${YELLOW}Warning: mpv not found. Installing for TTS...${NC}"
    sudo pacman -S --needed mpv || true
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "\n${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${GREEN}✓${NC} Virtual environment exists"
fi

# Activate virtual environment and install dependencies
echo -e "\n${YELLOW}Installing Python dependencies...${NC}"
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓${NC} Dependencies installed"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "\n${YELLOW}Creating .env file...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓${NC} .env created"
    echo -e "${YELLOW}Please edit .env and add your OPENAI_API_KEY${NC}"
else
    echo -e "${GREEN}✓${NC} .env exists"
fi

# Create data directories
echo -e "\n${YELLOW}Creating data directories...${NC}"
mkdir -p logs data
echo -e "${GREEN}✓${NC} Directories created"

# Install systemd service (optional)
read -p "Install as systemd service? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}Installing systemd service...${NC}"

    # Update service file with correct paths
    SERVICE_FILE="deploy/jarvis.service"
    TEMP_SERVICE="/tmp/jarvis.service"

    sed "s|/home/paul/Work/jarvis|$SCRIPT_DIR|g" "$SERVICE_FILE" > "$TEMP_SERVICE"
    sed -i "s|User=paul|User=$USER|g" "$TEMP_SERVICE"
    sed -i "s|Group=paul|Group=$USER|g" "$TEMP_SERVICE"

    sudo cp "$TEMP_SERVICE" /etc/systemd/system/jarvis.service
    sudo systemctl daemon-reload

    echo -e "${GREEN}✓${NC} Service installed"
    echo -e "\nTo start JARVIS:"
    echo -e "  sudo systemctl start jarvis"
    echo -e "  sudo systemctl enable jarvis  # Start on boot"
    echo -e "  sudo journalctl -u jarvis -f  # View logs"
fi

echo -e "\n${GREEN}Installation complete!${NC}"
echo -e "\nTo run JARVIS manually:"
echo -e "  source venv/bin/activate"
echo -e "  ./jarvis_v2.py"
echo -e "\nOr use the systemd service (if installed):"
echo -e "  sudo systemctl start jarvis"
