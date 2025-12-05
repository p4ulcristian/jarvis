"""Push-to-talk listener using evdev.

Listens for CapsLock press/release without grabbing the device,
so normal keyboard input continues to work.
"""

import threading
from evdev import InputDevice, ecodes, list_devices

# Key states
KEY_UP = 0
KEY_DOWN = 1
KEY_HOLD = 2


def find_keyboards():
    """Find all keyboard devices."""
    keyboards = []
    for path in list_devices():
        try:
            dev = InputDevice(path)
            caps = dev.capabilities()
            # Check if device has EV_KEY capability with actual keys
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                # Look for common keyboard keys (not just mouse buttons)
                if ecodes.KEY_A in keys or ecodes.KEY_CAPSLOCK in keys:
                    keyboards.append(dev)
                else:
                    dev.close()
            else:
                dev.close()
        except Exception:
            pass
    return keyboards


class PTTListener:
    """Listens for push-to-talk key (CapsLock) without grabbing device."""

    def __init__(self, on_press=None, on_release=None, key=ecodes.KEY_CAPSLOCK):
        self.on_press = on_press
        self.on_release = on_release
        self.key = key
        self._running = False
        self._threads = []
        self._devices = []

    def start(self):
        """Start listening on all keyboards."""
        self._running = True
        self._devices = find_keyboards()

        if not self._devices:
            print("Warning: No keyboard devices found for PTT")
            return

        print(f"PTT listening on {len(self._devices)} device(s) for CapsLock")

        for dev in self._devices:
            t = threading.Thread(target=self._listen, args=(dev,), daemon=True)
            t.start()
            self._threads.append(t)

    def _listen(self, device):
        """Listen for key events on a device (no grab!)."""
        try:
            for event in device.read_loop():
                if not self._running:
                    break

                if event.type == ecodes.EV_KEY and event.code == self.key:
                    if event.value == KEY_DOWN:
                        if self.on_press:
                            self.on_press()
                    elif event.value == KEY_UP:
                        if self.on_release:
                            self.on_release()
                    # Ignore KEY_HOLD (repeat) events
        except Exception as e:
            print(f"PTT listener error on {device.path}: {e}")

    def stop(self):
        """Stop listening."""
        self._running = False
        for dev in self._devices:
            try:
                dev.close()
            except Exception:
                pass


if __name__ == "__main__":
    # Test the listener
    def on_press():
        print("CapsLock PRESSED - start recording")

    def on_release():
        print("CapsLock RELEASED - stop recording")

    print("Testing PTT listener (Ctrl+C to exit)")
    print("Press and release CapsLock...")

    listener = PTTListener(on_press=on_press, on_release=on_release)
    listener.start()

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listener.stop()
        print("\nStopped")
