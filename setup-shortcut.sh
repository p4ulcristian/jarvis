#!/bin/bash
# Setup keyboard shortcut for Jarvis typing mode

TRIGGER_FILE="/tmp/jarvis-type-trigger"
CONFIG_FILE="$HOME/.config/jarvis-shortcut.sh"

# Create the trigger script
cat > "$CONFIG_FILE" << 'EOF'
#!/bin/bash
touch /tmp/jarvis-type-trigger
EOF

chmod +x "$CONFIG_FILE"

# Detect desktop environment and configure
if [ "$XDG_CURRENT_DESKTOP" = "KDE" ]; then
    echo "Detected KDE Plasma"
    echo "Please manually add shortcut in System Settings → Shortcuts → Custom Shortcuts"
    echo "Command: $CONFIG_FILE"

elif command -v xbindkeys &> /dev/null; then
    echo "Using xbindkeys to setup Ctrl shortcut"

    # Create xbindkeys config if it doesn't exist
    if [ ! -f "$HOME/.xbindkeysrc" ]; then
        touch "$HOME/.xbindkeysrc"
    fi

    # Add our binding (Ctrl_L = left Ctrl key)
    if ! grep -q "jarvis-type-trigger" "$HOME/.xbindkeysrc"; then
        cat >> "$HOME/.xbindkeysrc" << EOF

# Jarvis typing mode trigger
"touch /tmp/jarvis-type-trigger"
  Control_L + Release

EOF
        echo "Added shortcut to ~/.xbindkeysrc"

        # Restart xbindkeys if running, otherwise start it
        if pgrep xbindkeys > /dev/null; then
            killall xbindkeys
        fi
        xbindkeys
        echo "Started xbindkeys"
    else
        echo "Shortcut already configured in ~/.xbindkeysrc"
    fi
else
    echo "xbindkeys not found. Installing..."
    echo "Run: sudo pacman -S xbindkeys"
    echo "Then run this script again"
    exit 1
fi

echo ""
echo "✓ Setup complete!"
echo "Press Ctrl alone to trigger typing mode"
