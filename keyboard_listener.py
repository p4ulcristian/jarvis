#!/usr/bin/env python3
"""
Keyboard listener for Jarvis - logs all key presses
Writes events to a file for consumption by the main process
Displays keypresses in real-time
"""
import time
import sys
from datetime import datetime
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

def format_key_display(key):
    """Format key for display (make special keys readable)"""
    try:
        # Regular character keys
        if hasattr(key, 'char') and key.char is not None:
            # Show space visibly
            if key.char == ' ':
                return '[SPACE]'
            # Show newlines
            elif key.char == '\n':
                return '[ENTER]'
            elif key.char == '\t':
                return '[TAB]'
            else:
                return key.char
        # Special keys - show in brackets
        elif hasattr(key, 'name'):
            return f'[{key.name.upper()}]'
        else:
            key_str = str(key).replace('Key.', '')
            return f'[{key_str.upper()}]'
    except:
        return '[UNKNOWN]'

def on_press(key):
    """Called when a key is pressed"""
    key_name = get_key_name(key)
    write_event(key_name)

    # Display in real-time with timestamp
    timestamp = datetime.now().strftime('%H:%M:%S')
    display = format_key_display(key)
    print(f"[{timestamp}] {display}", flush=True)

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
