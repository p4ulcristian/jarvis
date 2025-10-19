"""
Audio capture and processing
Handles microphone input with resampling support
"""
import numpy as np
import sounddevice as sd
from typing import Optional, Callable
import logging
import queue
import threading

from .config import Config
from .retry import exponential_backoff, RetryExhausted

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

        # Error recovery configuration
        self.max_retries = config.audio_capture_max_retries if config.enable_error_recovery else 0
        self.retry_delay = config.audio_capture_retry_delay
        self.consecutive_failures = 0

        # Streaming mode components
        self.stream = None
        self.audio_queue = queue.Queue(maxsize=100)  # Buffer up to 100 chunks (~10 seconds)
        self.is_streaming = False
        self.stream_lock = threading.Lock()

        logger.info(f"Audio initialized: {self.device_sample_rate}Hz -> {self.target_sample_rate}Hz")
        if config.enable_error_recovery:
            logger.info(f"Error recovery enabled: max_retries={self.max_retries}, delay={self.retry_delay}s")

    def capture_chunk(self, duration_sec: Optional[float] = None) -> Optional[np.ndarray]:
        """
        Capture a single audio chunk with retry logic

        Args:
            duration_sec: Optional duration override (uses chunk_size if not specified)

        Returns:
            Audio data as float32 numpy array, or None on error
        """
        def _do_capture() -> np.ndarray:
            """Internal capture function for retry logic"""
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

        # Try capture with retry logic if enabled
        if self.max_retries > 0:
            try:
                result = exponential_backoff(
                    _do_capture,
                    max_retries=self.max_retries,
                    initial_delay=self.retry_delay,
                    max_delay=10.0,
                    exponential_base=2.0,
                    exceptions=(Exception,)
                )
                # Success - reset failure counter
                if self.consecutive_failures > 0:
                    logger.info("Audio capture recovered after failures")
                    self.consecutive_failures = 0
                return result
            except RetryExhausted:
                self.consecutive_failures += 1
                logger.error(
                    f"Audio capture failed after {self.max_retries} retries "
                    f"(consecutive failures: {self.consecutive_failures})"
                )
                return None
            except Exception as e:
                logger.error(f"Unexpected audio capture error: {e}", exc_info=True)
                return None
        else:
            # No retry - single attempt
            try:
                return _do_capture()
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

    def start_stream(self) -> bool:
        """
        Start continuous audio streaming (zero-gap capture)

        Audio is captured in a background thread and placed in a queue.
        Use get_chunk() to retrieve chunks for processing.

        Returns:
            True if started successfully, False otherwise
        """
        with self.stream_lock:
            if self.is_streaming:
                logger.warning("Stream already running")
                return True

            try:
                # Calculate device chunk size
                device_chunk_size = int(self.chunk_size * self.device_sample_rate / self.target_sample_rate)

                # Create input stream with callback
                self.stream = sd.InputStream(
                    samplerate=self.device_sample_rate,
                    channels=self.channels,
                    dtype='int16',
                    blocksize=device_chunk_size,
                    callback=self._audio_callback
                )

                # Start the stream
                self.stream.start()
                self.is_streaming = True
                logger.info(f"Continuous audio stream started (chunk={self.chunk_size} samples, {self.chunk_size/self.target_sample_rate*1000:.1f}ms)")
                return True

            except Exception as e:
                logger.error(f"Failed to start audio stream: {e}", exc_info=True)
                self.stream = None
                self.is_streaming = False
                return False

    def get_chunk(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        Get next audio chunk from streaming queue

        Args:
            timeout: Maximum time to wait for a chunk (seconds)

        Returns:
            Audio chunk as float32 array, or None if timeout/error
        """
        if not self.is_streaming:
            logger.error("Stream not running - call start_stream() first")
            return None

        try:
            # Get chunk from queue (blocks until available or timeout)
            chunk = self.audio_queue.get(timeout=timeout)
            return chunk
        except queue.Empty:
            logger.warning(f"No audio chunk available after {timeout}s timeout")
            return None
        except Exception as e:
            logger.error(f"Error getting audio chunk: {e}")
            return None

    def stop_stream(self) -> None:
        """Stop continuous audio streaming"""
        with self.stream_lock:
            if not self.is_streaming:
                return

            try:
                if self.stream:
                    self.stream.stop()
                    self.stream.close()
                    self.stream = None

                self.is_streaming = False

                # Clear the queue
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                    except queue.Empty:
                        break

                logger.info("Audio stream stopped")

            except Exception as e:
                logger.error(f"Error stopping stream: {e}", exc_info=True)

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """
        Audio callback - runs in separate thread

        This is called by sounddevice whenever new audio is available.
        Processes and queues audio chunks for the main loop.

        Args:
            indata: Input audio data from microphone
            frames: Number of frames
            time_info: Timing information
            status: Status flags
        """
        try:
            # Log any status issues
            if status:
                logger.warning(f"Audio callback status: {status}")

            # Convert from (N,1) to (N,) and copy data
            audio_np = indata.flatten().copy()

            # Resample if needed
            if self.needs_resampling:
                audio_np = self._resample(audio_np)

            # Convert to float32
            audio_float = audio_np.astype(np.float32) / 32768.0

            # Put in queue (non-blocking - drop if full)
            try:
                self.audio_queue.put_nowait(audio_float)
            except queue.Full:
                logger.warning("Audio queue full - dropping chunk (processing too slow)")

        except Exception as e:
            # Never let exceptions crash the audio thread
            logger.error(f"Error in audio callback: {e}", exc_info=True)

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
