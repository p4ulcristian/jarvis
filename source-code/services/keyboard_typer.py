#!/usr/bin/env python3
"""
Keyboard Typer for Jarvis - Wayland-compatible typing automation
Uses python-evdev with uinput for virtual keyboard input
"""
import time
import logging
from typing import Optional
from evdev import UInput, ecodes as e

logger = logging.getLogger(__name__)

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False
    logger.warning("pyperclip not available - paste_text() will use type_text() fallback")


# Key mapping: character -> evdev keycode
# This maps common ASCII characters to Linux input event codes
KEY_MAP = {
    # Letters (lowercase)
    'a': e.KEY_A, 'b': e.KEY_B, 'c': e.KEY_C, 'd': e.KEY_D,
    'e': e.KEY_E, 'f': e.KEY_F, 'g': e.KEY_G, 'h': e.KEY_H,
    'i': e.KEY_I, 'j': e.KEY_J, 'k': e.KEY_K, 'l': e.KEY_L,
    'm': e.KEY_M, 'n': e.KEY_N, 'o': e.KEY_O, 'p': e.KEY_P,
    'q': e.KEY_Q, 'r': e.KEY_R, 's': e.KEY_S, 't': e.KEY_T,
    'u': e.KEY_U, 'v': e.KEY_V, 'w': e.KEY_W, 'x': e.KEY_X,
    'y': e.KEY_Y, 'z': e.KEY_Z,

    # Numbers
    '0': e.KEY_0, '1': e.KEY_1, '2': e.KEY_2, '3': e.KEY_3,
    '4': e.KEY_4, '5': e.KEY_5, '6': e.KEY_6, '7': e.KEY_7,
    '8': e.KEY_8, '9': e.KEY_9,

    # Special characters (no shift)
    ' ': e.KEY_SPACE,
    '\n': e.KEY_ENTER,
    '\t': e.KEY_TAB,
    '-': e.KEY_MINUS,
    '=': e.KEY_EQUAL,
    '[': e.KEY_LEFTBRACE,
    ']': e.KEY_RIGHTBRACE,
    '\\': e.KEY_BACKSLASH,
    ';': e.KEY_SEMICOLON,
    '\'': e.KEY_APOSTROPHE,
    '`': e.KEY_GRAVE,
    ',': e.KEY_COMMA,
    '.': e.KEY_DOT,
    '/': e.KEY_SLASH,
}

# Shifted character mappings (char -> (keycode, needs_shift))
SHIFT_MAP = {
    'A': e.KEY_A, 'B': e.KEY_B, 'C': e.KEY_C, 'D': e.KEY_D,
    'E': e.KEY_E, 'F': e.KEY_F, 'G': e.KEY_G, 'H': e.KEY_H,
    'I': e.KEY_I, 'J': e.KEY_J, 'K': e.KEY_K, 'L': e.KEY_L,
    'M': e.KEY_M, 'N': e.KEY_N, 'O': e.KEY_O, 'P': e.KEY_P,
    'Q': e.KEY_Q, 'R': e.KEY_R, 'S': e.KEY_S, 'T': e.KEY_T,
    'U': e.KEY_U, 'V': e.KEY_V, 'W': e.KEY_W, 'X': e.KEY_X,
    'Y': e.KEY_Y, 'Z': e.KEY_Z,

    # Shifted symbols
    '!': e.KEY_1,
    '@': e.KEY_2,
    '#': e.KEY_3,
    '$': e.KEY_4,
    '%': e.KEY_5,
    '^': e.KEY_6,
    '&': e.KEY_7,
    '*': e.KEY_8,
    '(': e.KEY_9,
    ')': e.KEY_0,
    '_': e.KEY_MINUS,
    '+': e.KEY_EQUAL,
    '{': e.KEY_LEFTBRACE,
    '}': e.KEY_RIGHTBRACE,
    '|': e.KEY_BACKSLASH,
    ':': e.KEY_SEMICOLON,
    '"': e.KEY_APOSTROPHE,
    '~': e.KEY_GRAVE,
    '<': e.KEY_COMMA,
    '>': e.KEY_DOT,
    '?': e.KEY_SLASH,
}


class KeyboardTyper:
    """
    Wayland-compatible keyboard typer using uinput
    Creates a virtual keyboard device to simulate typing
    """

    def __init__(self, typing_delay: float = 0.01):
        """
        Initialize keyboard typer

        Args:
            typing_delay: Delay between keystrokes in seconds (default: 0.01 = 10ms)
        """
        self.typing_delay = typing_delay
        self.ui: Optional[UInput] = None
        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize the virtual keyboard device

        Returns:
            True if successful, False otherwise
        """
        if self._initialized:
            return True

        try:
            # Create virtual keyboard with all necessary key capabilities
            capabilities = {
                e.EV_KEY: list(set(KEY_MAP.values()) | set(SHIFT_MAP.values()) | {e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT})
            }

            self.ui = UInput(capabilities, name='jarvis-virtual-keyboard')
            self._initialized = True
            logger.info("Virtual keyboard initialized successfully")
            return True

        except PermissionError as err:
            logger.error(
                "Permission denied: Cannot access /dev/uinput. "
                "Please add your user to the 'input' group:\n"
                "  sudo usermod -a -G input $USER\n"
                "Then log out and log back in."
            )
            return False
        except Exception as err:
            logger.error(f"Failed to initialize virtual keyboard: {err}")
            return False

    def type_text(self, text: str, delay_before_typing: float = 0.0) -> bool:
        """
        Type the given text using the virtual keyboard

        Args:
            text: Text to type
            delay_before_typing: Delay in seconds before starting to type (default: 0.0)

        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            if not self.initialize():
                logger.error("Failed to initialize keyboard before typing")
                return False

        try:
            # Optional delay to allow window focus
            if delay_before_typing > 0:
                logger.debug(f"Waiting {delay_before_typing}s before typing...")
                time.sleep(delay_before_typing)

            logger.debug(f"Typing text: {text}")
            for char in text:
                self._type_char(char)
                time.sleep(self.typing_delay)

            # Add a space at the end for natural flow
            self._type_char(' ')

            logger.info(f"Successfully typed text: {text}")
            return True

        except Exception as err:
            logger.error(f"Failed to type text: {err}", exc_info=True)
            return False

    def paste_text(self, text: str, delay_before_paste: float = 0.0) -> bool:
        """
        Insert text instantly by copying to clipboard and simulating Ctrl+V

        Args:
            text: Text to paste
            delay_before_paste: Delay in seconds before pasting (default: 0.0)

        Returns:
            True if successful, False otherwise
        """
        if not PYPERCLIP_AVAILABLE:
            logger.warning("pyperclip not available, falling back to type_text()")
            return self.type_text(text, delay_before_typing=delay_before_paste)

        if not self._initialized:
            if not self.initialize():
                logger.error("Failed to initialize keyboard before pasting")
                return False

        try:
            # Optional delay to allow window focus
            if delay_before_paste > 0:
                logger.debug(f"Waiting {delay_before_paste}s before pasting...")
                time.sleep(delay_before_paste)

            # Add a space at the end for natural flow
            text_with_space = text + ' '

            # Copy text to clipboard
            logger.debug(f"Copying to clipboard: {text}")
            pyperclip.copy(text_with_space)

            # Longer delay to ensure clipboard is updated (especially on Wayland)
            time.sleep(0.05)

            # Simulate Ctrl+V
            logger.debug("Simulating Ctrl+V")
            self.ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 1)  # Ctrl down
            self.ui.syn()
            time.sleep(0.01)  # Small delay between Ctrl and V
            self.ui.write(e.EV_KEY, e.KEY_V, 1)  # V down
            self.ui.syn()
            self.ui.write(e.EV_KEY, e.KEY_V, 0)  # V up
            self.ui.syn()
            self.ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 0)  # Ctrl up
            self.ui.syn()

            logger.info(f"Successfully pasted text via clipboard: {text}")
            return True

        except Exception as err:
            logger.error(f"Failed to paste text: {err}", exc_info=True)
            # Try fallback to typing
            logger.warning("Attempting fallback to type_text()")
            return self.type_text(text, delay_before_typing=delay_before_paste)

    def _type_char(self, char: str) -> None:
        """
        Type a single character

        Args:
            char: Character to type
        """
        # Check if character needs shift
        if char in SHIFT_MAP:
            keycode = SHIFT_MAP[char]
            self._press_key_with_shift(keycode)
        elif char in KEY_MAP:
            keycode = KEY_MAP[char]
            self._press_key(keycode)
        else:
            # Unknown character - skip with debug log
            logger.debug(f"Skipping unsupported character: {repr(char)}")

    def _press_key(self, keycode: int) -> None:
        """
        Press and release a key

        Args:
            keycode: evdev keycode
        """
        self.ui.write(e.EV_KEY, keycode, 1)  # Key down
        self.ui.syn()
        self.ui.write(e.EV_KEY, keycode, 0)  # Key up
        self.ui.syn()

    def _press_key_with_shift(self, keycode: int) -> None:
        """
        Press and release a key with shift modifier

        Args:
            keycode: evdev keycode
        """
        self.ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)  # Shift down
        self.ui.syn()
        self.ui.write(e.EV_KEY, keycode, 1)  # Key down
        self.ui.syn()
        self.ui.write(e.EV_KEY, keycode, 0)  # Key up
        self.ui.syn()
        self.ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)  # Shift up
        self.ui.syn()

    def cleanup(self) -> None:
        """Clean up resources"""
        if self.ui:
            try:
                self.ui.close()
                logger.info("Virtual keyboard closed")
            except Exception as err:
                logger.error(f"Error closing virtual keyboard: {err}")
            finally:
                self.ui = None
                self._initialized = False


# Global instance (singleton pattern)
_typer_instance: Optional[KeyboardTyper] = None


def get_typer(typing_delay: float = 0.01) -> KeyboardTyper:
    """
    Get or create the global KeyboardTyper instance

    Args:
        typing_delay: Delay between keystrokes in seconds

    Returns:
        KeyboardTyper instance
    """
    global _typer_instance
    if _typer_instance is None:
        _typer_instance = KeyboardTyper(typing_delay=typing_delay)
    return _typer_instance


if __name__ == "__main__":
    # Test the keyboard typer
    import sys

    logging.basicConfig(level=logging.DEBUG)

    typer = KeyboardTyper(typing_delay=0.02)

    if not typer.initialize():
        print("Failed to initialize keyboard typer", file=sys.stderr)
        sys.exit(1)

    print("Keyboard typer initialized. Testing in 3 seconds...")
    time.sleep(3)

    test_text = "Hello, World! This is a test of the Jarvis keyboard typer."
    print(f"Typing: {test_text}")

    if typer.type_text(test_text):
        print("✓ Typing successful")
    else:
        print("✗ Typing failed")

    typer.cleanup()
