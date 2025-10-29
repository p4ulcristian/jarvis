#!/bin/bash
# Setup script for Type Mode - sets up permissions for keyboard automation

set -e

echo "=========================================="
echo "Jarvis Type Mode Setup"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Don't run this script as root or with sudo"
    echo "   Run it as your normal user: ./setup-type-mode.sh"
    exit 1
fi

echo "1. Loading uinput kernel module..."
if lsmod | grep -q uinput; then
    echo "   ✓ uinput module already loaded"
else
    echo "   Loading uinput module (requires sudo)..."
    sudo modprobe uinput
    echo "   ✓ uinput module loaded"
fi

echo ""
echo "2. Making uinput load on boot..."
if [ -f /etc/modules-load.d/uinput.conf ]; then
    echo "   ✓ uinput already configured to load on boot"
else
    echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf > /dev/null
    echo "   ✓ uinput will load automatically on boot"
fi

echo ""
echo "3. Checking /dev/uinput permissions..."
if [ -e /dev/uinput ]; then
    ls -l /dev/uinput
else
    echo "   ❌ /dev/uinput not found - module may not be loaded"
    exit 1
fi

echo ""
echo "4. Checking user groups..."
if groups | grep -q '\binput\b'; then
    echo "   ✓ You are already in the 'input' group"
else
    echo "   Adding you to the 'input' group (requires sudo)..."
    sudo usermod -a -G input $USER
    echo "   ✓ Added to input group"
    echo ""
    echo "   ⚠️  IMPORTANT: You must LOG OUT and LOG BACK IN for this to take effect!"
    echo "      After logging back in, run this script again to verify."
    exit 0
fi

echo ""
echo "5. Creating udev rule for uinput..."
UDEV_RULE="/etc/udev/rules.d/99-uinput.rules"
if [ -f "$UDEV_RULE" ]; then
    echo "   ✓ udev rule already exists"
else
    echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' | sudo tee "$UDEV_RULE" > /dev/null
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "   ✓ udev rule created and loaded"
fi

echo ""
echo "6. Testing permissions..."
if [ -r /dev/uinput ] && [ -w /dev/uinput ]; then
    echo "   ✓ You have read/write access to /dev/uinput"
else
    echo "   ❌ No access to /dev/uinput"
    echo "      You may need to log out and log back in"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Test the keyboard typer:"
echo "     cd source-code"
echo "     python3 -m services.keyboard_typer"
echo ""
echo "  2. Start Jarvis and enable Type Mode:"
echo "     python3 main.py"
echo "     (Click the 'Type Mode' button)"
echo ""
