# Type Mode Setup Guide

## Overview

Type Mode allows Jarvis to automatically type transcribed speech directly into any application. This uses a Wayland-compatible virtual keyboard via `python-evdev` and the Linux `uinput` kernel module.

## How It Works

1. **Virtual Keyboard**: Creates a virtual input device using `uinput`
2. **Type Mode Button**: Toggle button in the terminal UI
3. **Auto-typing**: When enabled, all transcriptions are automatically typed as keyboard input
4. **Wayland Compatible**: Works on both Wayland and X11

## Prerequisites

### 1. Install python-evdev

Already included in `requirements.txt`:
```bash
pip install evdev==1.7.1
```

### 2. Set Up Permissions

The `uinput` module requires special permissions. Choose **ONE** of these methods:

#### Method A: Add User to input Group (Recommended)
```bash
# Add your user to the input group
sudo usermod -a -G input $USER

# Verify the group was added
groups $USER

# Log out and log back in for changes to take effect
```

#### Method B: Create udev Rule (Alternative)
```bash
# Create a udev rule for uinput access
sudo tee /etc/udev/rules.d/99-uinput.rules > /dev/null <<EOF
KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Add yourself to input group
sudo usermod -a -G input $USER

# Reboot or log out/in
```

#### Method C: Run with sudo (Not Recommended)
```bash
# Only for testing - not recommended for production
sudo python3 source-code/main.py
```

### 3. Load uinput Module

```bash
# Load the module (temporary - until reboot)
sudo modprobe uinput

# Make it permanent (auto-load on boot)
echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf
```

### 4. Verify Setup

```bash
# Check if uinput device exists
ls -l /dev/uinput

# Should show something like:
# crw-rw---- 1 root input 10, 223 Oct 18 12:00 /dev/uinput

# Test the keyboard typer standalone
cd source-code
python3 -m services.keyboard_typer
```

## Usage

### 1. Start Jarvis
```bash
cd /home/paul/Work/jarvis/source-code
python3 main.py
```

### 2. Enable Type Mode
- Click the **"Type Mode"** button in the terminal UI header
- You should hear: "type mode enabled"
- The button will turn green when active

### 3. Speak and Watch It Type
- Speak into your microphone
- Transcribed text will appear in the UI
- **AND** will be automatically typed into your active application
- Each transcription adds a space at the end

### 4. Disable Type Mode
- Click the **"Type Mode"** button again
- You should hear: "type mode disabled"
- Transcriptions will still appear in UI but won't be typed

## Features

### Supported Characters
- All lowercase letters (a-z)
- All uppercase letters (A-Z) with auto-shift
- Numbers (0-9)
- Common punctuation: `. , ! ? ; : ' " - _ ( ) [ ] { } / \`
- Special characters: `@ # $ % ^ & * + = < > | ~`
- Whitespace: space, tab, newline

### Auto-spacing
- Each transcription automatically adds a trailing space
- Creates natural word separation

### Low Latency
- Default 10ms delay between keystrokes
- Configurable in `keyboard_typer.py`

## Troubleshooting

### Permission Denied Error
```
PermissionError: [Errno 13] Permission denied: '/dev/uinput'
```

**Solution**: You haven't set up permissions correctly.
1. Add yourself to `input` group: `sudo usermod -a -G input $USER`
2. Log out and log back in
3. Verify: `groups` should show "input" in the list

### Module Not Found: evdev
```
ModuleNotFoundError: No module named 'evdev'
```

**Solution**: Install evdev
```bash
pip install evdev==1.7.1
```

### uinput Device Not Found
```
FileNotFoundError: [Errno 2] No such file or directory: '/dev/uinput'
```

**Solution**: Load the uinput kernel module
```bash
sudo modprobe uinput
```

### Typing Not Working (No Error)
1. Check Type Mode is enabled (button should be green)
2. Check system logs in the UI for errors
3. Test with standalone script: `python3 -m services.keyboard_typer`
4. Verify permissions: `ls -l /dev/uinput`

### Characters Missing or Wrong
- Some special Unicode characters may not be supported
- Check logs for "Skipping unsupported character" messages
- Basic ASCII should work perfectly

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Terminal UI (terminal_ui.py)                   │
│  - Type Mode Toggle Button                      │
│  - Updates DataBridge state                     │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  DataBridge (data_bridge.py)                    │
│  - Tracks type_mode state (bool)                │
│  - Thread-safe state access                     │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  Main Loop (main.py)                            │
│  - Receives transcription                       │
│  - Checks if type_mode is True                  │
│  - Calls keyboard_typer.type_text()             │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  KeyboardTyper (keyboard_typer.py)              │
│  - Creates virtual keyboard via uinput          │
│  - Maps characters to keycodes                  │
│  - Simulates keypresses with evdev              │
└─────────────────────────────────────────────────┘
```

## Files Modified

1. **`services/keyboard_typer.py`** (NEW)
   - Virtual keyboard implementation
   - Character mapping and typing logic

2. **`ui/data_bridge.py`**
   - Added `type_mode` field to `SystemState`
   - Thread-safe state tracking

3. **`ui/terminal_ui.py`**
   - Type Mode button updates state in DataBridge
   - Logs when mode changes

4. **`main.py`**
   - Initializes keyboard typer
   - Checks type_mode before typing
   - Cleanup on shutdown

5. **`requirements.txt`**
   - Added `evdev==1.7.1`

## Security Considerations

⚠️ **Important**: Type Mode has full keyboard access and will type into ANY active window.

- Be careful when Type Mode is enabled
- Transcriptions will be typed wherever your cursor is focused
- Disable Type Mode when not needed
- The virtual keyboard has the same capabilities as a physical keyboard

## Performance

- **Latency**: ~10ms per character (configurable)
- **Overhead**: Minimal CPU usage
- **Memory**: Virtual device uses <1MB
- **Compatibility**: Works on Wayland and X11

## Future Improvements

Potential enhancements:
- [ ] Configurable typing speed
- [ ] Pause/resume typing mid-transcription
- [ ] Application-specific filtering (only type in certain apps)
- [ ] Keyboard shortcut to toggle Type Mode
- [ ] Visual indicator when typing is active
- [ ] Unicode emoji support
