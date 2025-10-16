#!/usr/bin/env python3
"""
Keyboard listener for Jarvis - listens for Ctrl key press/release
Writes events to a file for consumption by the Clojure process
"""
import time
import sys
from pynput import keyboard

# File to write keyboard events
EVENT_FILE = "/tmp/jarvis-keyboard-events"
STATE_FILE = "/tmp/jarvis-ctrl-state"

# Track Ctrl state
ctrl_pressed = False
other_key_pressed = False

def write_event(event_type):
    """Write a keyboard event to the event file"""
    timestamp = int(time.time() * 1000)  # milliseconds
    try:
        with open(EVENT_FILE, 'a') as f:
            f.write(f"{event_type}:{timestamp}\n")
            f.flush()
    except Exception as e:
        print(f"[ERROR] Failed to write event: {e}", file=sys.stderr)

def write_state(is_pressed):
    """Write current Ctrl state to state file"""
    try:
        with open(STATE_FILE, 'w') as f:
            f.write("1\n" if is_pressed else "0\n")
            f.flush()
    except Exception as e:
        print(f"[ERROR] Failed to write state: {e}", file=sys.stderr)

def on_press(key):
    """Called when a key is pressed"""
    global ctrl_pressed, other_key_pressed

    # Check if it's a Ctrl key
    if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
        if not ctrl_pressed:
            ctrl_pressed = True
            other_key_pressed = False
            write_state(True)
            write_event("ctrl-pressed")
            print(f"[KEYBOARD] Ctrl pressed", file=sys.stderr)
    else:
        # Some other key was pressed while Ctrl is held
        if ctrl_pressed:
            other_key_pressed = True

def on_release(key):
    """Called when a key is released"""
    global ctrl_pressed, other_key_pressed

    # Check if it's a Ctrl key
    if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
        if ctrl_pressed:
            was_alone = not other_key_pressed
            ctrl_pressed = False
            other_key_pressed = False
            write_state(False)

            if was_alone:
                write_event("ctrl-alone")
                print(f"[KEYBOARD] Ctrl released (alone)", file=sys.stderr)
            else:
                write_event("ctrl-released")
                print(f"[KEYBOARD] Ctrl released (with other keys)", file=sys.stderr)

def main():
    """Main entry point"""
    print("[KEYBOARD] Starting keyboard listener...", file=sys.stderr)

    # Clear event file and state file
    try:
        open(EVENT_FILE, 'w').close()
        open(STATE_FILE, 'w').write("0\n")
    except Exception as e:
        print(f"[ERROR] Failed to initialize files: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[KEYBOARD] Writing events to {EVENT_FILE}", file=sys.stderr)
    print(f"[KEYBOARD] Writing state to {STATE_FILE}", file=sys.stderr)
    print("[KEYBOARD] Listener ready. Press Ctrl to test...", file=sys.stderr)

    # Start listening
    try:
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    except Exception as e:
        print(f"[ERROR] Keyboard listener failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
