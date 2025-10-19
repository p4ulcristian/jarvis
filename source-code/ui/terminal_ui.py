#!/usr/bin/env python3
"""
JARVIS Terminal UI
Interactive dashboard using Textual framework with scrollable elements
Pip-Boy inspired green monochrome theme - retro-futuristic CRT aesthetic

Text Selection:
  - In most terminals: Hold Shift while dragging mouse to select text
  - Export logs: Press 'e' to export all logs to ~/jarvis_exports/
  - Terminal-specific: Some terminals may use different modifiers (Alt, Ctrl+Shift)
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
    """Widget to display microphone activity level and PTT status"""

    level = reactive(0.0)
    peak = reactive(0.0)
    ptt_active = reactive(False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "[MIC] Audio + Status"

    def render(self) -> Text:
        """Render the mic level display and PTT status"""
        level = self.level

        # Compact vertical bar meter (5 segments)
        segments = 5
        filled_segments = int((level / 100) * segments)

        # Build vertical meter from top to bottom
        content = Text()

        # Green monochrome colors based on level (amber for warnings)
        if level > 70:
            bar_color = "#ffaa00"  # amber warning
            status_text = "LOUD"
            status_color = "#ffaa00"
            icon = "[!]"
        elif level > 40:
            bar_color = "#00ff00"  # bright green
            status_text = "ACTV"
            status_color = "#00ff00"
            icon = "[*]"
        elif level > 10:
            bar_color = "#33ff33"  # lighter green
            status_text = "TALK"
            status_color = "#33ff33"
            icon = "[>]"
        else:
            bar_color = "#226622"  # dim green
            status_text = "IDLE"
            status_color = "#226622"
            icon = "[-]"

        # Draw compact vertical bars (from top to bottom)
        for i in range(segments, 0, -1):
            if i <= filled_segments:
                # Filled segment
                if i > 3:
                    content.append("█████ ", style=bar_color)
                else:
                    content.append("█████ ", style="#00ff00")
                content.append(f"{i*20}%\n", style="#226622")
            else:
                # Empty segment
                content.append("▒▒▒▒▒ ", style="#226622")
                content.append(f"{i*20}%\n", style="#226622")

        content.append(f"{icon} {status_text} ", style=status_color)
        content.append(f"P:{self.peak:.0f}%\n\n", style="#226622")

        # Add PTT status
        content.append("Type Mode: ", style="#33ff33")
        if self.ptt_active:
            content.append("ON ●", style="bold #00ff00")
        else:
            content.append("OFF", style="#226622")

        return content


class ChatWindow(Static):
    """Widget to display chat conversation"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "[</>] Chat"
        self.chat_log = None

    def compose(self) -> ComposeResult:
        """Create chat log widget"""
        self.chat_log = RichLog(
            highlight=True,
            markup=True,
            wrap=True
        )
        yield self.chat_log

    def add_message(self, role: str, text: str, timestamp: datetime, backend: Optional[str] = None):
        """Add a message to the chat window"""
        if not self.chat_log:
            return

        time_str = timestamp.strftime("%H:%M:%S")

        if role == "user":
            # User messages in bright green
            self.chat_log.write(f"[#00ff00][{time_str}] YOU:[/#00ff00] [#33ff33]{text}[/#33ff33]")
        elif role == "jarvis":
            # Jarvis messages with backend indicator
            backend_indicator = ""
            if backend == "claude_code":
                backend_indicator = " [#ffaa00]<CODE>[/#ffaa00]"
            elif backend == "ollama":
                backend_indicator = " [#33ff33]<AI>[/#33ff33]"

            self.chat_log.write(f"[#00ff00][{time_str}] JARVIS{backend_indicator}:[/#00ff00] [#33ff33]{text}[/#33ff33]")


class JarvisApp(App):
    """Textual App for JARVIS Dashboard"""

    # Keyboard shortcuts
    # Note: Ctrl key alone is handled by keyboard_listener.py
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("e", "export_logs", "Export Logs"),
    ]

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 4;
        grid-rows: 2 1fr 1fr 1;
        background: #0a0e0a;
    }

    #header {
        column-span: 2;
        height: 2;
        layout: horizontal;
        background: #0d1409;
        border: heavy #00ff00;
    }

    #title {
        width: 1fr;
        content-align: center middle;
        text-style: bold;
        color: #00ff00;
        background: #0d1409;
        text-align: center;
        text-opacity: 95%;
    }

    /* Top Left: Transcription */
    #transcription {
        column-span: 1;
        row-span: 1;
        border: heavy #00ff00;
        border-title-color: #33ff33;
        border-subtitle-color: #226622;
        background: #0d1409;
        height: 100%;
    }

    /* Top Right: Chat Window */
    #chat {
        column-span: 1;
        row-span: 1;
        border: heavy #00ff00;
        border-title-color: #33ff33;
        background: #0d1409;
        height: 100%;
    }

    ChatWindow RichLog {
        border: none;
        background: #0d1409;
    }

    /* Bottom Left: System Logs */
    #logs {
        column-span: 1;
        row-span: 1;
        border: heavy #00ff00;
        border-title-color: #33ff33;
        background: #0d1409;
        height: 100%;
    }

    /* Bottom Right: Audio Levels + Status */
    #audio-status {
        column-span: 1;
        row-span: 1;
        border: heavy #00ff00;
        border-title-color: #33ff33;
        background: #0d1409;
        height: 100%;
        padding: 1;
    }

    Footer {
        column-span: 2;
        background: #0d1409;
        color: #33ff33;
    }

    RichLog {
        scrollbar-gutter: stable;
        scrollbar-background: #0d1409;
        scrollbar-color: #00ff00;
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
        """Create child widgets for 4-quadrant layout"""
        # Header with title
        with Container(id="header"):
            yield Static("[:: J A R V I S ::]", id="title")

        # Top Left: Transcription log (scrollable)
        transcription_log = RichLog(
            highlight=True,
            markup=True,
            id="transcription"
        )
        transcription_log.border_title = "[>>] Transcription"
        transcription_log.border_subtitle = "select: shift+mouse | export: e"
        yield transcription_log

        # Top Right: Chat window (scrollable)
        yield ChatWindow(id="chat")

        # Bottom Left: System logs (scrollable)
        system_log = RichLog(
            highlight=True,
            markup=True,
            id="logs"
        )
        system_log.border_title = "[==] System Logs"
        system_log.border_subtitle = "export: e"
        yield system_log

        # Bottom Right: Audio levels + compact status
        yield MicMonitor(id="audio-status")

        # Footer
        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts"""
        # Start the data update loop
        self.set_interval(1.0 / self.refresh_rate, self.update_data)

        # Add initial messages with Pip-Boy green colors
        trans_log = self.query_one("#transcription", RichLog)
        trans_log.write("[#33ff33][>>] Ready to listen...[/#33ff33]")

        sys_log = self.query_one("#logs", RichLog)
        sys_log.write("[#00ff00][==] System initialized[/#00ff00]")

        # Initialize chat window
        chat_widget = self.query_one("#chat", ChatWindow)
        if chat_widget.chat_log:
            chat_widget.chat_log.write("[#33ff33][</>] Chat mode ready - say 'Jarvis' to start...[/#33ff33]")

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

                    # Check for Push-to-Talk start
                    if key_name == 'PTT_START':
                        # Update state in data bridge
                        self.data_bridge.update_state(ptt_active=True)
                        self.data_bridge.send_log("INFO", "⌨️  Type Mode Active (transcriptions will be typed on release)")

                    # Check for Push-to-Talk stop (transcribe and type)
                    elif key_name == 'PTT_STOP':
                        # Update state in data bridge
                        self.data_bridge.update_state(ptt_active=False)
                        self.data_bridge.send_log("INFO", "⏸️  Type Mode: Typing transcription...")

                    # Check for Push-to-Talk cancel (Ctrl+key combo)
                    elif key_name == 'PTT_CANCEL':
                        # Update state in data bridge
                        self.data_bridge.update_state(ptt_active=False)
                        self.data_bridge.send_log("INFO", "❌ Type Mode cancelled (keyboard combo detected)")


        except Exception as e:
            # Silently ignore errors to not disrupt UI
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses (currently no buttons in UI)"""
        pass

    def action_toggle_type_mode(self) -> None:
        """Action to toggle Type Mode via keyboard (deprecated - PTT is always auto-type)"""
        pass

    def action_toggle_chat_mode(self) -> None:
        """Action to toggle Chat Mode via keyboard (deprecated)"""
        pass

    def action_export_logs(self) -> None:
        """Export transcriptions and system logs to a file"""
        import os

        # Create exports directory if it doesn't exist
        export_dir = os.path.expanduser("~/jarvis_exports")
        os.makedirs(export_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = os.path.join(export_dir, f"jarvis_logs_{timestamp}.txt")

        try:
            # Get the log widgets
            trans_log = self.query_one("#transcription", RichLog)
            sys_log = self.query_one("#logs", RichLog)

            with open(export_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("JARVIS EXPORT\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")

                # Export transcriptions
                f.write("TRANSCRIPTIONS\n")
                f.write("-" * 80 + "\n")
                # Get text content from RichLog
                for line in trans_log.lines:
                    # Convert Rich text to plain text
                    f.write(line.text + "\n")
                f.write("\n\n")

                # Export system logs
                f.write("SYSTEM LOGS\n")
                f.write("-" * 80 + "\n")
                for line in sys_log.lines:
                    # Convert Rich text to plain text
                    f.write(line.text + "\n")

            # Show success message in system log
            self.data_bridge.send_log("INFO", f"Logs exported to: {export_file}")

        except Exception as e:
            # Show error message
            self.data_bridge.send_log("ERROR", f"Export failed: {str(e)}")

    def update_data(self) -> None:
        """Update UI from data bridge (called periodically)"""
        # Get mic/audio widget
        mic = self.query_one("#audio-status", MicMonitor)

        # Update PTT status from state
        state = self.data_bridge.get_state()
        mic.ptt_active = state.ptt_active

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
            trans_log.write(f"[#33ff33][{timestamp}][/#33ff33] [#00ff00]{trans.text}[/#00ff00]")
            self.transcription_count += 1

            # Update border title with count
            trans_log.border_title = f"[>>] Transcription ({self.transcription_count})"

        # Get system log widget
        sys_log = self.query_one("#logs", RichLog)

        # Get all pending logs
        while True:
            log = self.data_bridge.get_log(timeout=0.001)
            if log is None:
                break

            # Format log with Pip-Boy green monochrome (amber for warnings/errors)
            timestamp = log.timestamp.strftime("%H:%M:%S")
            level_colors = {
                "DEBUG": "#226622",
                "INFO": "#00ff00",
                "WARNING": "#ffaa00",
                "ERROR": "#ffaa00",
                "CRITICAL": "#ff6600"
            }
            level_icons = {
                "DEBUG": "[?]",
                "INFO": "[i]",
                "WARNING": "[!]",
                "ERROR": "[X]",
                "CRITICAL": "[!!]"
            }
            color = level_colors.get(log.level, "#33ff33")
            icon = level_icons.get(log.level, "[·]")
            sys_log.write(f"[{color}]{icon} [{timestamp}] {log.level}: {log.message}[/{color}]")
            self.log_count += 1

            # Update border title with count
            sys_log.border_title = f"[==] System Logs ({self.log_count})"

        # Get chat window widget
        chat_widget = self.query_one("#chat", ChatWindow)

        # Get all pending chat messages
        chat_count = 0
        while True:
            chat = self.data_bridge.get_chat_message(timeout=0.001)
            if chat is None:
                break

            # Add message to chat window
            chat_widget.add_message(
                role=chat.role,
                text=chat.text,
                timestamp=chat.timestamp,
                backend=chat.backend
            )
            chat_count += 1

        # Update chat border title if messages were added
        if chat_count > 0:
            total_messages = len(chat_widget.chat_log.lines) if chat_widget.chat_log else 0
            chat_widget.border_title = f"[</>] Chat ({total_messages})"

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
