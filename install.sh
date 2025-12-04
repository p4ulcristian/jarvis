#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing Jarvis PTT..."

# Install scripts
echo "Copying scripts to /usr/local/bin..."
sudo cp "$SCRIPT_DIR/scripts/jarvis-start" /usr/local/bin/
sudo cp "$SCRIPT_DIR/scripts/jarvis-stop" /usr/local/bin/
sudo chmod +x /usr/local/bin/jarvis-start /usr/local/bin/jarvis-stop

# Configure keyd
echo "Configuring keyd..."
sudo mkdir -p /etc/keyd
sudo cp "$SCRIPT_DIR/config/keyd.conf" /etc/keyd/default.conf
sudo systemctl enable --now keyd
sudo systemctl restart keyd

# Set up user service
echo "Setting up systemd user service..."
mkdir -p ~/.config/systemd/user
cp "$SCRIPT_DIR/config/jarvis.service" ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable jarvis

echo ""
echo "Done! To start Jarvis:"
echo "  systemctl --user start jarvis"
echo ""
echo "Then hold CapsLock and speak!"
