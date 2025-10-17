#!/home/paul/Work/jarvis/venv/bin/python
"""
JARVIS - Voice-to-Text System with Streaming NeMo ASR
Continuous speech logging with push-to-talk and typing modes
"""

import os
import sys
import time
import queue
import threading
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from collections import deque

import torch
import nemo.collections.asr as nemo_asr
import pyaudio
import wave
import numpy as np
from pynput.keyboard import Controller, Key

# Constants
SAMPLE_RATE = 16000
CHUNK_SIZE = 1600  # 100ms chunks at 16kHz
CHANNELS = 1
TRIGGER_FILE = "/tmp/jarvis-type-trigger"
KEYBOARD_STATE_FILE = "/tmp/jarvis-ctrl-state"
LOG_FILE = "conversation.jsonl"

# AI Detection
AI_DETECTOR_SCRIPT = "ai-detector/ai_detector_cli.py"
AI_DETECTOR_PYTHON = "ai-detector/venv/bin/python"
DETECTION_COOLDOWN = 30  # seconds
BUFFER_DURATION = 300  # 5 minutes in seconds

class AudioBuffer:
    """Thread-safe audio buffer for streaming"""
    def __init__(self):
        self.buffer = queue.Queue()
        self.is_recording = False

    def add(self, data):
        self.buffer.put(data)

    def get_all(self):
        chunks = []
        while not self.buffer.empty():
            try:
                chunks.append(self.buffer.get_nowait())
            except queue.Empty:
                break
        return b''.join(chunks) if chunks else None

    def clear(self):
        while not self.buffer.empty():
            try:
                self.buffer.get_nowait()
            except queue.Empty:
                break

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
        self.pyaudio = pyaudio.PyAudio()
        self.keyboard = Controller()
        self.audio_buffer = AudioBuffer()
        self.transcription_buffer = TranscriptionBuffer()
        self.last_trigger_time = 0
        self.last_detection_time = 0
        self.shutdown = False

    def load_model(self):
        """Load NeMo ASR model"""
        print("\n[INIT] Loading NeMo Parakeet-TDT-1.1B model...")
        sys.stdout.flush()

        try:
            self.model = nemo_asr.models.ASRModel.from_pretrained(
                "nvidia/parakeet-tdt-1.1b"
            )

            if torch.cuda.is_available():
                self.model = self.model.cuda()
                device_name = torch.cuda.get_device_name(0)
                gpu_mem = torch.cuda.memory_allocated(0) / 1024**3
                print(f"[OK] Model loaded on GPU: {device_name}")
                print(f"[OK] GPU Memory: {gpu_mem:.2f} GB")
            else:
                print("[WARNING] CUDA not available, using CPU")

            self.model.eval()
            print("[OK] NeMo model ready!")
            sys.stdout.flush()
            return True

        except Exception as e:
            print(f"[ERROR] Failed to load model: {e}")
            return False

    def transcribe_audio(self, audio_file):
        """Transcribe audio file using NeMo"""
        try:
            with torch.no_grad():
                result = self.model.transcribe([audio_file])

            # Extract text from NeMo result
            if isinstance(result, (list, tuple)) and len(result) > 0:
                first = result[0]
                if isinstance(first, (list, tuple)) and len(first) > 0:
                    text_elem = first[0]
                    if isinstance(text_elem, (list, tuple)) and len(text_elem) > 0:
                        text = str(text_elem[0])
                    else:
                        text = str(text_elem)
                else:
                    text = str(first)
            else:
                text = str(result)

            return text.strip()
        except Exception as e:
            print(f"[ERROR] Transcription failed: {e}")
            return None

    def record_audio_chunk(self, duration_ms=2000):
        """Record audio for specified duration and return temp file path"""
        try:
            stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )

            frames = []
            num_chunks = int(SAMPLE_RATE * duration_ms / (1000 * CHUNK_SIZE))

            for _ in range(num_chunks):
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)

            stream.stop_stream()
            stream.close()

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_path = temp_file.name
            temp_file.close()

            wf = wave.open(temp_path, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.pyaudio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))
            wf.close()

            return temp_path

        except Exception as e:
            print(f"[ERROR] Recording failed: {e}")
            return None

    def record_until_condition(self, stop_condition, check_interval_ms=50):
        """Record audio until stop condition is met"""
        try:
            stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )

            frames = []
            check_every_n_chunks = max(1, int(SAMPLE_RATE * check_interval_ms / (1000 * CHUNK_SIZE)))
            chunk_count = 0

            while not stop_condition():
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)
                chunk_count += 1

                # Check condition periodically
                if chunk_count >= check_every_n_chunks:
                    chunk_count = 0

            stream.stop_stream()
            stream.close()

            if not frames:
                return None

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_path = temp_file.name
            temp_file.close()

            wf = wave.open(temp_path, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.pyaudio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))
            wf.close()

            return temp_path

        except Exception as e:
            print(f"[ERROR] Recording failed: {e}")
            return None

    def is_ctrl_pressed(self):
        """Check if Ctrl key is pressed"""
        try:
            if os.path.exists(KEYBOARD_STATE_FILE):
                with open(KEYBOARD_STATE_FILE, 'r') as f:
                    return f.read().strip() == '1'
        except:
            pass
        return False

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

    def log_conversation(self, text, speaker="user"):
        """Log conversation to JSONL file"""
        try:
            import json
            entry = {
                'timestamp': datetime.now().isoformat(),
                'speaker': speaker,
                'text': text
            }
            with open(LOG_FILE, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            print(f"[ERROR] Logging failed: {e}")

    def check_ai_detection(self):
        """Check if text is directed at AI"""
        now = time.time()
        if now - self.last_detection_time < DETECTION_COOLDOWN:
            return False

        text = self.transcription_buffer.get_text()
        if not text:
            return False

        try:
            result = subprocess.run(
                [AI_DETECTOR_PYTHON, AI_DETECTOR_SCRIPT, text],
                capture_output=True,
                timeout=5
            )

            if result.returncode == 0:
                self.last_detection_time = now
                return True

        except Exception as e:
            print(f"[ERROR] AI detection failed: {e}")

        return False

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
            print("\n" + "=" * 60)
            print("[TYPING]")
            print(text)
            print("=" * 60)
            sys.stdout.flush()

            self.type_text(text)
            print("[OK] Typed successfully")
            sys.stdout.flush()

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
            print("\n" + "=" * 60)
            print("[WILL TYPE]")
            print(text)
            print("=" * 60)
            print("\n>>> CLICK WHERE YOU WANT TO TYPE NOW! <<<")
            print("Typing in 3 seconds...")
            sys.stdout.flush()

            for i in range(3, 0, -1):
                time.sleep(1)
                print(f"{i}...")
                sys.stdout.flush()

            print("[TYPING NOW]")
            sys.stdout.flush()
            self.type_text(text)
            print("[OK] Typed successfully")
            sys.stdout.flush()

    def continuous_logging(self):
        """Main loop: continuous speech logging"""
        print("\n[LISTENING] Continuous speech-to-text logging started")
        print(f"[INFO] Speaking now - everything will be logged")
        print(f"[INFO] To type mode: touch {TRIGGER_FILE}")
        print("[INFO] Push-to-talk: Hold Ctrl key while speaking\n")
        sys.stdout.flush()

        while not self.shutdown:
            try:
                # Check for push-to-talk (Ctrl pressed)
                if self.is_ctrl_pressed():
                    self.push_to_talk_mode()
                    continue

                # Check for trigger file
                if self.check_trigger_file():
                    print("\n[TRIGGER DETECTED] Switching to typing mode...")
                    sys.stdout.flush()
                    self.typing_mode()
                    continue

                # Record and transcribe 2-second chunk
                start_time = time.time()
                audio_file = self.record_audio_chunk(duration_ms=2000)
                record_time = time.time()

                if not audio_file:
                    continue

                # Check if file has content
                file_size = os.path.getsize(audio_file)
                if file_size < 20000:
                    os.unlink(audio_file)
                    continue

                # Transcribe
                text = self.transcribe_audio(audio_file)
                transcribe_time = time.time()
                os.unlink(audio_file)

                if text:
                    # Add to buffer
                    self.transcription_buffer.add(text)

                    # Log
                    self.log_conversation(text)

                    # Print timestamp and text
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}]")
                    print(text)
                    sys.stdout.flush()

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[ERROR] Loop error: {e}")
                time.sleep(0.5)

    def start(self):
        """Start Jarvis"""
        print("\n╔════════════════════════════════════════════════════════════╗")
        print("║         JARVIS - Continuous Speech Logger                  ║")
        print("╚════════════════════════════════════════════════════════════╝")
        sys.stdout.flush()

        if not self.load_model():
            return False

        # Start keyboard listener
        print("\n[INIT] Starting keyboard listener...")
        sys.stdout.flush()
        try:
            subprocess.Popen([sys.executable, "keyboard_listener.py"])
            time.sleep(0.5)
            print("[OK] Keyboard listener ready (Ctrl for push-to-talk)")
        except Exception as e:
            print(f"[WARNING] Keyboard listener failed: {e}")
            print("[INFO] Push-to-talk will not be available")

        sys.stdout.flush()

        # Start main loop
        try:
            self.continuous_logging()
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Stopping...")
        finally:
            self.cleanup()

        return True

    def cleanup(self):
        """Cleanup resources"""
        self.shutdown = True
        self.pyaudio.terminate()
        print("[OK] Goodbye!")
        sys.stdout.flush()

if __name__ == "__main__":
    jarvis = Jarvis()
    success = jarvis.start()
    sys.exit(0 if success else 1)
