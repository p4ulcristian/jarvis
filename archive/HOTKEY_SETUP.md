# JARVIS Keyboard Hotkey Setup

## What Changed

JARVIS now automatically handles sudo privileges for the keyboard hotkey listener!

### Changes Made:

1. **`source-code/main.py`**
   - Automatically starts keyboard listener with sudo on startup
   - Prompts for password once at launch
   - Handles cleanup when JARVIS exits
   - No manual setup needed!

2. **`source-code/services/keyboard_listener.py`**
   - Detects **Left Ctrl** key press and release events
   - Sends `TYPE_MODE_ENABLE` when Left Ctrl is pressed
   - Sends `TYPE_MODE_DISABLE` when Left Ctrl is released
   - Debug mode enabled: logs all key presses for troubleshooting

3. **`source-code/ui/terminal_ui.py`**
   - Responds to keyboard events from the listener
   - Updates Type Mode button in real-time
   - Shows **Hotkey Status widget** below microphone
   - Displays "Left Ctrl: ON/OFF" with visual feedback
   - Provides voice feedback via say.sh

## How to Use

### Starting JARVIS

Simply run the launcher script:

```bash
./jarvis.sh
```

**What happens:**
1. You'll see a message about sudo access for keyboard hotkey
2. You'll be prompted for your password (standard sudo prompt)
3. Password is verified and cached
4. Keyboard listener starts in background
5. Brief countdown, then JARVIS UI launches
6. Everything is ready!

**Important:** The sudo password prompt appears BEFORE the UI starts, so you'll have time to enter your password in the normal terminal.

### Using the Hotkey

- **Press and hold Left Ctrl** → Type Mode turns ON (green)
  - Voice says "type mode enabled"
  - Hotkey Status widget shows "Left Ctrl: ON ✓" in green
  - Type Mode button turns green
  - Transcriptions will be automatically typed

- **Release Left Ctrl** → Type Mode turns OFF (gray)
  - Voice says "type mode disabled"
  - Hotkey Status widget shows "Left Ctrl: OFF" in gray
  - Type Mode button turns gray
  - Transcriptions appear in UI only

### Workflow Example

1. Open a text editor or any application
2. Position your cursor where you want to type
3. Hold down the **Left Ctrl** key
4. Speak your text
5. Release the **Left Ctrl** key when done
6. Text appears where your cursor was!

### Visual Feedback

The UI now shows real-time hotkey status below the microphone monitor:
- **Green "ON ✓"** when Left Ctrl is pressed
- **Gray "OFF"** when Left Ctrl is released

## Technical Details

### Keyboard Key Detection

The **Left Ctrl** key is detected at the hardware level using the `evdev` library. The listener monitors for key codes `leftctrl` or `ctrl_l` and tracks both press (keystate=1) and release (keystate=0) events.

**Debug Mode**: All key presses are logged to help troubleshoot any detection issues. You can see these logs in the terminal where the keyboard listener is running (requires sudo).

### Permissions

The keyboard listener needs root access to read from `/dev/input/` devices. This is why JARVIS asks for sudo once at startup.

### Process Management

- Keyboard listener runs as separate process with sudo
- JARVIS automatically manages its lifecycle
- Cleanup happens automatically on exit (Ctrl+C or window close)

### Files Involved

- `/tmp/jarvis-keyboard-events` - Communication file between listener and UI
- Event format: `TYPE_MODE_ENABLE:timestamp` or `TYPE_MODE_DISABLE:timestamp`

## Troubleshooting

### "sudo" command not found
Install sudo or run as root (not recommended for normal use).

### Password prompt doesn't appear
The terminal may be in raw mode. Try running from a regular terminal, not inside another TUI app.

### Hotkey doesn't work
1. Check if keyboard listener is running: `ps aux | grep keyboard_listener`
2. Check event file exists: `ls -l /tmp/jarvis-keyboard-events`
3. Check keyboard listener output for debug logs (shows all key presses)
4. Look for ">>> LEFT CTRL pressed" messages when you press Left Ctrl
5. Verify the Hotkey Status widget in UI changes when you press Left Ctrl
6. Run test script: `./test_keyboard_hotkey.py`

### Permission denied
Make sure you entered the correct sudo password when prompted.

## Testing Without JARVIS

You can test the keyboard listener independently:

```bash
# In terminal 1 - start listener manually
sudo python3 source-code/services/keyboard_listener.py

# You'll see ALL key presses logged (debug mode)
# Press Left Ctrl and look for:
# [HH:MM:SS] leftctrl ↓ pressed
# [HH:MM:SS] >>> LEFT CTRL pressed - Type Mode ENABLED <<<
# [HH:MM:SS] leftctrl ↑ released
# [HH:MM:SS] >>> LEFT CTRL released - Type Mode DISABLED <<<

# In terminal 2 - monitor events
./test_keyboard_hotkey.py

# Press Left Ctrl key and watch the events!
```

## Alternative: Manual Mode

If you prefer to run the keyboard listener separately (without sudo prompt on JARVIS startup), you can:

1. Comment out the `start_keyboard_listener()` call in `source-code/main.py` (line 466)
2. Start the listener manually in another terminal before launching JARVIS:
   ```bash
   sudo python3 source-code/services/keyboard_listener.py
   ```
3. Launch JARVIS normally:
   ```bash
   ./jarvis.sh
   ```

## Security Note

**Debug Mode Enabled**: The keyboard listener currently logs ALL key presses to help diagnose issues. You'll see every key you press in the keyboard listener terminal output. This is intentional for troubleshooting.

**Event File**: The `/tmp/jarvis-keyboard-events` file only contains `TYPE_MODE_ENABLE` and `TYPE_MODE_DISABLE` events - not the debug logs of all keys.

**To Disable Debug Logging**: If you want to stop logging all key presses after troubleshooting, comment out lines 89-93 in `source-code/services/keyboard_listener.py`.
