#!/usr/bin/env python3
"""
JARVIS Terminal UI
Production-ready dashboard-style terminal interface
"""

import time
import threading
from datetime import datetime
from typing import Optional, List
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.console import RenderableType

from .data_bridge import DataBridge, SystemLog


class JarvisUI:
    """
    Terminal UI for JARVIS
    Displays real-time audio levels, transcriptions, and system logs
    """

    def __init__(self, data_bridge: DataBridge, refresh_rate: int = 4, log_history: int = 50):
        """
        Initialize JARVIS UI

        Args:
            data_bridge: DataBridge instance for receiving data
            refresh_rate: UI refresh rate in Hz
            log_history: Number of log entries to keep
        """
        self.console = Console()
        self.data_bridge = data_bridge
        self.refresh_rate = refresh_rate
        self.log_history = log_history

        # State
        self.logs: List[str] = []
        self.transcriptions: List[str] = []
        self.current_mic_level: float = 0.0
        self.peak_mic_level: float = 0.0
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start UI in background thread"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_ui, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        """Stop UI"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def _update_from_bridge(self) -> None:
        """Update UI state from data bridge"""
        # Get all pending audio levels (keep only latest)
        latest_audio = None
        while True:
            audio = self.data_bridge.get_audio_level(timeout=0.001)
            if audio is None:
                break
            latest_audio = audio

        if latest_audio:
            # Convert amplitude to percentage (0-100)
            # Use a lower threshold for more sensitive visualization
            # Typical speech is around 500-2000 amplitude range
            speech_max = 2000.0
            self.current_mic_level = min(100, (latest_audio.max_amplitude / speech_max) * 100)
            self.peak_mic_level = max(self.peak_mic_level, self.current_mic_level)

        # Get all pending transcriptions
        while True:
            trans = self.data_bridge.get_transcription(timeout=0.001)
            if trans is None:
                break

            timestamp = trans.timestamp.strftime("%H:%M:%S")
            formatted = f"[{timestamp}] {trans.text}"
            self.transcriptions.append(formatted)

            # Keep last N transcriptions
            if len(self.transcriptions) > self.log_history:
                self.transcriptions = self.transcriptions[-self.log_history:]

        # Get all pending logs
        while True:
            log = self.data_bridge.get_log(timeout=0.001)
            if log is None:
                break

            # Format log with color based on level
            timestamp = log.timestamp.strftime("%H:%M:%S")
            level_colors = {
                "DEBUG": "dim",
                "INFO": "white",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold red"
            }
            color = level_colors.get(log.level, "white")
            formatted = f"[{color}][{timestamp}] {log.level}: {log.message}[/{color}]"
            self.logs.append(formatted)

            # Keep last N logs
            if len(self.logs) > self.log_history:
                self.logs = self.logs[-self.log_history:]

    def create_title_panel(self) -> Panel:
        """Create the JARVIS title panel"""
        # Simple compact title
        title = Text("J A R V I S", style="bold cyan", justify="center")

        return Panel(
            title,
            style="bold blue",
            border_style="cyan",
            padding=(0, 1)
        )

    def create_transcription_panel(self) -> Panel:
        """Create the transcription/chat panel"""
        if self.transcriptions:
            # Show only the most recent 15 transcriptions that will fit
            # This ensures the newest ones are always visible at the bottom
            recent = self.transcriptions[-15:]
            content = "\n".join(recent)
        else:
            content = "[dim]Waiting for speech...[/dim]"

        return Panel(
            content,
            title=f"[bold white]Transcription ({len(self.transcriptions)} total)[/bold white]",
            border_style="green",
            padding=(1, 2)
        )

    def create_mic_panel(self) -> Panel:
        """Create the microphone activity panel"""
        level = self.current_mic_level

        # Create a visual bar (20 characters wide to fit better)
        bar_length = 20
        filled = int((level / 100) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        # Color based on level
        if level > 70:
            color = "red"
            status_text = "LOUD"
            status_color = "bold red"
        elif level > 40:
            color = "yellow"
            status_text = "ACTIVE"
            status_color = "bold yellow"
        elif level > 10:
            color = "green"
            status_text = "SPEAKING"
            status_color = "bold green"
        else:
            color = "dim white"
            status_text = "QUIET"
            status_color = "dim"

        content = Text()
        content.append(bar, style=color)
        content.append("\n\n")
        content.append(f"{level:.0f}%", style="bold white")
        content.append(f" / ", style="dim")
        content.append(f"{self.peak_mic_level:.0f}%", style="dim")
        content.append(f"\n\n")
        content.append(f"{status_text}", style=status_color)

        return Panel(
            content,
            title="[bold white]Mic[/bold white]",
            border_style="magenta",
            padding=(1, 1)
        )

    def create_logs_panel(self) -> Panel:
        """Create the system logs panel"""
        if self.logs:
            # Show last 20 logs for better scrolling visibility
            content = "\n".join(self.logs[-20:])
        else:
            content = "[dim]No system logs yet...[/dim]"

        return Panel(
            content,
            title=f"[bold white]System Logs ({len(self.logs)} total)[/bold white]",
            border_style="blue",
            padding=(1, 2)
        )

    def create_layout(self) -> Layout:
        """Create the dashboard layout"""
        layout = Layout()

        # Split into header and body
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body")
        )

        # Split body into top row (transcription | mic) and bottom row (logs)
        layout["body"].split_column(
            Layout(name="top_row", ratio=1),
            Layout(name="bottom_row", ratio=1)
        )

        # Split top row into transcription (left, 80%) and mic (right, 20%)
        layout["top_row"].split_row(
            Layout(name="transcription", ratio=4),
            Layout(name="mic", ratio=1, minimum_size=30)
        )

        # Populate panels
        layout["header"].update(self.create_title_panel())
        layout["transcription"].update(self.create_transcription_panel())
        layout["mic"].update(self.create_mic_panel())
        layout["bottom_row"].update(self.create_logs_panel())

        return layout

    def _run_ui(self) -> None:
        """Run the UI with live updates (runs in background thread)"""
        try:
            with Live(
                self.create_layout(),
                refresh_per_second=self.refresh_rate,
                console=self.console,
                screen=True
            ) as live:
                while self.running:
                    # Update state from data bridge
                    self._update_from_bridge()

                    # Update display
                    live.update(self.create_layout())

                    # Sleep based on refresh rate
                    time.sleep(1.0 / self.refresh_rate)

        except KeyboardInterrupt:
            pass
        except Exception as e:
            # Log error but don't crash
            self.console.print(f"\n[bold red]UI Error: {e}[/bold red]")
        finally:
            self.running = False


if __name__ == "__main__":
    # Test UI with mock data bridge
    from .data_bridge import DataBridge
    import random

    bridge = DataBridge()
    ui = JarvisUI(bridge, refresh_rate=4)

    # Update state
    bridge.update_state(model_loaded=True, mic_active=True)

    # Start UI
    ui.start()

    # Send some test data
    try:
        for i in range(100):
            # Send audio levels
            bridge.send_audio_level(
                max_amp=random.uniform(0, 32768),
                avg_amp=random.uniform(0, 16384)
            )

            # Send transcription occasionally
            if i % 10 == 0:
                bridge.send_transcription(f"Test transcription {i // 10}")

            # Send logs
            bridge.send_log("INFO", f"Test log message {i}")

            time.sleep(0.5)
    except KeyboardInterrupt:
        ui.stop()
