"""Output handling - copy to clipboard and paste."""

import subprocess
import json

# Terminal emulators that use Ctrl+Shift+V
TERMINALS = {"ghostty", "kitty", "alacritty", "foot", "wezterm", "konsole", "gnome-terminal"}


def get_active_window_class():
    """Get the class of the currently focused window."""
    try:
        result = subprocess.run(
            ["hyprctl", "activewindow", "-j"],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        return data.get("class", "").lower()
    except Exception:
        return ""


def paste_text(text: str):
    """Copy text to clipboard and paste with appropriate shortcut."""
    try:
        # Copy to clipboard
        subprocess.run(["wl-copy", text], check=True)

        # Check if active window is a terminal (needs Ctrl+Shift+V)
        window_class = get_active_window_class()
        is_terminal = any(term in window_class for term in TERMINALS)

        if is_terminal:
            shortcut = "CTRL_SHIFT,V,"
        else:
            shortcut = "CTRL,V,"

        subprocess.run(["hyprctl", "dispatch", "sendshortcut", shortcut], check=True)
        # Add trailing space
        subprocess.run(["hyprctl", "dispatch", "sendshortcut", ",space,"], check=True)
        print(f"Pasted! (window: {window_class})", flush=True)
    except Exception as e:
        print(f"paste_text error: {e}", flush=True)
