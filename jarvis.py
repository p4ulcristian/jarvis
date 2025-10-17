#!/home/paul/Work/jarvis/venv/bin/python
"""
JARVIS - Voice-to-Text System with Streaming NeMo ASR
Continuous speech logging with push-to-talk and typing modes
"""

import os
import sys

# Save original stderr
_original_stderr = sys.stderr

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
import threading
import queue
from pathlib import Path
from datetime import datetime
from collections import deque
import logging
import warnings

# Suppress warnings and verbose output
warnings.filterwarnings('ignore')
logging.getLogger().setLevel(logging.ERROR)

import torch
import numpy as np
import nemo.collections.asr as nemo_asr
import pyaudio
import wave
from pynput.keyboard import Controller

# Restore stderr after ALSA imports
sys.stderr = _original_stderr
_devnull.close()

# Suppress NeMo's verbose logging
import nemo.utils
logging.getLogger('nemo_logger').setLevel(logging.ERROR)

# Constants
SAMPLE_RATE = 16000
CHUNK_SIZE = 1600  # 100ms chunks at 16kHz
CHANNELS = 1
TRIGGER_FILE = "/tmp/jarvis-type-trigger"
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


class StreamingAudioBuffer:
    """Continuous audio buffer for real-time streaming"""
    def __init__(self, sample_rate=SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.buffer = queue.Queue()
        self.is_active = False

    def get_chunk(self, timeout=0.1):
        """Get next audio chunk as raw bytes"""
        try:
            return self.buffer.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear(self):
        """Clear the buffer"""
        while not self.buffer.empty():
            try:
                self.buffer.get_nowait()
            except queue.Empty:
                break


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
        # Convert to int16 range for amplitude check
        audio_int16 = (audio * 32768).astype(np.int16)

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
            # Convert back to int16 for wav file
            audio_int16 = (self.buffer * 32768).astype(np.int16)
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

            # Filter out empty or very short hallucinations
            if len(text) < 2:
                return ""

            # Apply word corrections
            text = self.apply_word_corrections(text)

            # Filter common hallucination phrases
            text_lower = text.lower()
            if text_lower in HALLUCINATION_PHRASES:
                return ""

            # Deduplication: check if same as previous
            if text == self.prev_text:
                self.prev_text_count += 1
                # If we see the same text 3+ times, it's likely a hallucination
                if self.prev_text_count >= 3:
                    return ""
                # Otherwise skip duplicate
                return ""

            # New text detected
            self.prev_text = text
            self.prev_text_count = 1

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

        # Suppress ALSA warnings during PyAudio initialization
        _stderr_backup = sys.stderr
        sys.stderr = open(os.devnull, 'w')
        self.pyaudio = pyaudio.PyAudio()
        sys.stderr.close()
        sys.stderr = _stderr_backup

        # Detect supported sample rate
        self.device_sample_rate = self._detect_sample_rate()
        self.needs_resampling = (self.device_sample_rate != SAMPLE_RATE)

        self.keyboard = Controller()
        self.transcription_buffer = TranscriptionBuffer()
        self.streaming_buffer = StreamingAudioBuffer()
        self.frame_asr = None
        self.audio_thread = None
        self.last_trigger_time = 0
        self.last_detection_time = 0
        self.shutdown = False
        self.streaming_mode = False
        self.conversation_improver_process = None

        # Improved text cache
        self.improved_cache = deque(maxlen=100)
        self.improved_log_path = Path("chat-revised.txt")
        self.improved_last_position = 0

    def _detect_sample_rate(self):
        """Detect a supported sample rate for the default input device"""
        # Just use 48000 Hz which is widely supported
        # Avoid multiple stream opens which can cause PyAudio/ALSA corruption
        return 48000

    def _resample_audio(self, audio_data, orig_rate, target_rate):
        """Resample audio from orig_rate to target_rate using linear interpolation"""
        if orig_rate == target_rate:
            return audio_data

        if len(audio_data) == 0:
            return audio_data

        # Calculate resampling ratio
        ratio = target_rate / orig_rate
        new_length = int(len(audio_data) * ratio)

        if new_length == 0:
            return np.array([], dtype=np.int16)

        # Use numpy interpolation
        try:
            indices = np.linspace(0, len(audio_data) - 1, new_length)
            resampled = np.interp(indices, np.arange(len(audio_data)), audio_data.astype(np.float64))
            return resampled.astype(np.int16)
        except Exception as e:
            print(f"[ERROR] Resampling failed: {e}", file=sys.stderr)
            return audio_data

    def load_model(self):
        """Load NeMo ASR model with word boosting"""
        print("Loading NeMo Parakeet-TDT model...", end=' ', flush=True)

        try:
            self.model = nemo_asr.models.ASRModel.from_pretrained(
                "nvidia/parakeet-tdt-0.6b-v3"
            )

            if torch.cuda.is_available():
                self.model = self.model.cuda()
                device_name = torch.cuda.get_device_name(0)
                print(f"✓ ({device_name})")
            else:
                print("✓ (CPU)")

            self.model.eval()

            # Initialize frame-based ASR for streaming
            self.frame_asr = FrameASR(self.model)

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

    def type_text(self, text):
        """Type text using keyboard"""
        try:
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

    def audio_capture_thread(self):
        """Background thread for continuous audio capture"""
        try:
            # Use device sample rate directly - NO numpy operations in this thread
            # Any numpy operations cause segfaults in background thread
            device_chunk_size = int(CHUNK_SIZE * self.device_sample_rate / SAMPLE_RATE)

            stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=self.device_sample_rate,
                input=True,
                frames_per_buffer=device_chunk_size
            )

            while self.streaming_mode and not self.shutdown:
                try:
                    # Read audio chunk - keep as raw bytes
                    audio_data = stream.read(device_chunk_size, exception_on_overflow=False)

                    # Store raw bytes directly - no numpy operations
                    # Conversion happens in main thread when processing
                    self.streaming_buffer.buffer.put(audio_data)

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"[ERROR] Audio capture error: {e}", file=sys.stderr)
                    time.sleep(0.1)

            stream.stop_stream()
            stream.close()

        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"[ERROR] Audio thread failed: {e}")
            self.streaming_mode = False

    def start_streaming_capture(self):
        """Start background audio capture"""
        if not self.streaming_mode:
            self.streaming_mode = True
            self.streaming_buffer.clear()
            self.audio_thread = threading.Thread(target=self.audio_capture_thread, daemon=True)
            self.audio_thread.start()
            time.sleep(0.2)  # Let thread initialize

    def stop_streaming_capture(self):
        """Stop background audio capture"""
        if self.streaming_mode:
            self.streaming_mode = False
            if self.audio_thread:
                self.audio_thread.join(timeout=1.0)
            self.streaming_buffer.clear()


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
        """Main loop: trigger file only for typing mode"""
        print("[INFO] Create /tmp/jarvis-type-trigger for typing mode\n")
        sys.stdout.flush()

        try:
            while not self.shutdown:
                try:
                    # Check for trigger file
                    if self.check_trigger_file():
                        print("\n[TRIGGER DETECTED] Switching to typing mode...")
                        sys.stdout.flush()
                        self.typing_mode()
                        continue

                    # Just sleep and wait for user input
                    time.sleep(0.1)

                except Exception as e:
                    print(f"[ERROR] Main loop error: {e}")
                    time.sleep(0.1)

        except KeyboardInterrupt:
            pass

    def start(self):
        """Start Jarvis"""
        print("\n╔══════════════════════════════════════════════╗")
        print("║       JARVIS - Speech Logger                 ║")
        print("╚══════════════════════════════════════════════╝")

        # Show audio device info
        if self.needs_resampling:
            print(f"Audio: {self.device_sample_rate}Hz → 16kHz (resampling)")
        else:
            print(f"Audio: {self.device_sample_rate}Hz")

        sys.stdout.flush()

        # Clear log files on startup
        try:
            Path(LOG_FILE).write_text('')
            Path("chat-revised.txt").write_text('')
        except Exception as e:
            print(f"[WARNING] Could not clear log files: {e}")

        if not self.load_model():
            return False

        # Start keyboard listener
        print("Starting keyboard listener...", end=' ', flush=True)
        try:
            subprocess.Popen([sys.executable, "keyboard_listener.py"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            time.sleep(0.5)
            print("✓")
        except Exception as e:
            print(f"✗ (push-to-talk unavailable)")

        # Start conversation improver
        print("Starting conversation improver...", end=' ', flush=True)
        try:
            self.conversation_improver_process = subprocess.Popen(
                [sys.executable, "conversation_improver.py"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(0.5)
            print("✓")
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
        self.stop_streaming_capture()

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

        # Terminate pyaudio safely
        try:
            if hasattr(self, 'pyaudio') and self.pyaudio:
                self.pyaudio.terminate()
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
