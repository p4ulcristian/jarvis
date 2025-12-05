"""Evdev-based hotkey listener for true PTT."""

import threading
from evdev import InputDevice, ecodes, list_devices


def find_keyboard():
    """Find a keyboard device."""
    for path in list_devices():
        device = InputDevice(path)
        caps = device.capabilities()
        # Check if device has key events and has capslock
        if ecodes.EV_KEY in caps:
            keys = caps[ecodes.EV_KEY]
            if ecodes.KEY_CAPSLOCK in keys:
                return device
    return None


def listen_hotkey(key_code, on_press, on_release):
    """
    Listen for key press/release events.

    Args:
        key_code: evdev key code (e.g., ecodes.KEY_CAPSLOCK)
        on_press: callback for key press
        on_release: callback for key release
    """
    device = find_keyboard()
    if not device:
        print("No keyboard found!", flush=True)
        return

    print(f"Listening on: {device.name}", flush=True)

    try:
        for event in device.read_loop():
            if event.type == ecodes.EV_KEY and event.code == key_code:
                if event.value == 1:  # Press
                    on_press()
                elif event.value == 0:  # Release
                    on_release()
    except Exception as e:
        print(f"Hotkey listener error: {e}")


def start_hotkey_thread(key_code, on_press, on_release):
    """Start hotkey listener in background thread."""
    thread = threading.Thread(
        target=listen_hotkey,
        args=(key_code, on_press, on_release),
        daemon=True
    )
    thread.start()
    return thread
