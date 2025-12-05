"""Output handling - type text using wtype."""

import subprocess


def paste_text(text: str):
    """Type text directly using wtype with trailing space."""
    try:
        subprocess.run(["wtype", text + " "], check=True)
        print(f"Typed: {text}", flush=True)
    except Exception as e:
        print(f"paste_text error: {e}", flush=True)
