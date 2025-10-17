#!/usr/bin/env python3
"""
Keyboard listener for Jarvis - logs all key presses
Writes events to a file for consumption by the main process
"""
import time
import sys
from pynput import keyboard

# File to write keyboard events
EVENT_FILE = "/tmp/jarvis-keyboard-events"

def write_event(key_name):
    """Write a keyboard event to the event file"""
    timestamp = int(time.time() * 1000)  # milliseconds
    try:
        with open(EVENT_FILE, 'a') as f:
            f.write(f"{key_name}:{timestamp}\n")
            f.flush()
    except Exception as e:
        print(f"[ERROR] Failed to write event: {e}", file=sys.stderr)

def get_key_name(key):
    """Get a readable name for the key"""
    try:
        # Try to get character for regular keys
        if hasattr(key, 'char') and key.char is not None:
            return key.char
        # For special keys, get the name
        elif hasattr(key, 'name'):
            return key.name
        else:
            return str(key).replace('Key.', '')
    except:
        return str(key)

def on_press(key):
    """Called when a key is pressed"""
    key_name = get_key_name(key)
    write_event(key_name)

def on_release(key):
    """Called when a key is released"""
    pass  # Don't log release events

def main():
    """Main entry point"""
    # Clear event file
    try:
        open(EVENT_FILE, 'w').close()
    except Exception as e:
        print(f"[ERROR] Failed to initialize file: {e}", file=sys.stderr)
        sys.exit(1)

    # Start listening
    try:
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
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
