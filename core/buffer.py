"""
Buffer management for transcriptions
Handles rolling buffers with time-based expiration
"""
import time
from collections import deque
from typing import Optional


class RollingBuffer:
    """
    Rolling buffer for text with time-based expiration
    Used for AI detection and context management
    """

    def __init__(self, max_duration: int = 300):
        """
        Initialize rolling buffer

        Args:
            max_duration: Maximum duration to keep entries (seconds)
        """
        self.buffer = deque()
        self.max_duration = max_duration

    def add(self, text: str) -> None:
        """
        Add text to buffer with timestamp

        Args:
            text: Text to add
        """
        self.buffer.append({
            'text': text,
            'timestamp': time.time()
        })
        self._clean()

    def get_text(self) -> str:
        """
        Get all text in buffer as single string

        Returns:
            Concatenated text from buffer
        """
        self._clean()
        return ' '.join(entry['text'] for entry in self.buffer)

    def get_recent(self, seconds: int) -> str:
        """
        Get text from last N seconds

        Args:
            seconds: Number of seconds to look back

        Returns:
            Concatenated text from recent entries
        """
        self._clean()
        cutoff = time.time() - seconds
        recent = [
            entry['text']
            for entry in self.buffer
            if entry['timestamp'] >= cutoff
        ]
        return ' '.join(recent)

    def clear(self) -> None:
        """Clear all entries from buffer"""
        self.buffer.clear()

    def is_empty(self) -> bool:
        """Check if buffer is empty"""
        self._clean()
        return len(self.buffer) == 0

    def _clean(self) -> None:
        """Remove expired entries"""
        cutoff = time.time() - self.max_duration
        while self.buffer and self.buffer[0]['timestamp'] < cutoff:
            self.buffer.popleft()

    def __len__(self) -> int:
        """Get number of entries in buffer"""
        self._clean()
        return len(self.buffer)

    def __repr__(self) -> str:
        """String representation"""
        return f"RollingBuffer(entries={len(self)}, duration={self.max_duration}s)"
