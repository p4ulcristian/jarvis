"""
Audio capture and processing
Handles microphone input with resampling support
"""
import numpy as np
import sounddevice as sd
from typing import Optional, Callable
import logging

from .config import Config

logger = logging.getLogger(__name__)


class AudioCapture:
    """
    Manages audio capture from microphone
    Handles resampling and streaming
    """

    def __init__(self, config: Config):
        """
        Initialize audio capture

        Args:
            config: Configuration object
        """
        self.config = config
        self.device_sample_rate = config.device_sample_rate
        self.target_sample_rate = config.sample_rate
        self.chunk_size = config.chunk_size
        self.channels = config.channels
        self.needs_resampling = (self.device_sample_rate != self.target_sample_rate)

        logger.info(f"Audio initialized: {self.device_sample_rate}Hz -> {self.target_sample_rate}Hz")

    def capture_chunk(self, duration_sec: Optional[float] = None) -> Optional[np.ndarray]:
        """
        Capture a single audio chunk

        Args:
            duration_sec: Optional duration override (uses chunk_size if not specified)

        Returns:
            Audio data as float32 numpy array, or None on error
        """
        try:
            if duration_sec:
                device_chunk_size = int(duration_sec * self.device_sample_rate)
            else:
                device_chunk_size = int(self.chunk_size * self.device_sample_rate / self.target_sample_rate)

            # Capture audio using sounddevice (returns numpy array directly)
            audio_np = sd.rec(
                device_chunk_size,
                samplerate=self.device_sample_rate,
                channels=self.channels,
                dtype='int16',
                blocking=True
            )
            audio_np = audio_np.flatten()  # Convert from (N,1) to (N,)

            # Resample if needed
            if self.needs_resampling:
                audio_np = self._resample(audio_np)

            # Convert to float32
            audio_float = audio_np.astype(np.float32) / 32768.0

            return audio_float

        except Exception as e:
            logger.error(f"Audio capture failed: {e}")
            return None

    def stream(self, callback: Callable[[np.ndarray], None]) -> None:
        """
        Stream audio continuously and call callback for each chunk

        Args:
            callback: Function to call with each audio chunk
        """
        logger.info("Starting audio stream...")

        device_chunk_size = int(self.chunk_size * self.device_sample_rate / self.target_sample_rate)

        try:
            while True:
                # Capture chunk
                audio_np = sd.rec(
                    device_chunk_size,
                    samplerate=self.device_sample_rate,
                    channels=self.channels,
                    dtype='int16',
                    blocking=True
                )
                audio_np = audio_np.flatten()

                # Resample if needed
                if self.needs_resampling:
                    audio_np = self._resample(audio_np)

                # Convert to float32
                audio_float = audio_np.astype(np.float32) / 32768.0

                # Call callback
                callback(audio_float)

        except KeyboardInterrupt:
            logger.info("Audio stream stopped by user")
        except Exception as e:
            logger.error(f"Audio stream error: {e}")

    def _resample(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Resample audio using simple decimation

        Args:
            audio_data: Input audio array

        Returns:
            Resampled audio array
        """
        if len(audio_data) == 0:
            return audio_data

        # For 48kHz -> 16kHz, take every 3rd sample
        if self.device_sample_rate == 48000 and self.target_sample_rate == 16000:
            return audio_data[::3]

        # General case: stride-based decimation
        stride = int(self.device_sample_rate / self.target_sample_rate)
        if stride > 1:
            return audio_data[::stride]

        return audio_data

    @staticmethod
    def calculate_energy(audio: np.ndarray) -> tuple[float, float]:
        """
        Calculate audio energy metrics

        Args:
            audio: Audio data as float32 array

        Returns:
            Tuple of (max_amplitude, avg_amplitude)
        """
        # Convert to int16 range for amplitude check
        audio_int16 = (audio * 32768).astype(np.int16)
        amplitude = np.abs(audio_int16)

        max_amp = float(np.max(amplitude))
        avg_amp = float(np.mean(amplitude))

        return max_amp, avg_amp
