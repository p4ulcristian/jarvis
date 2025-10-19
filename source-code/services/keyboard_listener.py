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

    # Listen for events
    try:
        for event in device.read_loop():
            if event.type == ecodes.EV_KEY:
                key_event = categorize(event)

                # Only process key down events (not key up)
                if key_event.keystate == 1:  # 1 = key down, 0 = key up, 2 = key hold
                    key_name = get_key_name(event.code)

                    # Remove KEY_ prefix if present
                    if key_name.startswith('KEY_'):
                        key_name = key_name[4:].lower()

                    # Write event
                    write_event(key_name)

                    # Display in real-time with timestamp
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    print(f"[{timestamp}] {key_name}", flush=True)

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
