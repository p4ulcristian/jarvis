#!/home/paul/Work/jarvis/venv/bin/python
"""
JARVIS - Voice-to-Text System with Streaming NeMo ASR
Continuous speech logging with push-to-talk and typing modes
"""

import os
import sys

# Save original stderr
_original_stderr = sys.stderr

# Fix malloc issues BEFORE any library imports
os.environ['MALLOC_TRIM_THRESHOLD_'] = '0'
os.environ['MALLOC_MMAP_THRESHOLD_'] = '131072'
os.environ['MALLOC_MMAP_MAX_'] = '65536'

# Suppress ALSA warnings BEFORE importing pyaudio
os.environ['PYTHONWARNINGS'] = 'ignore'
os.environ['ALSA_CONFIG_PATH'] = '/dev/null'

# Redirect stderr to /dev/null temporarily for ALSA imports
_devnull = open(os.devnull, 'w')
sys.stderr = _devnull

import time
import subprocess
import tempfile
import json
from pathlib import Path
from datetime import datetime
from collections import deque
import logging
import warnings
import gc
import ctypes

# Suppress warnings and verbose output
warnings.filterwarnings('ignore')
logging.getLogger().setLevel(logging.ERROR)

import torch
import numpy as np
import nemo.collections.asr as nemo_asr
import sounddevice as sd
import wave
from pynput.keyboard import Controller

# Restore stderr after ALSA imports
sys.stderr = _original_stderr
_devnull.close()

# Suppress NeMo's verbose logging
import nemo.utils
logging.getLogger('nemo_logger').setLevel(logging.ERROR)

# Fix PyTorch/NumPy memory allocator conflict
# This must be done before any CUDA initialization
# Use native allocator to avoid conflicts with PyAudio
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'backend:native'
# Re-enable CUDA now that sounddevice fixed the malloc conflict
# os.environ['CUDA_VISIBLE_DEVICES'] = ''  # Disabled - we can use GPU now!

# Feature Flags - Enable/disable modules as needed
ENABLE_MICROPHONE = True   # Audio capture ✓
ENABLE_MODEL = True        # NeMo ASR model ✓
ENABLE_VAD = True          # Voice activity detection ✓
ENABLE_AI_DETECTION = False  # AI detection (disabled by default)
ENABLE_TRANSCRIPTION = True  # Real-time transcription ✓

# Constants
DEBUG_MODE = False  # Set to True to see detailed audio/VAD/transcription logging
SAMPLE_RATE = 16000
CHUNK_SIZE = 1600  # 100ms chunks at 16kHz
CHANNELS = 1
TRIGGER_FILE = "/tmp/jarvis-type-trigger"
KEYBOARD_EVENT_FILE = "/tmp/jarvis-keyboard-events"
LOG_FILE = "chat.txt"

# Streaming ASR settings
FRAME_LEN = 1.6  # seconds per frame
CHUNK_DURATION_SEC = 0.1  # 100ms chunks
SILENCE_THRESHOLD = 10  # Minimum audio energy to consider as speech (lower = more sensitive) - VERY SENSITIVE
MIN_SPEECH_RATIO = 0.0001  # Minimum % of frame that must be above threshold (0.01%) - VERY SENSITIVE

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

# AI Detection
AI_DETECTOR_SCRIPT = "ai-detector/ai_detector_cli.py"
AI_DETECTOR_PYTHON = "ai-detector/venv/bin/python"
DETECTION_COOLDOWN = 5  # seconds
BUFFER_DURATION = 300  # 5 minutes in seconds


class FrameASR:
    """
    Frame-based ASR for continuous streaming transcription
    Uses overlapping buffers to prevent word cutoff
    """
    def __init__(self, model, frame_len=FRAME_LEN, sample_rate=SAMPLE_RATE):
        self.model = model
        self.frame_len = frame_len
        self.sample_rate = sample_rate
        self.n_frame_len = int(frame_len * sample_rate)

        # Sliding buffer with overlap
        self.buffer = np.zeros(self.n_frame_len, dtype=np.float32)
        self.prev_text = ''
        self.prev_text_count = 0  # Track how many times we see the same text
        self.last_max_amplitude = 0
        self.last_avg_amplitude = 0

    def has_speech(self, audio, debug=False):
        """
        Check if audio contains speech using energy-based VAD
        Returns: True if speech detected, False if silence
        """
        # Convert to int16 range for amplitude check - avoid astype() malloc conflicts
        audio_int16 = np.empty(audio.shape, dtype=np.int16)
        np.multiply(audio, 32768, out=audio_int16, casting='unsafe')

        # Calculate absolute amplitude
        amplitude = np.abs(audio_int16)

        # Calculate max amplitude and average
        max_amplitude = np.max(amplitude)
        avg_amplitude = np.mean(amplitude)

        # Check what percentage of samples exceed threshold
        speech_samples = np.sum(amplitude > SILENCE_THRESHOLD)
        speech_ratio = speech_samples / len(audio)

        has_speech = speech_ratio > MIN_SPEECH_RATIO

        # Store last values for logging
        self.last_max_amplitude = max_amplitude
        self.last_avg_amplitude = avg_amplitude

        # Debug logging
        if DEBUG_MODE and debug:
            status = "SPEECH" if has_speech else "SILENCE"
            print(f"[DEBUG VAD] {status} | Max: {max_amplitude:5.0f} | Avg: {avg_amplitude:5.1f} | "
                  f"Ratio: {speech_ratio*100:5.2f}% (threshold: {MIN_SPEECH_RATIO*100:.2f}%)")
            sys.stdout.flush()

        return has_speech

    def transcribe_chunk(self, chunk):
        """
        Transcribe an audio chunk using the sliding buffer
        Returns: transcribed text (only new characters)
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

        # Check if buffer contains speech (VAD) - enable debug
        if not self.has_speech(self.buffer, debug=True):
            # Reset counter on silence
            if self.prev_text:
                self.prev_text = ''
                self.prev_text_count = 0
            return ""

        # Transcribe current buffer
        if DEBUG_MODE:
            print("[DEBUG] Transcription starting...")
            sys.stdout.flush()
        start_time = time.time()
        try:
            # Create temp file for transcription
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_path = temp_file.name
            temp_file.close()

            # Write buffer to wav file
            wf = wave.open(temp_path, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            # Convert back to int16 for wav file - avoid astype() malloc conflicts
            audio_int16 = np.empty(self.buffer.shape, dtype=np.int16)
            np.multiply(self.buffer, 32768, out=audio_int16, casting='unsafe')
            wf.writeframes(audio_int16.tobytes())
            wf.close()

            # Transcribe
            transcribe_start = time.time()
            with torch.no_grad():
                result = self.model.transcribe([temp_path], verbose=False)
            transcribe_time = time.time() - transcribe_start

            os.unlink(temp_path)

            # Extract text
            if isinstance(result, (list, tuple)) and len(result) > 0:
                first = result[0]
                if hasattr(first, 'text'):
                    text = first.text
                elif isinstance(first, str):
                    text = first
                else:
                    text = str(first)
            else:
                text = str(result)

            text = text.strip()

            total_time = time.time() - start_time

            if DEBUG_MODE:
                print(f"[DEBUG] Transcription completed in {total_time:.2f}s | Raw text: '{text}'")
                sys.stdout.flush()

            # Filter out empty or very short hallucinations
            if len(text) < 2:
                if DEBUG_MODE:
                    print(f"[DEBUG] Filtered: too short (len={len(text)})")
                    sys.stdout.flush()
                return ""

            # Apply word corrections
            text = self.apply_word_corrections(text)

            # Filter common hallucination phrases
            text_lower = text.lower()
            if text_lower in HALLUCINATION_PHRASES:
                if DEBUG_MODE:
                    print(f"[DEBUG] Filtered: hallucination phrase")
                    sys.stdout.flush()
                return ""

            # Deduplication: check if same as previous
            if text == self.prev_text:
                self.prev_text_count += 1
                # If we see the same text 3+ times, it's likely a hallucination
                if self.prev_text_count >= 3:
                    if DEBUG_MODE:
                        print(f"[DEBUG] Filtered: repeated 3+ times")
                        sys.stdout.flush()
                    return ""
                # Otherwise skip duplicate
                if DEBUG_MODE:
                    print(f"[DEBUG] Filtered: duplicate")
                    sys.stdout.flush()
                return ""

            # New text detected
            self.prev_text = text
            self.prev_text_count = 1

            if DEBUG_MODE:
                print(f"[DEBUG] ✓ Accepted text: '{text}'")
                sys.stdout.flush()

            return text

        except Exception as e:
            print(f"[ERROR] Chunk transcription failed: {e}", file=sys.stderr)
            return ""

    def apply_word_corrections(self, text):
        """Apply word-level corrections for common misrecognitions"""
        import re

        # Filter out Cyrillic characters (Russian, Ukrainian, etc.)
        # Keep only Latin, Hungarian, punctuation, and common symbols
        text = re.sub(r'[А-Яа-яЁё]+', '', text)
        text = re.sub(r'\s+', ' ', text).strip()  # Clean up extra spaces

        if not text:
            return ""

        # Split into words while preserving punctuation
        words = text.split()
        corrected_words = []

        for word in words:
            # Extract word without punctuation for matching
            word_clean = re.sub(r'[^\w]', '', word).lower()

            # Check if word needs correction
            if word_clean in WORD_CORRECTIONS:
                # Preserve original punctuation
                punctuation = ''.join(c for c in word if not c.isalnum())
                corrected = WORD_CORRECTIONS[word_clean]

                # Reattach punctuation
                if word[0] in '.,!?;:':
                    corrected = word[0] + corrected
                if len(word) > 1 and word[-1] in '.,!?;:':
                    corrected = corrected + word[-1]

                corrected_words.append(corrected)
            else:
                corrected_words.append(word)

        return ' '.join(corrected_words)

    def reset(self):
        """Reset the buffer"""
        self.buffer = np.zeros(self.n_frame_len, dtype=np.float32)
        self.prev_text = ''
        self.prev_text_count = 0


class TranscriptionBuffer:
    """Rolling buffer for AI detection"""
    def __init__(self, max_duration=BUFFER_DURATION):
        self.buffer = deque()
        self.max_duration = max_duration

    def add(self, text):
        self.buffer.append({
            'text': text,
            'timestamp': time.time()
        })
        self._clean()

    def get_text(self):
        self._clean()
        return ' '.join(entry['text'] for entry in self.buffer)

    def _clean(self):
        cutoff = time.time() - self.max_duration
        while self.buffer and self.buffer[0]['timestamp'] < cutoff:
            self.buffer.popleft()

class Jarvis:
    def __init__(self):
        self.model = None
        self.keyboard = None

        # sounddevice works natively with NumPy - no malloc conflicts!
        print("Initializing audio...", end=' ', flush=True)
        self.device_sample_rate = 48000  # Use 48kHz (widely supported)
        self.needs_resampling = True
        print("✓", flush=True)
        self.transcription_buffer = TranscriptionBuffer()
        self.frame_asr = None
        self.audio_stream = None
        self.last_trigger_time = 0
        self.last_detection_time = 0
        self.shutdown = False
        self.conversation_improver_process = None

        # Improved text cache
        self.improved_cache = deque(maxlen=100)
        self.improved_log_path = Path("chat-revised.txt")
        self.improved_last_position = 0

    def _init_pyaudio(self):
        """Initialize PyAudio after model loading to avoid conflicts"""
        if self.pyaudio is not None:
            return  # Already initialized

        # Suppress ALSA warnings during PyAudio initialization
        _stderr_backup = sys.stderr
        sys.stderr = open(os.devnull, 'w')
        self.pyaudio = pyaudio.PyAudio()
        sys.stderr.close()
        sys.stderr = _stderr_backup

        # Detect supported sample rate
        self.device_sample_rate = self._detect_sample_rate()
        self.needs_resampling = (self.device_sample_rate != SAMPLE_RATE)

    def _detect_sample_rate(self):
        """Detect a supported sample rate for the default input device"""
        # Use 48000 Hz which is widely supported
        # We'll use simple decimation for resampling to avoid numpy/pytorch conflicts
        return 48000

    def _resample_audio(self, audio_data, orig_rate, target_rate):
        """Resample audio using simple decimation to avoid numpy/pytorch memory conflicts"""
        if orig_rate == target_rate:
            return audio_data

        if len(audio_data) == 0:
            return audio_data

        # For 48kHz -> 16kHz, we can use simple decimation (take every 3rd sample)
        # This avoids numpy memory allocation that conflicts with PyTorch CUDA
        if orig_rate == 48000 and target_rate == 16000:
            # Simple decimation: take every 3rd sample
            return audio_data[::3]

        # For other rates, use stride-based decimation
        stride = int(orig_rate / target_rate)
        if stride > 1:
            return audio_data[::stride]

        # If upsampling is needed, just repeat samples (simple but works)
        if stride < 1:
            repeat_factor = int(target_rate / orig_rate)
            return np.repeat(audio_data, repeat_factor)

        return audio_data

    def load_model(self):
        """Load NeMo ASR model with word boosting"""
        if not ENABLE_MODEL:
            print("Model loading DISABLED (feature flag)")
            return True

        print("Loading NeMo Parakeet-TDT model...", end=' ', flush=True)
        sys.stdout.flush()

        try:
            # Set environment variables to prevent threading conflicts
            os.environ['OMP_NUM_THREADS'] = '1'
            os.environ['MKL_NUM_THREADS'] = '1'
            os.environ['NUMEXPR_NUM_THREADS'] = '1'

            print("\n[DEBUG] About to call from_pretrained...", flush=True)
            torch.set_num_threads(1)  # Limit PyTorch threading
            self.model = nemo_asr.models.ASRModel.from_pretrained(
                "nvidia/parakeet-tdt-0.6b-v3"
            )
            print("\n[DEBUG] from_pretrained completed", flush=True)

            # Force garbage collection and malloc trim after model loading
            gc.collect()
            try:
                libc = ctypes.CDLL("libc.so.6")
                libc.malloc_trim(0)
            except:
                pass

            if torch.cuda.is_available():
                self.model = self.model.cuda()
                device_name = torch.cuda.get_device_name(0)
                print(f"✓ ({device_name})")
            else:
                print("✓ (CPU)")

            # Configure GPU-PB word boosting
            boost_file = Path("boost_words.txt")
            if boost_file.exists():
                try:
                    # Read and prepare key phrases (must be capitalized for Parakeet-TDT)
                    with open(boost_file, 'r') as f:
                        key_phrases = [line.strip() for line in f if line.strip()]

                    if key_phrases:
                        print(f"\n[Word Boost] Loaded {len(key_phrases)} phrases: {', '.join(key_phrases)}")

                        # Configure GPU-PB decoding strategy
                        from omegaconf import OmegaConf
                        decoding_cfg = OmegaConf.create({
                            'strategy': 'greedy_batch',
                            'context_score': 1.0,
                            'depth_scaling': 1.0,  # 1.0 for Parakeet-TDT/Canary models
                            'boosting_tree_alpha': 0.3,  # Shallow fusion weight (tune between 0-1)
                            'key_phrases_list': key_phrases
                        })

                        self.model.change_decoding_strategy(decoding_cfg)
                        print("[Word Boost] GPU-PB enabled ✓")
                except Exception as e:
                    print(f"\n[WARNING] Failed to enable word boosting: {e}")
            else:
                print(f"\n[INFO] No boost_words.txt found, word boosting disabled")

            self.model.eval()

            # Initialize frame-based ASR for streaming
            if ENABLE_TRANSCRIPTION:
                self.frame_asr = FrameASR(self.model)
            else:
                self.frame_asr = None

            sys.stdout.flush()
            return True

        except Exception as e:
            print(f"\n[ERROR] Failed to load model: {e}")
            return False

    def transcribe_audio(self, audio_file):
        """Transcribe audio file using NeMo"""
        try:
            with torch.no_grad():
                result = self.model.transcribe([audio_file], verbose=False)

            # Extract text from NeMo result
            if isinstance(result, (list, tuple)) and len(result) > 0:
                first = result[0]
                # Check if it has a .text attribute (Hypothesis object)
                if hasattr(first, 'text'):
                    text = first.text
                elif isinstance(first, str):
                    text = first
                else:
                    text = str(first)
            else:
                text = str(result)

            text = text.strip()

            # Apply word corrections
            text = self.frame_asr.apply_word_corrections(text) if self.frame_asr else text

            return text
        except Exception as e:
            print(f"[ERROR] Transcription failed: {e}")
            return None

    def record_audio_chunk(self, duration_ms=2000):
        """Record audio for specified duration and return temp file path"""
        try:
            device_chunk_size = int(CHUNK_SIZE * self.device_sample_rate / SAMPLE_RATE)

            stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=self.device_sample_rate,
                input=True,
                frames_per_buffer=device_chunk_size
            )

            frames = []
            num_chunks = int(self.device_sample_rate * duration_ms / (1000 * device_chunk_size))

            for _ in range(num_chunks):
                data = stream.read(device_chunk_size, exception_on_overflow=False)
                frames.append(data)

            stream.stop_stream()
            stream.close()

            # Combine frames
            audio_data = b''.join(frames)
            audio_np = np.frombuffer(audio_data, dtype=np.int16)

            # Resample if needed
            if self.needs_resampling:
                audio_np = self._resample_audio(audio_np, self.device_sample_rate, SAMPLE_RATE)

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_path = temp_file.name
            temp_file.close()

            wf = wave.open(temp_path, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.pyaudio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_np.tobytes())
            wf.close()

            return temp_path

        except Exception as e:
            print(f"[ERROR] Recording failed: {e}")
            return None

    def record_until_condition(self, stop_condition, check_interval_ms=50):
        """Record audio until stop condition is met"""
        try:
            device_chunk_size = int(CHUNK_SIZE * self.device_sample_rate / SAMPLE_RATE)

            stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=self.device_sample_rate,
                input=True,
                frames_per_buffer=device_chunk_size
            )

            frames = []
            check_every_n_chunks = max(1, int(self.device_sample_rate * check_interval_ms / (1000 * device_chunk_size)))
            chunk_count = 0

            while not stop_condition():
                data = stream.read(device_chunk_size, exception_on_overflow=False)
                frames.append(data)
                chunk_count += 1

                # Check condition periodically
                if chunk_count >= check_every_n_chunks:
                    chunk_count = 0

            stream.stop_stream()
            stream.close()

            if not frames:
                return None

            # Combine frames
            audio_data = b''.join(frames)
            audio_np = np.frombuffer(audio_data, dtype=np.int16)

            # Resample if needed
            if self.needs_resampling:
                audio_np = self._resample_audio(audio_np, self.device_sample_rate, SAMPLE_RATE)

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_path = temp_file.name
            temp_file.close()

            wf = wave.open(temp_path, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.pyaudio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_np.tobytes())
            wf.close()

            return temp_path

        except Exception as e:
            print(f"[ERROR] Recording failed: {e}")
            return None


    def check_trigger_file(self):
        """Check if trigger file was modified"""
        try:
            if os.path.exists(TRIGGER_FILE):
                mtime = os.path.getmtime(TRIGGER_FILE)
                if mtime > self.last_trigger_time:
                    self.last_trigger_time = mtime
                    return True
        except:
            pass
        return False

    def read_keyboard_events(self, lookback_ms=200):
        """Read recent keyboard events from keyboard_listener.py"""
        try:
            if not os.path.exists(KEYBOARD_EVENT_FILE):
                return []

            current_time = int(time.time() * 1000)
            events = []

            with open(KEYBOARD_EVENT_FILE, 'r') as f:
                lines = f.readlines()
                # Check last 100 lines (most recent events)
                for line in lines[-100:]:
                    line = line.strip()
                    if ':' in line:
                        key, timestamp_str = line.rsplit(':', 1)
                        timestamp = int(timestamp_str)
                        if current_time - timestamp < lookback_ms:
                            events.append(key)

            return events
        except Exception as e:
            return []

    def is_ctrl_pressed(self):
        """Check if Ctrl key was pressed recently"""
        events = self.read_keyboard_events(lookback_ms=200)
        return 'ctrl' in events or 'ctrl_l' in events or 'ctrl_r' in events

    def type_text(self, text):
        """Type text using keyboard"""
        try:
            # Lazy-initialize keyboard controller to avoid threading conflicts
            if self.keyboard is None:
                self.keyboard = Controller()

            for char in text:
                self.keyboard.type(char)
                time.sleep(0.01)  # Small delay between characters
        except Exception as e:
            print(f"[ERROR] Typing failed: {e}")

    def log_conversation(self, text):
        """Log conversation as continuous text"""
        try:
            with open(LOG_FILE, 'a') as f:
                f.write(text + ' ')
        except Exception as e:
            print(f"[ERROR] Logging failed: {e}")

    def check_ai_detection(self, text):
        """
        Check if text is directed at AI.
        Returns: (should_display, is_ai_detected) tuple
        """
        now = time.time()

        # Don't check too frequently (cooldown)
        if now - self.last_detection_time < DETECTION_COOLDOWN:
            return (False, False)

        # Need at least some text in buffer
        buffer_text = self.transcription_buffer.get_text()
        if not buffer_text:
            return (False, False)

        try:
            result = subprocess.run(
                [AI_DETECTOR_PYTHON, AI_DETECTOR_SCRIPT, buffer_text],
                capture_output=True,
                timeout=5,
                text=True
            )

            self.last_detection_time = now
            is_ai_detected = (result.returncode == 0)

            return (True, is_ai_detected)

        except Exception as e:
            print(f"[ERROR] AI detection failed: {e}", file=sys.stderr)
            return (False, False)

    def push_to_talk_mode(self):
        """Push-to-talk: record while Ctrl is held"""
        print("\n[PUSH-TO-TALK] Recording... (release Ctrl to stop)")
        sys.stdout.flush()

        audio_file = self.record_until_condition(
            lambda: not self.is_ctrl_pressed()
        )

        if not audio_file:
            print("[ERROR] Failed to record")
            return

        # Check if file has content
        file_size = os.path.getsize(audio_file)
        if file_size < 20000:
            print("[SILENT] No speech detected")
            os.unlink(audio_file)
            return

        # Transcribe
        text = self.transcribe_audio(audio_file)
        os.unlink(audio_file)

        if text:
            self.log_conversation(text)
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}]")
            print(text)
            sys.stdout.flush()

            self.type_text(text)

    def typing_mode(self):
        """Typing mode: record fixed duration and type with countdown"""
        print("\n[TYPING MODE] Recording... speak now")
        sys.stdout.flush()

        audio_file = self.record_audio_chunk(duration_ms=2000)

        if not audio_file:
            print("[ERROR] Failed to record")
            return

        # Check if file has content
        file_size = os.path.getsize(audio_file)
        if file_size < 20000:
            print("[SILENT] No speech detected")
            os.unlink(audio_file)
            return

        # Transcribe
        text = self.transcribe_audio(audio_file)
        os.unlink(audio_file)

        if text:
            self.log_conversation(text)
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}]")
            print(text)
            sys.stdout.flush()

            for i in range(3, 0, -1):
                time.sleep(1)
                print(f"{i}...")
                sys.stdout.flush()

            self.type_text(text)

    def continuous_logging(self):
        """Main loop: continuous speech capture with AI detection"""
        if not ENABLE_MICROPHONE:
            print("[INFO] Microphone DISABLED (feature flag)")
            print("[INFO] Nothing to do, exiting...")
            return

        if not ENABLE_MODEL:
            print("[INFO] MICROPHONE TEST MODE - Model disabled")
            print("[INFO] Will capture audio but NOT transcribe\n")
        else:
            print("[INFO] Starting continuous speech capture...")
            print("[INFO] Create /tmp/jarvis-type-trigger for typing mode\n")
        sys.stdout.flush()

        # Calculate chunk size for sounddevice
        chunk_duration_sec = CHUNK_SIZE / SAMPLE_RATE  # seconds per chunk

        if DEBUG_MODE:
            print(f"[DEBUG] Will use chunk duration: {chunk_duration_sec}s, rate: {SAMPLE_RATE}Hz")
            sys.stdout.flush()

        # Accumulator for audio chunks
        audio_accumulator = []
        last_ai_check = 0
        chunks_captured = 0

        # sounddevice doesn't need stream opening - just call sd.rec() in the loop
        if DEBUG_MODE:
            print(f"[DEBUG] Audio ready (sounddevice)")
            sys.stdout.flush()

        try:
            iteration = 0
            while not self.shutdown:
                try:
                    iteration += 1
                    if DEBUG_MODE and iteration % 100 == 0:
                        print(f"[DEBUG] Main loop iteration {iteration}", flush=True)

                    # Check for trigger file
                    if self.check_trigger_file():
                        print("\n[TRIGGER DETECTED] Switching to typing mode...")
                        sys.stdout.flush()
                        self.typing_mode()
                        audio_accumulator = []
                        continue

                    # Read audio chunk using sounddevice (returns numpy array directly!)
                    if DEBUG_MODE and iteration == 1:
                        print(f"[DEBUG] About to read first audio chunk (size: {CHUNK_SIZE})", flush=True)
                        sys.stdout.flush()

                    # sounddevice returns numpy array directly - no malloc conflicts!
                    device_chunk_size = int(CHUNK_SIZE * self.device_sample_rate / SAMPLE_RATE)
                    audio_np = sd.rec(device_chunk_size, samplerate=self.device_sample_rate, channels=CHANNELS, dtype='int16', blocking=True)
                    audio_np = audio_np.flatten()  # Convert from (N,1) to (N,)

                    # Resample 48kHz -> 16kHz using simple decimation
                    if self.needs_resampling:
                        audio_np = audio_np[::3]  # Take every 3rd sample

                    if DEBUG_MODE and iteration == 1:
                        print(f"[DEBUG] Successfully read audio chunk, shape: {audio_np.shape}", flush=True)
                        sys.stdout.flush()

                    chunks_captured += 1
                    if DEBUG_MODE and iteration == 1:
                        print(f"[DEBUG] chunks_captured incremented to {chunks_captured}", flush=True)

                    # Convert to float32 (sounddevice already gave us a proper numpy array)
                    if DEBUG_MODE and iteration == 1:
                        print(f"[DEBUG] Converting to float32...", flush=True)
                    audio_float = audio_np.astype(np.float32) / 32768.0

                    if DEBUG_MODE and iteration == 1:
                        print(f"[DEBUG] Appending to accumulator...", flush=True)
                    # Accumulate chunks
                    audio_accumulator.append(audio_float)

                    if DEBUG_MODE and iteration == 1:
                        print(f"[DEBUG] First chunk processed successfully!", flush=True)

                    # Process when we have enough audio (1.6 seconds for frame)
                    total_samples = sum(len(chunk) for chunk in audio_accumulator)
                    if total_samples >= int(FRAME_LEN * SAMPLE_RATE):
                        if DEBUG_MODE:
                            print(f"[DEBUG] Processing frame: {total_samples} samples ({total_samples/SAMPLE_RATE:.2f}s of audio)")
                            sys.stdout.flush()
                        # Combine accumulated audio
                        combined_audio = np.concatenate(audio_accumulator)

                        # MICROPHONE TEST MODE: Just print stats, don't transcribe
                        if not ENABLE_MODEL or not ENABLE_TRANSCRIPTION:
                            print(f"[MIC TEST] Captured {total_samples} samples ({total_samples/SAMPLE_RATE:.2f}s) - max amplitude: {np.max(np.abs(combined_audio)):.3f}")
                            sys.stdout.flush()
                        else:
                            # Transcribe the chunk
                            text = self.frame_asr.transcribe_chunk(combined_audio)

                            if text:
                                # Log to file
                                self.log_conversation(text)

                                # Add to buffer for AI detection
                                self.transcription_buffer.add(text)

                                # Check AI detection periodically
                                if ENABLE_AI_DETECTION:
                                    now = time.time()
                                    if now - last_ai_check >= DETECTION_COOLDOWN:
                                        should_check, is_ai = self.check_ai_detection(text)
                                        if should_check:
                                            timestamp = datetime.now().strftime('%H:%M:%S')
                                            self.display_formatted_output(text, is_ai, timestamp)
                                            last_ai_check = now
                                    else:
                                        # Just print raw text if not checking AI
                                        print(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
                                        sys.stdout.flush()
                                else:
                                    # Just print raw text
                                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
                                    sys.stdout.flush()

                        # Reset accumulator but keep overlap for continuity
                        overlap_samples = int(0.4 * SAMPLE_RATE)  # 400ms overlap
                        if len(combined_audio) > overlap_samples:
                            audio_accumulator = [combined_audio[-overlap_samples:]]
                        else:
                            audio_accumulator = []

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"[ERROR] Main loop error: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(0.1)

        except KeyboardInterrupt:
            pass
        finally:
            # sounddevice cleans up automatically
            pass

    def start(self):
        """Start Jarvis"""
        print("\n╔══════════════════════════════════════════════╗")
        print("║       JARVIS - Speech Logger                 ║")
        print("╚══════════════════════════════════════════════╝")

        # Show audio device info
        if self.needs_resampling:
            print(f"Audio: {self.device_sample_rate}Hz → {SAMPLE_RATE}Hz (sounddevice)")
        else:
            print(f"Audio: {SAMPLE_RATE}Hz (sounddevice)")

        sys.stdout.flush()

        # Clear log files on startup
        try:
            Path(LOG_FILE).write_text('')
            Path("chat-revised.txt").write_text('')
        except Exception as e:
            print(f"[WARNING] Could not clear log files: {e}")

        if not self.load_model():
            return False

        # PyAudio already initialized in __init__ before model loading

        # Start keyboard listener
        print("Starting keyboard listener...", end=' ', flush=True)
        try:
            # DISABLED: subprocess causes memory corruption with PyAudio
            # subprocess.Popen([sys.executable, "keyboard_listener.py"])
            # time.sleep(0.5)
            print("✗ (disabled - causes conflicts)")
        except Exception as e:
            print(f"✗ (push-to-talk unavailable)")

        # Start conversation improver
        print("Starting conversation improver...", end=' ', flush=True)
        try:
            # DISABLED: subprocess may cause conflicts with PyAudio
            # self.conversation_improver_process = subprocess.Popen(
            #     [sys.executable, "conversation_improver.py"],
            #     stdout=subprocess.DEVNULL,
            #     stderr=subprocess.DEVNULL
            # )
            # time.sleep(0.5)
            print("✗ (disabled - causes conflicts)")
        except Exception as e:
            print(f"✗")

        # Initialize improved text cache
        if self.improved_log_path.exists():
            self.load_improved_entries()

        print("\n[READY] Listening... (keyboard logger active)\n")
        sys.stdout.flush()

        # Start main loop
        try:
            self.continuous_logging()
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

        return True

    def load_improved_entries(self):
        """Load new improved text entries from conversation_improved.json"""
        if not self.improved_log_path.exists():
            return

        try:
            with open(self.improved_log_path, 'r') as f:
                f.seek(self.improved_last_position)
                new_content = f.read()
                self.improved_last_position = f.tell()

            if not new_content.strip():
                return

            # Parse new improved entries
            for line in new_content.strip().split('\n'):
                if line.strip():
                    try:
                        entry = json.loads(line)
                        self.improved_cache.append(entry)
                    except json.JSONDecodeError:
                        pass

        except Exception:
            pass  # Silent fail

    def find_improved_text(self, raw_text: str, timestamp: str = None) -> dict:
        """Find the best matching improved text for a raw message"""
        from difflib import SequenceMatcher

        # Load any new entries first
        self.load_improved_entries()

        if not self.improved_cache:
            return None

        # Try to match by timestamp if provided
        if timestamp:
            for entry in self.improved_cache:
                timestamp_start = entry.get('timestamp_start', '')
                timestamp_end = entry.get('timestamp_end', '')

                if timestamp_start <= timestamp <= timestamp_end:
                    return {
                        'improved_text': entry.get('improved_text'),
                        'original_batch': entry.get('original_text')
                    }

        # Try substring match
        best_match = None
        best_score = 0.0

        for entry in self.improved_cache:
            original = entry.get('original_text', '')

            # Check if raw text is a substring
            if raw_text.lower().strip() in original.lower():
                return {
                    'improved_text': entry.get('improved_text'),
                    'original_batch': original
                }

            # Calculate similarity as fallback
            similarity = SequenceMatcher(None, raw_text.lower(), original.lower()).ratio()

            if similarity > best_score:
                best_score = similarity
                best_match = entry

        # Return if similarity is reasonable (>30%)
        if best_score > 0.3 and best_match:
            return {
                'improved_text': best_match.get('improved_text'),
                'original_batch': best_match.get('original_text')
            }

        return None

    def display_formatted_output(self, text: str, is_ai_detected: bool, timestamp: str = None):
        """Display formatted output with raw and improved text"""
        # Find improved text
        improved_data = self.find_improved_text(text, timestamp)

        # Print AI detection status
        if is_ai_detected:
            print("Ai: me", flush=True)
        else:
            print("Ai: not me", flush=True)

        # Always show raw text
        print(f"  Raw: {text}", flush=True)

        # Show batch context if available
        if improved_data:
            original_batch = improved_data.get('original_batch')
            if original_batch:
                # Truncate if too long (show first 150 chars)
                batch_display = original_batch if len(original_batch) <= 150 else original_batch[:150] + "..."
                print(f"  Batch: {batch_display}", flush=True)

            # Show improved text
            improved_text = improved_data.get('improved_text')
            if improved_text:
                print(f"  Improved: {improved_text}", flush=True)
            else:
                print(f"  Improved: (not available yet)", flush=True)
        else:
            print(f"  Improved: (not available yet)", flush=True)

    def cleanup(self):
        """Cleanup resources"""
        self.shutdown = True

        # sounddevice cleans up automatically - no need to terminate

        # Stop conversation improver
        if self.conversation_improver_process:
            try:
                self.conversation_improver_process.terminate()
                self.conversation_improver_process.wait(timeout=2)
            except:
                pass

        # Cleanup keyboard controller (suppress pynput cleanup exception)
        try:
            del self.keyboard
        except:
            pass

        print("\n[STOPPED]")
        sys.stdout.flush()

if __name__ == "__main__":
    import signal

    # Suppress KeyboardInterrupt traceback
    def signal_handler(sig, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        jarvis = Jarvis()
        success = jarvis.start()
        sys.exit(0 if success else 1)
    except Exception as e:
        # Suppress pynput Controller cleanup exceptions
        if 'NoneType' not in str(e):
            print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
