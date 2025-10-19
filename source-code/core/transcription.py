"""
ASR Transcription with NeMo Parakeet-TDT
Real-time transcription with buffering for accuracy
"""
import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional, Tuple
import re

import numpy as np
import torch
import nemo.collections.asr as nemo_asr

from .config import Config

logger = logging.getLogger(__name__)


# Common hallucinations to filter out (keep this minimal!)
# NOTE: Only filter phrases that are clearly hallucinations, not common words
HALLUCINATION_PHRASES = {
    'thanks for watching', 'please subscribe',
    'uh', 'um', 'ah', 'mm', 'hmm',
    '.', '...'
    # Removed: 'you', 'okay', 'ok', 'thank you' - these are real words!
}

# Word corrections for common misrecognitions
WORD_CORRECTIONS = {
    'jarve': 'Jarvis',
    'jarvy': 'Jarvis',
    'jarry': 'Jarvis',
    'jervis': 'Jarvis',
    'jarvie': 'Jarvis',
    'jarvey': 'Jarvis',
    'jadrice': 'Jarvis',
    'jobies': 'Jarvis',
    'jarbies': 'Jarvis',
    'jeremies': 'Jarvis',
}


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
    Real-time ASR for transcription with Parakeet-TDT
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
        self.min_buffer_duration = 0.4  # seconds - reduced for faster response
        self.max_buffer_duration = 3.0  # seconds - max before forcing flush
        self.silence_chunks_to_flush = 2  # flush after 2 silence chunks (200ms)
        self.silence_count = 0

        logger.info("Frame ASR initialized for real-time transcription")

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
        logger.info(f"Flushing buffer: {duration:.2f}s of audio ({len(self.speech_buffer)} chunks)")
        self.speech_buffer = []
        self.silence_count = 0
        return audio

    def transcribe_chunk(self, chunk: np.ndarray) -> str:
        """
        Transcribe an audio chunk in real-time

        Args:
            chunk: Audio chunk as float32 array

        Returns:
            Transcribed text from this chunk
        """
        if chunk is None or len(chunk) == 0:
            return ""

        start_time = time.time()

        try:
            import tempfile
            import wave
            import os

            # NeMo's transcribe() works best with WAV files
            # Create a temporary WAV file with proper format
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            tmp_path = temp_file.name
            temp_file.close()

            # Write audio to WAV file with 16-bit samples
            with wave.open(tmp_path, 'wb') as wf:
                wf.setnchannels(1)  # Mono
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)

                # Convert float32 to int16
                audio_int16 = np.empty(chunk.shape, dtype=np.int16)
                np.multiply(chunk, 32768, out=audio_int16, casting='unsafe')
                wf.writeframes(audio_int16.tobytes())

            # Transcribe the file
            result = self.model.transcribe([tmp_path], verbose=False)

            # Clean up temp file
            os.unlink(tmp_path)

            logger.info(f"Transcribe result type: {type(result)}, length: {len(result) if result else 0}")

            # Extract text from result
            text = ""
            if result and len(result) > 0:
                first = result[0]
                logger.info(f"First result type: {type(first)}, value: {first}")

                # Check if it's a Hypothesis object with .text attribute
                if hasattr(first, 'text'):
                    text = first.text
                    logger.info(f"Got .text attribute: '{text}'")
                elif isinstance(first, str):
                    text = first
                    logger.info(f"Got string directly: '{text}'")
                else:
                    text = str(first)
                    logger.info(f"Converted to string: '{text}'")

            elapsed = time.time() - start_time

            # Log RAW output before any processing
            if text:
                logger.info(f"[RAW OUTPUT] '{text}' ({elapsed*1000:.0f}ms)")
            else:
                logger.debug(f"Transcription in {elapsed*1000:.1f}ms | Raw: '' (empty)")

            # Filter and process
            processed_text = self._process_text(text)

            # Log if filtering changed anything
            if text and not processed_text:
                logger.warning(f"[FILTERED OUT] '{text}' was filtered")
            elif processed_text:
                logger.info(f"[FINAL] '{processed_text}'")

            return processed_text

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
        if len(text) < 2:
            logger.debug(f"Filtered: too short (len={len(text)})")
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


def load_nemo_model(config: Config) -> Optional[nemo_asr.models.ASRModel]:
    """
    Load NeMo ASR model (Parakeet-TDT by default)

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

        # Load streaming model
        model = nemo_asr.models.ASRModel.from_pretrained(config.model_name)

        # Move to GPU if available
        if torch.cuda.is_available():
            model = model.cuda()
            device_name = torch.cuda.get_device_name(0)
            logger.info(f"Parakeet-TDT loaded on GPU: {device_name}")
        else:
            logger.info("Parakeet-TDT loaded on CPU")

        # Enable streaming mode if available (not all streaming models have this method)
        if hasattr(model, 'set_streaming_mode'):
            model.set_streaming_mode(True)
            logger.info("✓ Streaming mode enabled via set_streaming_mode")

        # Check if model has conformer_stream_step (this is the key API we need)
        if hasattr(model, 'conformer_stream_step'):
            logger.info("✓ conformer_stream_step API available - cache-aware processing active")
        else:
            logger.warning("⚠ conformer_stream_step not available - will use fallback transcription")

        # Configure word boosting if available
        boost_file = Path(config.boost_words_file)
        if boost_file.exists() and hasattr(model, 'change_decoding_strategy'):
            _configure_word_boosting(model, boost_file)

        model.eval()
        logger.info(f"Model ready - Expected latency: ~80-160ms per chunk")
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

        from omegaconf import OmegaConf
        decoding_cfg = OmegaConf.create({
            'strategy': 'greedy_batch',
            'context_score': 3.0,
            'key_phrases_list': key_phrases
        })

        model.change_decoding_strategy(decoding_cfg)
        logger.info("GPU-PB word boosting configured")

    except Exception as e:
        logger.warning(f"Failed to enable word boosting: {e}")
