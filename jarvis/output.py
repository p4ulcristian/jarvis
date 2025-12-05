"""Output handling - clipboard and paste via wtype."""

import os
import time
import subprocess

OUTPUT_MODE = os.environ.get("JARVIS_OUTPUT_MODE", "clipboard")


def paste_text(text: str):
    # Small delay to let CapsLock fully release
    time.sleep(0.1)
    if OUTPUT_MODE == "type":
        _type_direct(text)
    else:
        _clipboard_paste(text)


def _clipboard_paste(text: str):
    """Copy to clipboard and paste with Ctrl+V."""
    subprocess.run(["wl-copy", text], check=True)
    subprocess.run(["wtype", "-M", "ctrl", "v"], check=True)


def _type_direct(text: str):
    """Type directly without touching clipboard."""
    subprocess.run(["wtype", text], check=True)
