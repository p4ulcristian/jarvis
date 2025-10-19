#!/usr/bin/env python3
"""
Keyboard listener for Jarvis - logs all key presses
Writes events to a file for consumption by the main process
Displays keypresses in real-time
Uses evdev for Wayland compatibility
"""
import time
import sys
from datetime import datetime
from evdev import InputDevice, categorize, ecodes, list_devices

# File to write keyboard events
EVENT_FILE = "/tmp/jarvis-keyboard-events"

def find_keyboard_device():
    """Find the keyboard input device"""
    devices = [InputDevice(path) for path in list_devices()]

    # Look for keyboard device
    for device in devices:
        # Check if device has keyboard capabilities
        caps = device.capabilities()
        if ecodes.EV_KEY in caps:
            # Check if it has letter keys (indicates keyboard not just power button)
            keys = caps[ecodes.EV_KEY]
            if ecodes.KEY_A in keys or ecodes.KEY_LEFTCTRL in keys:
                print(f"[INFO] Using keyboard device: {device.name} ({device.path})", file=sys.stderr)
                return device

    print("[ERROR] No keyboard device found", file=sys.stderr)
    return None

def write_event(key_name):
    """Write a keyboard event to the event file"""
    timestamp = int(time.time() * 1000)  # milliseconds
    try:
        with open(EVENT_FILE, 'a') as f:
            f.write(f"{key_name}:{timestamp}\n")
            f.flush()
    except Exception as e:
        print(f"[ERROR] Failed to write event: {e}", file=sys.stderr)

def get_key_name(keycode):
    """Get a readable name for the key code"""
    try:
        return ecodes.KEY[keycode]
    except KeyError:
        return f"KEY_{keycode}"

def main():
    """Main entry point"""
    # Clear event file
    try:
        open(EVENT_FILE, 'w').close()

        # Set permissions so any user can read/write (since we run as root)
        import os
        os.chmod(EVENT_FILE, 0o666)

        print(f"[INFO] Event file initialized: {EVENT_FILE}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Failed to initialize file: {e}", file=sys.stderr)
        sys.exit(1)

    # Find keyboard device
    device = find_keyboard_device()
    if not device:
        print("[ERROR] Cannot proceed without keyboard device", file=sys.stderr)
        print("[HINT] You may need to run this script with sudo or add your user to the 'input' group:", file=sys.stderr)
        print("       sudo usermod -a -G input $USER", file=sys.stderr)
        print("       Then log out and log back in.", file=sys.stderr)
        sys.exit(1)

    print("[INFO] Listening for keyboard events... Press Ctrl+C to exit", file=sys.stderr)
    print("[INFO] Hotkey: Hold LEFT CTRL to enable Type Mode (auto-type transcriptions)", file=sys.stderr)
    print("[INFO] Debug mode: Logging all key presses", file=sys.stderr)

    # Track left Ctrl key state for push-to-talk
    left_ctrl_pressed = False
    other_key_pressed_during_left_ctrl = False

    # Listen for events
    try:
        for event in device.read_loop():
            if event.type == ecodes.EV_KEY:
                key_event = categorize(event)
                key_name = get_key_name(event.code)

                # Remove KEY_ prefix if present
                if key_name.startswith('KEY_'):
                    key_name = key_name[4:].lower()

                # DEBUG: Log all key presses for troubleshooting
                timestamp = datetime.now().strftime('%H:%M:%S')
                if key_event.keystate == 1:  # Key down
                    print(f"[{timestamp}] {key_name} ↓ pressed", flush=True)
                elif key_event.keystate == 0:  # Key up
                    print(f"[{timestamp}] {key_name} ↑ released", flush=True)

                # Check for LEFT CTRL key (can appear as 'leftctrl' or 'ctrl_l')
                if key_name in ['leftctrl', 'ctrl_l']:
                    # Key down event - start PTT
                    if key_event.keystate == 1 and not left_ctrl_pressed:
                        left_ctrl_pressed = True
                        other_key_pressed_during_left_ctrl = False
                        # Only start PTT if no other keys are pressed
                        write_event('PTT_START')
                        print(f"[{timestamp}] >>> LEFT CTRL pressed - Type Mode ACTIVE <<<", flush=True)
                    # Key up event - stop PTT
                    elif key_event.keystate == 0 and left_ctrl_pressed:
                        left_ctrl_pressed = False
                        # Only type if no other keys were pressed (not a keyboard combo)
                        if not other_key_pressed_during_left_ctrl:
                            write_event('PTT_STOP')
                            print(f"[{timestamp}] >>> LEFT CTRL released - Typing transcription <<<", flush=True)
                        else:
                            write_event('PTT_CANCEL')
                            print(f"[{timestamp}] >>> LEFT CTRL released with combo - Type Mode CANCELLED <<<", flush=True)
                        other_key_pressed_during_left_ctrl = False

                else:
                    # Track if any other key was pressed while Left Ctrl is held
                    if left_ctrl_pressed and key_event.keystate == 1:
                        other_key_pressed_during_left_ctrl = True
                        print(f"[{timestamp}] >>> Other key pressed during Ctrl hold - will cancel PTT <<<", flush=True)

    except KeyboardInterrupt:
        print("\n[INFO] Keyboard listener stopped", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] Keyboard listener failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    import signal

    # Suppress KeyboardInterrupt traceback
    def signal_handler(sig, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
