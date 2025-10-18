"""
ASR Transcription with NeMo
Frame-based streaming transcription with VAD and deduplication
"""
import os
import sys
import time
import tempfile
import wave
import logging
from pathlib import Path
from typing import Optional
import re

import numpy as np
import torch
import nemo.collections.asr as nemo_asr

from .config import Config

logger = logging.getLogger(__name__)


# Common hallucinations to filter out
HALLUCINATION_PHRASES = {
    'thank you', 'thanks for watching', 'please subscribe',
    'you', 'uh', 'um', 'ah', 'mm', 'hmm',
    '.', '...', 'okay', 'ok'
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
    Frame-based ASR for continuous streaming transcription
    Uses overlapping buffers to prevent word cutoff
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
        self.frame_len = config.frame_len
        self.sample_rate = config.sample_rate
        self.n_frame_len = int(config.frame_len * config.sample_rate)

        # Sliding buffer with overlap
        self.buffer = np.zeros(self.n_frame_len, dtype=np.float32)
        self.prev_text = ''
        self.prev_text_count = 0
        self.last_max_amplitude = 0
        self.last_avg_amplitude = 0

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

    def transcribe_chunk(self, chunk: np.ndarray) -> str:
        """
        Transcribe an audio chunk using the sliding buffer

        Args:
            chunk: Audio chunk as float32 array

        Returns:
            Transcribed text (only new characters)
        """
        if chunk is None or len(chunk) == 0:
            return ""

        # Update sliding buffer
        chunk_len = len(chunk)
        if chunk_len < self.n_frame_len:
            # Shift buffer and add new chunk
            self.buffer[:-chunk_len] = self.buffer[chunk_len:]
            self.buffer[-chunk_len:] = chunk
        else:
            # Replace entire buffer
            self.buffer = chunk[-self.n_frame_len:]

        # Check if buffer contains speech (VAD)
        if not self.has_speech(self.buffer, debug=True):
            # Reset counter on silence
            if self.prev_text:
                self.prev_text = ''
                self.prev_text_count = 0
            return ""

        # Transcribe current buffer
        logger.debug("Transcription starting...")
        start_time = time.time()

        try:
            # Create temp file for transcription
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_path = temp_file.name
            temp_file.close()

            # Write buffer to wav file
            with wave.open(temp_path, 'wb') as wf:
                wf.setnchannels(self.config.channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)

                # Convert to int16
                audio_int16 = np.empty(self.buffer.shape, dtype=np.int16)
                np.multiply(self.buffer, 32768, out=audio_int16, casting='unsafe')
                wf.writeframes(audio_int16.tobytes())

            # Transcribe
            with torch.no_grad():
                result = self.model.transcribe([temp_path], verbose=False)

            os.unlink(temp_path)

            # Extract text from result
            text = self._extract_text(result).strip()

            elapsed = time.time() - start_time
            logger.debug(f"Transcription completed in {elapsed:.2f}s | Raw: '{text}'")

            # Filter and process
            text = self._process_text(text)

            return text

        except Exception as e:
            logger.error(f"Chunk transcription failed: {e}")
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
        # Filter too short
        if len(text) < 2:
            logger.debug(f"Filtered: too short (len={len(text)})")
            return ""

        # Apply word corrections
        text = self._apply_corrections(text)

        # Filter hallucinations
        if text.lower() in HALLUCINATION_PHRASES:
            logger.debug("Filtered: hallucination phrase")
            return ""

        # Deduplication
        if text == self.prev_text:
            self.prev_text_count += 1
            if self.prev_text_count >= 3:
                logger.debug("Filtered: repeated 3+ times")
                return ""
            logger.debug("Filtered: duplicate")
            return ""

        # New text detected
        self.prev_text = text
        self.prev_text_count = 1

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
        """Reset the buffer"""
        self.buffer = np.zeros(self.n_frame_len, dtype=np.float32)
        self.prev_text = ''
        self.prev_text_count = 0


def load_nemo_model(config: Config) -> Optional[nemo_asr.models.ASRModel]:
    """
    Load NeMo ASR model with word boosting

    Args:
        config: Configuration object

    Returns:
        Loaded model or None on error
    """
    if not config.enable_model:
        logger.warning("Model loading DISABLED (feature flag)")
        return None

    logger.info("Loading NeMo Parakeet-TDT model...")

    try:
        # Set environment for threading
        os.environ['OMP_NUM_THREADS'] = '1'
        os.environ['MKL_NUM_THREADS'] = '1'
        os.environ['NUMEXPR_NUM_THREADS'] = '1'

        torch.set_num_threads(1)

        # Load model
        model = nemo_asr.models.ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v3")

        # Move to GPU if available
        if torch.cuda.is_available():
            model = model.cuda()
            device_name = torch.cuda.get_device_name(0)
            logger.info(f"Model loaded on GPU: {device_name}")
        else:
            logger.info("Model loaded on CPU")

        # Configure word boosting
        boost_file = Path(config.boost_words_file)
        if boost_file.exists():
            _configure_word_boosting(model, boost_file)

        model.eval()
        return model

    except Exception as e:
        logger.error(f"Failed to load model: {e}")
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
