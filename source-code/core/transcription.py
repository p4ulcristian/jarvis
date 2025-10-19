"""
ASR Transcription with NVIDIA Canary-1B Flash
Real-time transcription with state-of-the-art accuracy (1000+ RTFx)
"""
import os
import sys
import time
import logging
import warnings
from pathlib import Path
from typing import Optional, Tuple
import re

# Suppress NeMo/PyTorch logging BEFORE importing (prevents stdout interference with TUI)
os.environ['HYDRA_FULL_ERROR'] = '0'  # Suppress Hydra verbose errors
os.environ['NEMO_LOG_LEVEL'] = 'ERROR'  # Set NeMo log level

# Comprehensive NeMo logger suppression (catches runtime loggers too)
_nemo_loggers = [
    'nemo_logger',
    'nemo',
    'nemo.collections',
    'nemo.core',
    'nemo.utils',
    'nemo.collections.asr',
    'nemo.collections.common',
    'lhotse',  # NeMo's data loading library
    'pytorch_lightning',
    'torch',
    'lightning',
    'lightning_fabric',
    'hydra',
    'omegaconf',
]
for logger_name in _nemo_loggers:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)
    logging.getLogger(logger_name).propagate = False

# Also suppress the root logger's StreamHandlers to catch any stragglers
_root_logger = logging.getLogger()
for handler in _root_logger.handlers[:]:
    if isinstance(handler, logging.StreamHandler) and handler.stream in (sys.stdout, sys.stderr):
        _root_logger.removeHandler(handler)

# Suppress Python warnings from NeMo/Lhotse/Hydra/OmegaConf
warnings.filterwarnings('ignore', category=UserWarning, module='nemo')
warnings.filterwarnings('ignore', category=UserWarning, module='lhotse')
warnings.filterwarnings('ignore', category=UserWarning, module='hydra')
warnings.filterwarnings('ignore', category=UserWarning, module='omegaconf')
warnings.filterwarnings('ignore', category=FutureWarning, module='nemo')
warnings.filterwarnings('ignore', category=FutureWarning, module='lhotse')
warnings.filterwarnings('ignore', category=FutureWarning, module='hydra')
warnings.filterwarnings('ignore', category=FutureWarning, module='omegaconf')

import numpy as np
import torch
import nemo.collections.asr as nemo_asr
from nemo.collections.asr.models import EncDecMultiTaskModel

from .config import Config
from .constants import (
    HALLUCINATION_PHRASES,
    WORD_CORRECTIONS,
    MIN_TEXT_LENGTH,
    MAX_CHAR_REPEATS,
    MAX_CHUNK_DURATION_SECONDS,
    MIN_BUFFER_DURATION,
    MAX_BUFFER_DURATION,
    SILENCE_CHUNKS_TO_FLUSH
)
from .retry import exponential_backoff, RetryExhausted
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def suppress_nemo_output():
    """
    Context manager to suppress NeMo output by temporarily disabling loggers
    Simpler and safer than stream redirection - avoids I/O issues

    Only suppresses during quick operations (not model loading)
    """
    # Save original warning filters
    original_filters = warnings.filters[:]

    # Save original logger levels
    saved_levels = {}
    for logger_name in _nemo_loggers:
        log = logging.getLogger(logger_name)
        saved_levels[logger_name] = log.level
        log.setLevel(logging.CRITICAL + 1)  # Above CRITICAL = no output

    try:
        # Suppress all warnings during NeMo operations
        warnings.simplefilter('ignore')

        yield
    finally:
        # Restore logger levels
        for logger_name, level in saved_levels.items():
            logging.getLogger(logger_name).setLevel(level)

        # Restore warning filters
        warnings.filters[:] = original_filters


class TranscriptionBuffer:
    """Simple transcription buffer for batching"""

    def __init__(self):
        self.text = ""
        self.last_processed_time = time.time()

    def add(self, text: str) -> None:
        """Add text to buffer"""
        self.text += text + " "

    def get(self) -> str:
        """Get all text"""
        return self.text.strip()

    def clear(self) -> None:
        """Clear buffer"""
        self.text = ""
        self.last_processed_time = time.time()


class FrameASR:
    """
    Real-time ASR for transcription with Canary-1B Flash
    Accumulates speech chunks for better accuracy
    """

    def __init__(self, model, config: Config):
        """
        Initialize Frame ASR

        Args:
            model: NeMo ASR model
            config: Configuration object
        """
        self.model = model
        self.config = config
        self.sample_rate = config.sample_rate

        # VAD state
        self.last_max_amplitude = 0
        self.last_avg_amplitude = 0

        # Model components
        self.preprocessor = model.preprocessor
        self.encoder = model.encoder
        self.decoder = model.decoding.decoder if hasattr(model.decoding, 'decoder') else None

        # Speech accumulation buffer (accumulate speech before transcribing)
        self.speech_buffer = []
        self.min_buffer_duration = MIN_BUFFER_DURATION
        self.max_buffer_duration = MAX_BUFFER_DURATION
        self.silence_chunks_to_flush = SILENCE_CHUNKS_TO_FLUSH
        self.silence_count = 0

        # Error recovery configuration
        self.max_retries = config.transcription_max_retries if config.enable_error_recovery else 0
        self.retry_delay = config.transcription_retry_delay
        self.consecutive_failures = 0

        logger.info("Frame ASR initialized for real-time transcription")
        if config.enable_error_recovery:
            logger.info(f"Transcription error recovery enabled: max_retries={self.max_retries}")

    def has_speech(self, audio: np.ndarray, debug: bool = False) -> bool:
        """
        Check if audio contains speech using energy-based VAD

        Args:
            audio: Audio data as float32 array
            debug: Enable debug logging

        Returns:
            True if speech detected, False if silence
        """
        # Convert to int16 range for amplitude check
        audio_int16 = np.empty(audio.shape, dtype=np.int16)
        np.multiply(audio, 32768, out=audio_int16, casting='unsafe')

        # Calculate absolute amplitude
        amplitude = np.abs(audio_int16)

        # Calculate max amplitude and average
        max_amplitude = np.max(amplitude)
        avg_amplitude = np.mean(amplitude)

        # Check what percentage of samples exceed threshold
        speech_samples = np.sum(amplitude > self.config.silence_threshold)
        speech_ratio = speech_samples / len(audio)

        has_speech = speech_ratio > self.config.min_speech_ratio

        # Store last values for logging
        self.last_max_amplitude = max_amplitude
        self.last_avg_amplitude = avg_amplitude

        # Debug logging
        if debug and self.config.debug_mode:
            status = "SPEECH" if has_speech else "SILENCE"
            logger.debug(
                f"{status} | Max: {max_amplitude:5.0f} | Avg: {avg_amplitude:5.1f} | "
                f"Ratio: {speech_ratio*100:5.2f}% (threshold: {self.config.min_speech_ratio*100:.2f}%)"
            )

        return has_speech

    def add_speech_chunk(self, chunk: np.ndarray) -> None:
        """Add a speech chunk to the buffer"""
        self.speech_buffer.append(chunk)
        self.silence_count = 0

    def increment_silence(self) -> None:
        """Increment silence counter when silence is detected"""
        self.silence_count += 1

    def should_transcribe(self) -> bool:
        """Check if we have enough audio to transcribe"""
        if not self.speech_buffer:
            return False

        total_samples = sum(len(chunk) for chunk in self.speech_buffer)
        duration = total_samples / self.sample_rate

        # Transcribe if:
        # 1. We have minimum audio AND hit silence (end of utterance)
        # 2. OR buffer is getting too full (force flush)
        has_min_audio = duration >= self.min_buffer_duration
        buffer_full = duration >= self.max_buffer_duration
        silence_detected = self.silence_count >= self.silence_chunks_to_flush

        return (has_min_audio and silence_detected) or buffer_full

    def get_buffered_audio(self) -> np.ndarray:
        """Get concatenated buffered audio and clear buffer"""
        if not self.speech_buffer:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(self.speech_buffer)
        duration = len(audio) / self.sample_rate
        logger.debug(f"Flushing buffer: {duration:.2f}s of audio ({len(self.speech_buffer)} chunks)")
        self.speech_buffer = []
        self.silence_count = 0
        return audio

    def transcribe_chunk(self, chunk: np.ndarray) -> str:
        """
        Transcribe an audio chunk in real-time with retry logic

        Args:
            chunk: Audio chunk as float32 array

        Returns:
            Transcribed text from this chunk
        """
        if chunk is None or len(chunk) == 0:
            return ""

        # Safety check: Canary-1B trained on <30s audio
        # Reject chunks longer than MAX_CHUNK_DURATION_SECONDS to prevent hallucinations
        duration = len(chunk) / self.sample_rate
        if duration > MAX_CHUNK_DURATION_SECONDS:
            logger.warning(
                f"Chunk too long ({duration:.1f}s), "
                f"truncating to {MAX_CHUNK_DURATION_SECONDS}s to prevent hallucinations"
            )
            max_samples = int(MAX_CHUNK_DURATION_SECONDS * self.sample_rate)
            chunk = chunk[:max_samples]
            duration = MAX_CHUNK_DURATION_SECONDS

        def _do_transcribe() -> str:
            """Internal transcription function for retry logic"""
            import tempfile
            import wave
            import os
            import io

            start_time = time.time()

            # Use in-memory buffer for WAV generation (faster than disk I/O)
            wav_buffer = io.BytesIO()

            # Write audio to WAV buffer with 16-bit samples
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(1)  # Mono
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)

                # Convert float32 to int16
                audio_int16 = np.empty(chunk.shape, dtype=np.int16)
                np.multiply(chunk, 32768, out=audio_int16, casting='unsafe')
                wf.writeframes(audio_int16.tobytes())

            # Get WAV data from buffer
            wav_data = wav_buffer.getvalue()
            wav_buffer.close()

            # NeMo requires a file path, write minimal temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            tmp_path = temp_file.name
            temp_file.write(wav_data)
            temp_file.close()

            try:
                # Transcribe the file with output suppression (prevents TUI interference)
                # Canary-1B Flash returns Hypothesis objects with .text attribute
                with suppress_nemo_output():
                    result = self.model.transcribe([tmp_path], verbose=False)

                logger.debug(f"Transcribe result type: {type(result)}, length: {len(result) if result else 0}")

                # Extract text from Canary result (format: result[0].text)
                text = ""
                if result and len(result) > 0:
                    first = result[0]
                    logger.debug(f"First result type: {type(first)}, value: {first}")

                    # Canary/EncDecMultiTaskModel returns Hypothesis objects
                    if hasattr(first, 'text'):
                        text = first.text
                        logger.debug(f"Got .text attribute: '{text}'")
                    elif isinstance(first, str):
                        text = first
                        logger.debug(f"Got string directly: '{text}'")
                    else:
                        text = str(first)
                        logger.debug(f"Converted to string: '{text}'")

                elapsed = time.time() - start_time

                # Log RAW output before any processing (only in debug mode)
                if text:
                    logger.debug(f"[RAW OUTPUT] '{text}' ({elapsed*1000:.0f}ms)")
                else:
                    logger.debug(f"Transcription in {elapsed*1000:.1f}ms | Raw: '' (empty)")

                # Filter and process
                processed_text = self._process_text(text)

                # Log if filtering changed anything (only warnings and debug)
                if text and not processed_text:
                    logger.debug(f"[FILTERED OUT] '{text}' was filtered")
                elif processed_text:
                    logger.debug(f"[FINAL] '{processed_text}'")

                return processed_text

            finally:
                # Always clean up temp file
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        # Try transcription with retry logic if enabled
        if self.max_retries > 0:
            try:
                result = exponential_backoff(
                    _do_transcribe,
                    max_retries=self.max_retries,
                    initial_delay=self.retry_delay,
                    max_delay=5.0,
                    exponential_base=2.0,
                    exceptions=(Exception,)
                )
                # Success - reset failure counter
                if self.consecutive_failures > 0:
                    logger.info("Transcription recovered after failures")
                    self.consecutive_failures = 0
                return result
            except RetryExhausted:
                self.consecutive_failures += 1
                logger.error(
                    f"Transcription failed after {self.max_retries} retries "
                    f"(consecutive failures: {self.consecutive_failures})"
                )
                return ""
            except Exception as e:
                import traceback
                logger.error(f"Unexpected transcription error: {e}")
                logger.error(f"Full traceback:\n{traceback.format_exc()}")
                return ""
        else:
            # No retry - single attempt
            try:
                return _do_transcribe()
            except Exception as e:
                import traceback
                logger.error(f"Transcription failed: {e}")
                logger.error(f"Full traceback:\n{traceback.format_exc()}")
                return ""

    def _extract_text(self, result) -> str:
        """Extract text from NeMo result"""
        if isinstance(result, (list, tuple)) and len(result) > 0:
            first = result[0]
            if hasattr(first, 'text'):
                return first.text
            elif isinstance(first, str):
                return first
            else:
                return str(first)
        return str(result)

    def _process_text(self, text: str) -> str:
        """Process and filter transcribed text"""
        original_text = text

        # Filter too short
        if len(text) < MIN_TEXT_LENGTH:
            logger.debug(f"Filtered: too short (len={len(text)}, min={MIN_TEXT_LENGTH})")
            return ""

        # Filter Canary-1B repetition hallucinations (e.g., "Dohhhhhhhh...")
        # Check for excessive character repetition (likely hallucination)
        if len(text) > 50:
            # Count consecutive repeated characters
            max_repeats = 1
            current_repeats = 1
            prev_char = ''
            for char in text:
                if char == prev_char and char.isalpha():
                    current_repeats += 1
                    max_repeats = max(max_repeats, current_repeats)
                else:
                    current_repeats = 1
                prev_char = char

            # If more than MAX_CHAR_REPEATS repeated characters, it's likely a hallucination
            if max_repeats > MAX_CHAR_REPEATS:
                logger.warning(
                    f"Filtered repetition hallucination: '{text[:100]}...' "
                    f"(max_repeats={max_repeats}, threshold={MAX_CHAR_REPEATS})"
                )
                return ""

        # Apply word corrections
        text = self._apply_corrections(text)

        # Filter hallucinations (only if EXACT match to known hallucinations)
        if text.lower() in HALLUCINATION_PHRASES:
            logger.debug(f"Filtered hallucination: '{original_text}' -> '{text}'")
            return ""

        # Log what we're accepting
        if text != original_text:
            logger.debug(f"✓ Corrected: '{original_text}' -> '{text}'")
        else:
            logger.debug(f"✓ Accepted: '{text}'")
        return text

    def _apply_corrections(self, text: str) -> str:
        """Apply word-level corrections"""
        # Filter Cyrillic characters
        text = re.sub(r'[А-Яа-яЁё]+', '', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if not text:
            return ""

        # Apply word corrections
        words = text.split()
        corrected_words = []

        for word in words:
            word_clean = re.sub(r'[^\w]', '', word).lower()

            if word_clean in WORD_CORRECTIONS:
                # Preserve punctuation
                punctuation = ''.join(c for c in word if not c.isalnum())
                corrected = WORD_CORRECTIONS[word_clean]

                if word and word[0] in '.,!?;:':
                    corrected = word[0] + corrected
                if len(word) > 1 and word[-1] in '.,!?;:':
                    corrected = corrected + word[-1]

                corrected_words.append(corrected)
            else:
                corrected_words.append(word)

        return ' '.join(corrected_words)

    def reset(self) -> None:
        """Reset internal state"""
        self.speech_buffer = []
        self.silence_count = 0
        logger.debug("ASR state reset")

    def is_model_healthy(self) -> bool:
        """
        Check if model is healthy and responsive

        Returns:
            True if healthy, False if potentially stuck
        """
        try:
            # Quick health check - try to access model attributes
            if self.model is None:
                return False

            # Check if model is on expected device
            if hasattr(self.model, 'device'):
                _ = self.model.device

            return True

        except Exception as e:
            logger.error(f"Model health check failed: {e}")
            return False


def load_nemo_model(config: Config) -> Optional[EncDecMultiTaskModel]:
    """
    Load NeMo ASR model (Canary-1B Flash)

    Args:
        config: Configuration object

    Returns:
        Loaded model or None on error
    """
    if not config.enable_model:
        logger.warning("Model loading DISABLED (feature flag)")
        return None

    logger.info(f"Loading NeMo model: {config.model_name}")

    try:
        # Set environment for threading
        os.environ['OMP_NUM_THREADS'] = '1'
        os.environ['MKL_NUM_THREADS'] = '1'
        os.environ['NUMEXPR_NUM_THREADS'] = '1'

        torch.set_num_threads(1)

        # Load Canary multi-task model
        # Suppress NeMo warnings during model load
        with suppress_nemo_output():
            model = EncDecMultiTaskModel.from_pretrained(config.model_name)

        # Move to GPU if available
        if torch.cuda.is_available():
            model = model.cuda()

        # Log after suppression context exits
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            logger.info(f"Canary-1B Flash loaded on GPU: {device_name}")
        else:
            logger.info("Canary-1B Flash loaded on CPU")

        # Configure greedy decoding for optimal speed/accuracy (suppress output)
        with suppress_nemo_output():
            decode_cfg = model.cfg.decoding
            decode_cfg.beam.beam_size = config.canary_beam_size  # 1 for greedy (fastest)
            model.change_decoding_strategy(decode_cfg)

        logger.info(f"✓ Greedy decoding configured (beam_size={config.canary_beam_size})")

        # Enable streaming mode if available (suppress output)
        with suppress_nemo_output():
            if hasattr(model, 'set_streaming_mode'):
                model.set_streaming_mode(True)

        if hasattr(model, 'set_streaming_mode'):
            logger.info("✓ Streaming mode enabled")

        # Configure word boosting if available
        boost_file = Path(config.boost_words_file)
        if boost_file.exists() and hasattr(model, 'change_decoding_strategy'):
            _configure_word_boosting(model, boost_file)

        # Set model to eval mode (suppress any potential output)
        with suppress_nemo_output():
            model.eval()

        logger.info(f"Model ready - Expected latency: <50ms per chunk (1000+ RTFx)")
        logger.info(f"Language: {config.canary_source_lang} → {config.canary_target_lang} | Task: {config.canary_task}")
        return model

    except Exception as e:
        logger.error(f"Failed to load model: {e}", exc_info=True)
        return None


def _configure_word_boosting(model, boost_file: Path) -> None:
    """Configure GPU-PB word boosting"""
    try:
        with open(boost_file, 'r') as f:
            key_phrases = [line.strip() for line in f if line.strip()]

        if not key_phrases:
            return

        logger.info(f"Word boost enabled: {len(key_phrases)} phrases")

        # Suppress NeMo output during decoding strategy change
        with suppress_nemo_output():
            from omegaconf import OmegaConf
            decoding_cfg = OmegaConf.create({
                'strategy': 'greedy_batch',
                'context_score': 6.0,  # Increased from 3.0 for better wake word recognition
                'key_phrases_list': key_phrases
            })

            model.change_decoding_strategy(decoding_cfg)

        logger.info("GPU-PB word boosting configured")

    except Exception as e:
        logger.warning(f"Failed to enable word boosting: {e}")
