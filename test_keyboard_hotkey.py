#!/usr/bin/env python3
"""
Test script for the keyboard hotkey implementation
Monitors the keyboard events file to verify < key detection
"""
import time
import os

EVENT_FILE = "/tmp/jarvis-keyboard-events"

def monitor_events():
    """Monitor keyboard events file for Type Mode events"""
    print("Monitoring keyboard events...")
    print("Press and hold < key to test Type Mode enable/disable")
    print("Press Ctrl+C to exit\n")

    # Track file position
    last_pos = 0

    # Wait for file to exist
    while not os.path.exists(EVENT_FILE):
        print(f"Waiting for {EVENT_FILE} to be created...")
        print("Make sure keyboard_listener.py is running with sudo!")
        time.sleep(1)

    print(f"Found {EVENT_FILE}, starting monitor...\n")

    try:
        while True:
            with open(EVENT_FILE, 'r') as f:
                # Seek to last position
                f.seek(last_pos)

                # Read new content
                new_content = f.read()
                last_pos = f.tell()

                # Process new events
                for line in new_content.strip().split('\n'):
                    if not line:
                        continue

                    parts = line.split(':')
                    if len(parts) >= 1:
                        event_name = parts[0]

                        if event_name == 'TYPE_MODE_ENABLE':
                            print("✅ TYPE MODE ENABLED - < key pressed")
                        elif event_name == 'TYPE_MODE_DISABLE':
                            print("❌ TYPE MODE DISABLED - < key released")
                        else:
                            print(f"   Other event: {event_name}")

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped")

if __name__ == "__main__":
    monitor_events()
