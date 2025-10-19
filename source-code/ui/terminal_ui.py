#!/usr/bin/env python3
"""
JARVIS Terminal UI
Interactive dashboard using Textual framework with scrollable elements
Soft pastel color theme - easy on the eyes
"""

import asyncio
from datetime import datetime
from typing import Optional
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, RichLog, ProgressBar, Header, Footer, Button
from textual.reactive import reactive
from rich.text import Text
import subprocess

from .data_bridge import DataBridge


class ToggleButton(Button):
    """Button widget that can be toggled on/off with different colors"""

    is_active = reactive(False)
    can_focus = True  # Allow button to receive focus

    def __init__(self, label: str, *args, **kwargs):
        super().__init__(label, *args, **kwargs)
        self.update_classes()  # Initialize classes on creation

    def toggle(self) -> None:
        """Toggle the button state"""
        self.is_active = not self.is_active
        self.update_classes()

    def update_classes(self) -> None:
        """Update CSS classes based on state"""
        if self.is_active:
            self.add_class("active")
            self.remove_class("passive")
        else:
            self.add_class("passive")
            self.remove_class("active")


class MicMonitor(Static):
    """Widget to display microphone activity level"""

    level = reactive(0.0)
    peak = reactive(0.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "Microphone"

    def render(self) -> Text:
        """Render the mic level display with soft pastel colors"""
        level = self.level

        # Create visual bar with smooth gradient effect
        bar_length = 40
        filled = int((level / 100) * bar_length)

        # Use different characters for smoother visual
        bar_chars = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        filled_bar = "".join([bar_chars[min(7, int((i / bar_length) * 8))] for i in range(filled)])
        empty_bar = "░" * (bar_length - filled)
        bar = filled_bar + empty_bar

        # Soft pastel colors based on level
        if level > 70:
            color = "#ff9999"  # pastel red
            status_text = "LOUD"
            status_color = "#ff9999"
            icon = "🔊"
        elif level > 40:
            color = "#ffcc99"  # pastel orange
            status_text = "ACTIVE"
            status_color = "#ffcc99"
            icon = "🎤"
        elif level > 10:
            color = "#99ff99"  # pastel green
            status_text = "SPEAKING"
            status_color = "#99ff99"
            icon = "💬"
        else:
            color = "#ccccdd"  # soft gray
            status_text = "QUIET"
            status_color = "#9999cc"
            icon = "🔇"

        content = Text()
        content.append(f"{icon} ", style="")
        content.append(bar, style=color)
        content.append("\n\n")
        content.append(f"Level: ", style="#b8b8d0")
        content.append(f"{level:.0f}%", style=color)
        content.append(f"  │  ", style="#b8b8d0")
        content.append(f"Peak: ", style="#b8b8d0")
        content.append(f"{self.peak:.0f}%", style="#ccccdd")
        content.append(f"\n\n")
        content.append(f"{status_text}", style=status_color)

        return content


class KeyStatusWidget(Static):
    """Widget to display keyboard hotkey status"""

    ctrl_pressed = reactive(False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "⌨️ Hotkey Status"

    def render(self) -> Text:
        """Render the key status display with soft pastel colors"""
        content = Text()

        if self.ctrl_pressed:
            # Ctrl is pressed - Type Mode ON
            content.append("⌨️  Left Ctrl: ", style="#b8b8d0")
            content.append("ON", style="bold #99ff99")
            content.append(" ✓", style="#99ff99")
            content.append("\n\n")
            content.append("Type Mode ", style="#b8b8d0")
            content.append("ACTIVE", style="bold #99ff99")
        else:
            # Ctrl is released - Type Mode OFF
            content.append("⌨️  Left Ctrl: ", style="#b8b8d0")
            content.append("OFF", style="#7888a0")
            content.append("\n\n")
            content.append("Type Mode ", style="#b8b8d0")
            content.append("INACTIVE", style="#7888a0")

        return content


class JarvisApp(App):
    """Textual App for JARVIS Dashboard"""

    # Keyboard shortcuts
    # Note: Ctrl key alone is handled by keyboard_listener.py
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
    ]

    CSS = """
    Screen {
        layout: grid;
        grid-size: 5 5;
        grid-rows: 3 1fr 5 1fr 1;
        background: #1a1a2e;
    }

    #header {
        column-span: 5;
        height: 3;
        layout: horizontal;
        background: #2d2d44;
        border: round #b8b8ff;
    }

    #title {
        width: 1fr;
        content-align: center middle;
        text-style: bold;
        color: #b8b8ff;
        background: #2d2d44;
        text-align: center;
    }

    #button-bar {
        width: auto;
        height: 100%;
        align: right middle;
        padding: 0 2;
    }

    ToggleButton {
        margin: 0 1;
        min-width: 15;
        height: 1;
    }

    ToggleButton.passive {
        background: #3d3d54;
        color: #7888a0;
        border: none;
    }

    ToggleButton.passive:hover {
        background: #4d4d64;
        color: #8898b0;
    }

    ToggleButton.active {
        background: #99ddbb;
        color: #1a1a2e;
        text-style: bold;
        border: none;
    }

    ToggleButton.active:hover {
        background: #aaeedd;
        color: #1a1a2e;
    }

    #transcription {
        column-span: 4;
        row-span: 2;
        border: round #99ddbb;
        background: #1e1e2e;
        height: 100%;
    }

    #mic {
        column-span: 1;
        border: round #ddaadd;
        background: #1e1e2e;
        height: 100%;
        padding: 1 2;
    }

    #key-status {
        column-span: 1;
        border: round #ffcc99;
        background: #1e1e2e;
        height: 100%;
        padding: 1 2;
    }

    #logs {
        column-span: 5;
        border: round #99ccff;
        background: #1e1e2e;
        height: 100%;
    }

    Footer {
        column-span: 5;
        background: #2d2d44;
        color: #b8b8d0;
    }

    RichLog {
        scrollbar-gutter: stable;
        scrollbar-background: #2d2d44;
        scrollbar-color: #b8b8ff;
    }
    """

    def __init__(self, data_bridge: DataBridge, refresh_rate: int = 4):
        """
        Initialize JARVIS App

        Args:
            data_bridge: DataBridge instance for receiving data
            refresh_rate: UI refresh rate in Hz
        """
        super().__init__()
        self.data_bridge = data_bridge
        self.refresh_rate = refresh_rate
        self.transcription_count = 0
        self.log_count = 0
        self.keyboard_event_file = "/tmp/jarvis-keyboard-events"
        self.last_keyboard_check_pos = 0

    def compose(self) -> ComposeResult:
        """Create child widgets"""
        # Header with title and buttons
        with Container(id="header"):
            yield Static("✨ J · A · R · V · I · S ✨", id="title")
            with Horizontal(id="button-bar"):
                type_btn = ToggleButton("Type Mode", id="type-mode-btn")
                type_btn.add_class("passive")
                yield type_btn

                chat_btn = ToggleButton("Chat Mode", id="chat-mode-btn")
                chat_btn.add_class("passive")
                yield chat_btn

        # Transcription log (scrollable)
        transcription_log = RichLog(
            highlight=True,
            markup=True,
            id="transcription"
        )
        transcription_log.border_title = "💬 Transcription"
        transcription_log.border_subtitle = "scroll: ↑↓ pgup/pgdn"
        yield transcription_log

        # Mic monitor
        yield MicMonitor(id="mic")

        # Key status widget (shows Ctrl key state)
        yield KeyStatusWidget(id="key-status")

        # System logs (scrollable)
        system_log = RichLog(
            highlight=True,
            markup=True,
            id="logs"
        )
        system_log.border_title = "📋 System Logs"
        yield system_log

        # Footer
        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts"""
        # Start the data update loop
        self.set_interval(1.0 / self.refresh_rate, self.update_data)

        # Add initial messages with soft colors
        trans_log = self.query_one("#transcription", RichLog)
        trans_log.write("[#b8b8d0]✨ Ready to listen...[/#b8b8d0]")

        sys_log = self.query_one("#logs", RichLog)
        sys_log.write("[#99ccff]⚡ System initialized[/#99ccff]")

    def check_keyboard_events(self) -> None:
        """Check for keyboard events and handle < key press/release"""
        try:
            import os
            if not os.path.exists(self.keyboard_event_file):
                return

            # Read new events from file
            with open(self.keyboard_event_file, 'r') as f:
                # On first run, skip to end of file to ignore old events
                if self.last_keyboard_check_pos == 0:
                    f.seek(0, 2)  # Seek to end
                    self.last_keyboard_check_pos = f.tell()
                    return  # Don't process old events

                f.seek(self.last_keyboard_check_pos)
                new_events = f.read()
                self.last_keyboard_check_pos = f.tell()

            # Process events
            for line in new_events.strip().split('\n'):
                if not line:
                    continue

                # Parse event: "key_name:timestamp"
                parts = line.split(':')
                if len(parts) >= 1:
                    key_name = parts[0]

                    # Get the Type Mode button and key status widget
                    type_btn = self.query_one("#type-mode-btn", ToggleButton)
                    key_status = self.query_one("#key-status", KeyStatusWidget)
                    say_script = "/home/paul/Work/jarvis/source-code/services/say.sh"

                    # Check for Ctrl key press (enable Type Mode)
                    if key_name == 'TYPE_MODE_ENABLE':
                        # Enable Type Mode
                        type_btn.is_active = True
                        type_btn.update_classes()

                        # Update key status widget
                        key_status.ctrl_pressed = True

                        # Update state in data bridge
                        self.data_bridge.update_state(type_mode=True)

                        subprocess.Popen([say_script, "type mode enabled"])
                        self.data_bridge.send_log("INFO", "Type Mode: ON - Left Ctrl pressed")

                    # Check for Ctrl key release (disable Type Mode)
                    elif key_name == 'TYPE_MODE_DISABLE':
                        # Disable Type Mode
                        type_btn.is_active = False
                        type_btn.update_classes()

                        # Update key status widget
                        key_status.ctrl_pressed = False

                        # Update state in data bridge
                        self.data_bridge.update_state(type_mode=False)

                        subprocess.Popen([say_script, "type mode disabled"])
                        self.data_bridge.send_log("INFO", "Type Mode: OFF - Left Ctrl released")

        except Exception as e:
            # Silently ignore errors to not disrupt UI
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        button = event.button

        if isinstance(button, ToggleButton):
            button.toggle()

            say_script = "/home/paul/Work/jarvis/source-code/services/say.sh"

            if button.id == "type-mode-btn":
                # Update state in data bridge
                self.data_bridge.update_state(type_mode=button.is_active)

                if button.is_active:
                    subprocess.Popen([say_script, "type mode enabled"])
                    self.data_bridge.send_log("INFO", "Type Mode: ON - Transcriptions will be typed automatically")
                else:
                    subprocess.Popen([say_script, "type mode disabled"])
                    self.data_bridge.send_log("INFO", "Type Mode: OFF")

            elif button.id == "chat-mode-btn":
                if button.is_active:
                    subprocess.Popen([say_script, "chat mode enabled"])
                else:
                    subprocess.Popen([say_script, "chat mode disabled"])

    def action_toggle_type_mode(self) -> None:
        """Action to toggle Type Mode via keyboard"""
        try:
            type_btn = self.query_one("#type-mode-btn", ToggleButton)
            type_btn.toggle()

            # Update state in data bridge
            self.data_bridge.update_state(type_mode=type_btn.is_active)

            say_script = "/home/paul/Work/jarvis/source-code/services/say.sh"
            if type_btn.is_active:
                subprocess.Popen([say_script, "type mode enabled"])
                self.data_bridge.send_log("INFO", "Type Mode: ON - Transcriptions will be typed automatically")
            else:
                subprocess.Popen([say_script, "type mode disabled"])
                self.data_bridge.send_log("INFO", "Type Mode: OFF")
        except Exception as e:
            self.data_bridge.send_log("ERROR", f"Failed to toggle Type Mode: {e}")

    def action_toggle_chat_mode(self) -> None:
        """Action to toggle Chat Mode via keyboard"""
        try:
            chat_btn = self.query_one("#chat-mode-btn", ToggleButton)
            chat_btn.toggle()

            say_script = "/home/paul/Work/jarvis/source-code/services/say.sh"
            if chat_btn.is_active:
                subprocess.Popen([say_script, "chat mode enabled"])
            else:
                subprocess.Popen([say_script, "chat mode disabled"])
        except Exception as e:
            self.data_bridge.send_log("ERROR", f"Failed to toggle Chat Mode: {e}")

    def update_data(self) -> None:
        """Update UI from data bridge (called periodically)"""
        # Get mic widget
        mic = self.query_one("#mic", MicMonitor)

        # Get all pending audio levels (keep only latest)
        latest_audio = None
        while True:
            audio = self.data_bridge.get_audio_level(timeout=0.001)
            if audio is None:
                break
            latest_audio = audio

        if latest_audio:
            # Convert amplitude to percentage (0-100)
            speech_max = 2000.0
            level = min(100, (latest_audio.max_amplitude / speech_max) * 100)
            mic.level = level
            mic.peak = max(mic.peak, level)

        # Get transcription log widget
        trans_log = self.query_one("#transcription", RichLog)

        # Get all pending transcriptions
        while True:
            trans = self.data_bridge.get_transcription(timeout=0.001)
            if trans is None:
                break

            timestamp = trans.timestamp.strftime("%H:%M:%S")
            trans_log.write(f"[#99ddbb][{timestamp}][/#99ddbb] [#e0e0e0]{trans.text}[/#e0e0e0]")
            self.transcription_count += 1

            # Update border title with count
            trans_log.border_title = f"💬 Transcription ({self.transcription_count})"

        # Get system log widget
        sys_log = self.query_one("#logs", RichLog)

        # Get all pending logs
        while True:
            log = self.data_bridge.get_log(timeout=0.001)
            if log is None:
                break

            # Format log with soft pastel colors based on level
            timestamp = log.timestamp.strftime("%H:%M:%S")
            level_colors = {
                "DEBUG": "#b8b8d0",
                "INFO": "#99ccff",
                "WARNING": "#ffcc99",
                "ERROR": "#ff9999",
                "CRITICAL": "#ff9999"
            }
            level_icons = {
                "DEBUG": "🔍",
                "INFO": "ℹ️",
                "WARNING": "⚠️",
                "ERROR": "❌",
                "CRITICAL": "🔥"
            }
            color = level_colors.get(log.level, "#e0e0e0")
            icon = level_icons.get(log.level, "•")
            sys_log.write(f"[{color}]{icon} [{timestamp}] {log.level}: {log.message}[/{color}]")
            self.log_count += 1

            # Update border title with count
            sys_log.border_title = f"📋 System Logs ({self.log_count})"

        # Check for keyboard events (Control key to enable Type Mode)
        self.check_keyboard_events()


class JarvisUI:
    """
    Wrapper class to maintain API compatibility
    Manages the Textual app lifecycle
    """

    def __init__(self, data_bridge: DataBridge, refresh_rate: int = 4, log_history: int = 50):
        """
        Initialize JARVIS UI

        Args:
            data_bridge: DataBridge instance for receiving data
            refresh_rate: UI refresh rate in Hz
            log_history: Not used in Textual version (kept for API compatibility)
        """
        self.app = JarvisApp(data_bridge, refresh_rate)
        self.running = False
        self._shutdown_callback = None

    def set_shutdown_callback(self, callback):
        """Set callback to call when UI quits"""
        self._shutdown_callback = callback

    def show_splash_screen(self) -> None:
        """Show Iron Man ASCII art splash screen for 1 second"""
        import sys
        import time

        splash = """⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⢀⢄⢄⠢⡠⡀⢀⠄⡀⡀⠄⠄⠄⠄⠐⠡⠄⠉⠻⣻⣟⣿⣿⣄⠄⠄⠄⠄⠄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⢠⢣⠣⡎⡪⢂⠊⡜⣔⠰⡐⠠⠄⡾⠄⠈⠠⡁⡂⠄⠔⠸⣻⣿⣿⣯⢂⠄⠄⠄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⠄⡀⠄⠄⠄⠄⠄⠄⠄⠐⢰⡱⣝⢕⡇⡪⢂⢊⢪⢎⢗⠕⢕⢠⣻⠄⠄⠄⠂⠢⠌⡀⠄⠨⢚⢿⣿⣧⢄⠄⠄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⡐⡈⠌⠄⠄⠄⠄⠄⠄⠄⡧⣟⢼⣕⢝⢬⠨⡪⡚⡺⡸⡌⡆⠜⣾⠄⠄⠄⠁⡐⠠⣐⠨⠄⠁⠹⡹⡻⣷⡕⢄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⢄⠇⠂⠄⠄⠄⠄⠄⠄⠄⢸⣻⣕⢗⠵⣍⣖⣕⡼⡼⣕⢭⢮⡆⠱⣽⡇⠄⠄⠂⠁⠄⢁⠢⡁⠄⠄⠐⠈⠺⢽⣳⣄⠄⠄
⠄⠄⠄⠄⠄⢔⢕⢌⠄⠄⠄⠄⠄⢀⠄⠄⣾⢯⢳⠹⠪⡺⡺⣚⢜⣽⣮⣳⡻⡇⡙⣜⡇⠄⠄⢸⠄⠄⠂⡀⢠⠂⠄⢶⠊⢉⡁⠨⡒⠄⠄
⠄⠄⠄⠄⡨⣪⣿⢰⠈⠄⠄⠄⡀⠄⠄⠄⣽⣵⢿⣸⢵⣫⣳⢅⠕⡗⣝⣼⣺⠇⡘⡲⠇⠄⠄⠨⠄⠐⢀⠐⠐⠡⢰⠁⠄⣴⣾⣷⣮⣇⠄
⠄⠄⠄⠄⡮⣷⣿⠪⠄⠄⠄⠠⠄⠂⠠⠄⡿⡞⡇⡟⣺⣺⢷⣿⣱⢕⢵⢺⢼⡁⠪⣘⡇⠄⠄⢨⠄⠐⠄⠄⢀⠄⢸⠄⠄⣿⣿⣿⣿⣿⡆
⠄⠄⠄⢸⣺⣿⣿⣇⠄⠄⠄⠄⢀⣤⣖⢯⣻⡑⢕⢭⢷⣻⣽⡾⣮⡳⡵⣕⣗⡇⠡⡣⣃⠄⠄⠸⠄⠄⠄⠄⠄⠄⠈⠄⠄⢻⣿⣿⣵⡿⣹
⠄⠄⠄⢸⣿⣿⣟⣯⢄⢤⢲⣺⣻⣻⡺⡕⡔⡊⡎⡮⣿⣿⣽⡿⣿⣻⣼⣼⣺⡇⡀⢎⢨⢐⢄⡀⠄⢁⠠⠄⠄⠐⠄⠣⠄⠸⣿⣿⣯⣷⣿
⠄⠄⠄⢸⣿⣿⣿⢽⠲⡑⢕⢵⢱⢪⡳⣕⢇⢕⡕⣟⣽⣽⣿⣿⣿⣿⣿⣿⣿⢗⢜⢜⢬⡳⣝⢸⣢⢀⠄⠄⠐⢀⠄⡀⠆⠄⠸⣿⣿⣿⣿
⠄⠄⠄⢸⣿⣿⣿⢽⣝⢎⡪⡰⡢⡱⡝⡮⡪⡣⣫⢎⣿⣿⣿⣿⣿⣿⠟⠋⠄⢄⠄⠈⠑⠑⠭⡪⡪⢏⠗⡦⡀⠐⠄⠄⠈⠄⠄⠙⣿⣿⣿
⠄⠄⠄⠘⣿⣿⣿⣿⡲⣝⢮⢪⢊⢎⢪⢺⠪⣝⢮⣯⢯⣟⡯⠷⠋⢀⣠⣶⣾⡿⠿⢀⣴⣖⢅⠪⠘⡌⡎⢍⣻⠠⠅⠄⠄⠈⠢⠄⠄⠙⠿
⠄⠄⠄⠄⣿⣿⣿⣿⣽⢺⢍⢎⢎⢪⡪⡮⣪⣿⣞⡟⠛⠋⢁⣠⣶⣿⡿⠛⠋⢀⣤⢾⢿⣕⢇⠡⢁⢑⠪⡳⡏⠄⠄⠄⠄⠄⠄⢑⠤⢀⢠
⠄⠄⠄⠄⢸⣿⣿⣿⣟⣮⡳⣭⢪⡣⡯⡮⠗⠋⠁⠄⠄⠈⠿⠟⠋⣁⣀⣴⣾⣿⣗⡯⡳⡕⡕⡕⡡⢂⠊⢮⠃⠄⠄⠄⠄⠄⢀⠐⠨⢁⠨
⠄⠄⠄⠄⠈⢿⣿⣿⣿⠷⠯⠽⠐⠁⠁⢀⡀⣤⢖⣽⢿⣦⣶⣾⣿⣿⣿⣿⣿⣿⢎⠇⡪⣸⡪⡮⠊⠄⠌⠎⡄⠄⠄⠄⠄⠄⠄⡂⢁⠉⡀
⠄⠄⠄⠄⠄⠈⠛⠚⠒⠵⣶⣶⣶⣶⢪⢃⢇⠏⡳⡕⣝⢽⡽⣻⣿⣿⣿⣿⡿⣺⠰⡱⢜⢮⡟⠁⠄⠄⠅⠅⢂⠐⠄⠐⢀⠄⠄⠄⠂⡁⠂
⠄⠄⠄⠄⠄⠄⠄⠰⠄⠐⢒⣠⣿⣟⢖⠅⠆⢝⢸⡪⡗⡅⡯⣻⣺⢯⡷⡯⡏⡇⡅⡏⣯⡟⠄⠄⠄⠨⡊⢔⢁⠠⠄⠄⠄⠄⠄⢀⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⠄⠹⣿⣿⣿⣿⢿⢕⢇⢣⢸⢐⢇⢯⢪⢪⠢⡣⠣⢱⢑⢑⠰⡸⡸⡇⠁⠄⠄⠠⡱⠨⢘⠄⠂⡀⠂⠄⠄⠄⠄⠈⠂⠄
⠄⠄⠄⠄⠄⠄⠄⠄⠄⢻⣿⣿⣿⣟⣝⢔⢅⠸⡘⢌⠮⡨⡪⠨⡂⠅⡑⡠⢂⢇⢇⢿⠁⠄⢀⠠⠨⡘⢌⡐⡈⠄⠄⠠⠄⠄⠄⠄⠄⠄⠁
⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠹⣿⣿⣿⣯⢢⢊⢌⢂⠢⠑⠔⢌⡂⢎⠔⢔⢌⠎⡎⡮⡃⢀⠐⡐⠨⡐⠌⠄⡑⠄⢂⠐⢀⠄⠄⠈⠄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠙⣿⣿⣿⣯⠂⡀⠔⢔⠡⡹⠰⡑⡅⡕⡱⠰⡑⡜⣜⡅⡢⡈⡢⡑⡢⠁⠰⠄⠨⢀⠐⠄⠄⠄⠄⠄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠈⠻⢿⣿⣷⣢⢱⠡⡊⢌⠌⡪⢨⢘⠜⡌⢆⢕⢢⢇⢆⢪⢢⡑⡅⢁⡖⡄⠄⠄⠄⢀⠄⠄⠄⠄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠛⢿⣿⣵⡝⣜⢐⠕⢌⠢⡑⢌⠌⠆⠅⠑⠑⠑⠝⢜⠌⠠⢯⡚⡜⢕⢄⠄⠁⠄⠄⠄⠄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠙⢿⣷⡣⣇⠃⠅⠁⠈⡠⡠⡔⠜⠜⣿⣗⡖⡦⣰⢹⢸⢸⢸⡘⠌⠄⠄⠄⠄⠄⠄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠈⠋⢍⣠⡤⡆⣎⢇⣇⢧⡳⡍⡆⢿⣯⢯⣞⡮⣗⣝⢎⠇⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠁⣿⣿⣎⢦⠣⠳⠑⠓⠑⠃⠩⠉⠈⠈⠉⠄⠁⠉⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠈⡿⡞⠁⠄⠄⢀⠐⢐⠠⠈⡌⠌⠂⡁⠌⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠈⢂⢂⢀⠡⠄⣈⠠⢄⠡⠒⠈⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄
⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠢⠠⠊⠨⠐⠈⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄⠄"""

        # Clear screen and display splash
        print("\033[2J\033[H", end='')
        print(splash)
        sys.stdout.flush()

        # Wait for 1 second
        time.sleep(1)

        # Clear screen for the terminal UI
        print("\033[2J\033[H", end='')
        sys.stdout.flush()

    def start(self) -> None:
        """Start UI (blocking call - runs in main thread)"""
        if self.running:
            return

        self.running = True

        # Splash screen disabled - it interferes with Textual UI
        # self.show_splash_screen()

        # Textual app.run() is blocking and handles its own event loop
        try:
            self.app.run()
        finally:
            # Call shutdown callback when UI exits
            if self._shutdown_callback:
                self._shutdown_callback()

    def stop(self) -> None:
        """Stop UI"""
        if not self.running:
            return
        self.running = False
        try:
            self.app.exit()
        except Exception:
            pass  # Ignore errors during shutdown


if __name__ == "__main__":
    # Test UI with mock data bridge
    import random
    import threading
    import time
    from .data_bridge import DataBridge

    bridge = DataBridge()

    # Update state
    bridge.update_state(model_loaded=True, mic_active=True)

    # Start mock data generator in background
    def generate_mock_data():
        for i in range(200):
            # Send audio levels
            bridge.send_audio_level(
                max_amp=random.uniform(0, 2500),
                avg_amp=random.uniform(0, 1250)
            )

            # Send transcription occasionally
            if i % 15 == 0:
                bridge.send_transcription(f"Test transcription number {i // 15}")

            # Send logs with varying levels
            levels = ["INFO", "DEBUG", "WARNING", "ERROR"]
            level = random.choice(levels)
            bridge.send_log(level, f"Test {level.lower()} message {i}")

            time.sleep(0.3)

    data_thread = threading.Thread(target=generate_mock_data, daemon=True)
    data_thread.start()

    # Start UI (blocking)
    ui = JarvisUI(bridge, refresh_rate=4)
    ui.start()
