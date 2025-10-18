"""
Data Bridge for JARVIS UI
Thread-safe communication between JARVIS core and UI
"""
import threading
import queue
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AudioLevel:
    """Audio level data"""
    max_amplitude: float
    avg_amplitude: float
    timestamp: datetime


@dataclass
class TranscriptionData:
    """Transcription text data"""
    text: str
    timestamp: datetime


@dataclass
class SystemLog:
    """System log entry"""
    level: str  # INFO, WARNING, ERROR, DEBUG
    message: str
    timestamp: datetime


@dataclass
class SystemState:
    """System state information"""
    model_loaded: bool
    mic_active: bool
    processing: bool
    error: Optional[str]


class DataBridge:
    """
    Thread-safe data bridge between JARVIS core and UI
    Uses queues for async communication
    """

    def __init__(self, max_queue_size: int = 1000):
        """
        Initialize data bridge

        Args:
            max_queue_size: Maximum size for each queue
        """
        # Queues for different data types
        self.audio_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self.transcription_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self.log_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)

        # State (thread-safe with lock)
        self._state_lock = threading.Lock()
        self._state = SystemState(
            model_loaded=False,
            mic_active=False,
            processing=False,
            error=None
        )

    # Audio Level Methods
    def send_audio_level(self, max_amp: float, avg_amp: float) -> None:
        """
        Send audio level data to UI

        Args:
            max_amp: Maximum amplitude
            avg_amp: Average amplitude
        """
        try:
            data = AudioLevel(
                max_amplitude=max_amp,
                avg_amplitude=avg_amp,
                timestamp=datetime.now()
            )
            self.audio_queue.put_nowait(data)
        except queue.Full:
            pass  # Drop if queue is full

    def get_audio_level(self, timeout: float = 0.01) -> Optional[AudioLevel]:
        """
        Get latest audio level (non-blocking)

        Args:
            timeout: Timeout in seconds

        Returns:
            AudioLevel or None
        """
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # Transcription Methods
    def send_transcription(self, text: str) -> None:
        """
        Send transcription text to UI

        Args:
            text: Transcribed text
        """
        try:
            data = TranscriptionData(
                text=text,
                timestamp=datetime.now()
            )
            self.transcription_queue.put_nowait(data)
        except queue.Full:
            pass  # Drop if queue is full

    def get_transcription(self, timeout: float = 0.01) -> Optional[TranscriptionData]:
        """
        Get latest transcription (non-blocking)

        Args:
            timeout: Timeout in seconds

        Returns:
            TranscriptionData or None
        """
        try:
            return self.transcription_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # System Log Methods
    def send_log(self, level: str, message: str) -> None:
        """
        Send system log to UI

        Args:
            level: Log level (INFO, WARNING, ERROR, DEBUG)
            message: Log message
        """
        try:
            data = SystemLog(
                level=level,
                message=message,
                timestamp=datetime.now()
            )
            self.log_queue.put_nowait(data)
        except queue.Full:
            pass  # Drop if queue is full

    def get_log(self, timeout: float = 0.01) -> Optional[SystemLog]:
        """
        Get latest log entry (non-blocking)

        Args:
            timeout: Timeout in seconds

        Returns:
            SystemLog or None
        """
        try:
            return self.log_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # System State Methods
    def update_state(self, **kwargs) -> None:
        """
        Update system state

        Args:
            **kwargs: State fields to update (model_loaded, mic_active, processing, error)
        """
        with self._state_lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)

    def get_state(self) -> SystemState:
        """
        Get current system state (thread-safe copy)

        Returns:
            SystemState object
        """
        with self._state_lock:
            return SystemState(
                model_loaded=self._state.model_loaded,
                mic_active=self._state.mic_active,
                processing=self._state.processing,
                error=self._state.error
            )


class UILogHandler(logging.Handler):
    """
    Custom logging handler that sends logs to DataBridge
    """

    def __init__(self, data_bridge: DataBridge):
        """
        Initialize handler

        Args:
            data_bridge: DataBridge instance
        """
        super().__init__()
        self.data_bridge = data_bridge

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to the data bridge

        Args:
            record: Log record
        """
        try:
            # Format the message
            msg = self.format(record)

            # Send to bridge
            self.data_bridge.send_log(
                level=record.levelname,
                message=msg
            )
        except Exception:
            # Don't let logging errors crash the app
            pass
