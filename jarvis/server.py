"""Unified Jarvis server - STT (NeMo) + TTS (Kokoro) with HTTP API."""

import os
import sys
import signal
import logging
import tempfile
import threading
import queue
import subprocess
import time
import requests
from pathlib import Path

# Suppress NeMo logging spam before imports
os.environ['NEMO_LOG_LEVEL'] = 'ERROR'
os.environ['HYDRA_FULL_ERROR'] = '0'
logging.disable(logging.WARNING)

import warnings
warnings.filterwarnings('ignore')

# Suppress stdout/stderr during imports
_stdout, _stderr = sys.stdout, sys.stderr
sys.stdout = sys.stderr = open(os.devnull, 'w')

import torch
import numpy as np
import soundfile as sf
from flask import Flask, request, jsonify
from nemo.collections.asr.models import EncDecMultiTaskModel

sys.stdout, sys.stderr = _stdout, _stderr
logging.disable(logging.NOTSET)

# Suppress Flask/Werkzeug logs
logging.getLogger('werkzeug').setLevel(logging.ERROR)

from jarvis.audio import AudioRecorder
from jarvis.output import paste_text
from jarvis.ptt import PTTListener

# Config
HOST = "127.0.0.1"
PORT = 8765
PID_FILE = Path("/tmp/jarvis.pid")

# Kokoro TTS config
KOKORO_URL = "http://127.0.0.1:7123"
KOKORO_START_SCRIPT = Path("/home/paul/Work/kokoro/start.sh")
KOKORO_VOICE = "bf_isabella"

# STT config
STT_MODEL = "nvidia/canary-1b-v2"
STT_SAMPLE_RATE = 16000

app = Flask(__name__)


def _quiet():
    """Context manager to suppress stdout/stderr."""
    class Quiet:
        def __enter__(self):
            self._stdout, self._stderr = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = open(os.devnull, 'w')
            return self
        def __exit__(self, *args):
            sys.stdout, sys.stderr = self._stdout, self._stderr
    return Quiet()


def ensure_kokoro_running():
    """Start Kokoro TTS server if not already running."""
    try:
        resp = requests.get(f"{KOKORO_URL}/health", timeout=1)
        if resp.status_code == 200:
            print("Kokoro TTS already running", flush=True)
            return True
    except requests.exceptions.ConnectionError:
        pass

    print("Starting Kokoro TTS server...", flush=True)
    subprocess.Popen(
        [str(KOKORO_START_SCRIPT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )

    # Wait for Kokoro to be ready
    for _ in range(60):  # Wait up to 60 seconds
        time.sleep(1)
        try:
            resp = requests.get(f"{KOKORO_URL}/health", timeout=1)
            if resp.status_code == 200:
                print("Kokoro TTS ready", flush=True)
                return True
        except requests.exceptions.ConnectionError:
            pass

    print("Warning: Kokoro TTS failed to start", flush=True)
    return False


class JarvisServer:
    def __init__(self):
        self.stt_model = None
        self.recorder = AudioRecorder()
        self.recording = False
        self._load_stt_model()

        # Audio playback queue
        self._audio_queue = queue.Queue()
        self._playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self._playback_thread.start()

    def _playback_worker(self):
        """Background thread that plays audio from the queue."""
        while True:
            audio_bytes = self._audio_queue.get()
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as f:
                    f.write(audio_bytes)
                    f.flush()
                    subprocess.run(['mpv', '--no-video', '--really-quiet', f.name],
                                   check=False, capture_output=True)
                # Brief pause between clips
                time.sleep(0.3)
            except Exception as e:
                print(f"Playback error: {e}", flush=True)
            finally:
                self._audio_queue.task_done()

    def queue_speak(self, text: str, voice: str = KOKORO_VOICE, speed: float = 1.0):
        """Request TTS from Kokoro and queue for playback."""
        # Clean text: replace newlines/tabs with spaces, collapse multiple spaces
        import re
        # Handle both literal \n strings and actual newlines
        text = text.replace('\\n', ' ').replace('\\r', ' ').replace('\\t', ' ')
        text = re.sub(r'[\n\r\t]+', ' ', text)
        text = re.sub(r' +', ' ', text).strip()
        if not text:
            return

        try:
            resp = requests.post(
                f"{KOKORO_URL}/speak",
                json={"text": text, "voice": voice, "speed": speed},
                timeout=30
            )
            if resp.status_code == 200:
                self._audio_queue.put(resp.content)
            else:
                print(f"Kokoro TTS error: {resp.status_code}", flush=True)
        except Exception as e:
            print(f"TTS error: {e}", flush=True)

    def _load_stt_model(self):
        print("Loading STT model (Canary)...", flush=True)
        with _quiet():
            self.stt_model = EncDecMultiTaskModel.from_pretrained(STT_MODEL, map_location='cpu')
            self.stt_model = self.stt_model.half().cuda()
            self.stt_model.eval()
        print("STT ready", flush=True)

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio to text."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as f:
            sf.write(f.name, audio, STT_SAMPLE_RATE)
            with _quiet():
                result = self.stt_model.transcribe([f.name], source_lang='en', target_lang='en', verbose=False)
        if result and len(result) > 0:
            hyp = result[0]
            text = hyp.text if hasattr(hyp, 'text') else str(hyp)
            return text.strip()
        return ""

    def start_recording(self):
        if self.recording:
            return
        self.recording = True
        print("Recording...", flush=True)
        self.recorder.start()

    def stop_recording(self) -> str:
        if not self.recording:
            return ""
        self.recording = False
        print("Processing...", flush=True)
        audio = self.recorder.stop()
        if audio is not None and len(audio) > 0:
            text = self.transcribe(audio)
            if text:
                print(f"Transcribed: {text}")
                return text
        return ""


# Global server instance
server = None


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


@app.route('/speak', methods=['POST'])
def speak():
    """TTS endpoint. POST {"text": "...", "voice": "...", "speed": 1.0} -> queues audio"""
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "missing 'text' field"}), 400

    text = data['text']
    voice = data.get('voice', KOKORO_VOICE)
    speed = data.get('speed', 1.0)
    server.queue_speak(text, voice=voice, speed=speed)
    return jsonify({"status": "queued"})


@app.route('/listen', methods=['POST'])
def listen():
    """STT endpoint. POST audio file -> {"text": "..."}"""
    if 'audio' not in request.files:
        return jsonify({"error": "missing 'audio' file"}), 400

    audio_file = request.files['audio']
    audio_data, sr = sf.read(audio_file)

    # Resample if needed
    if sr != STT_SAMPLE_RATE:
        import librosa
        audio_data = librosa.resample(audio_data, orig_sr=sr, target_sr=STT_SAMPLE_RATE)

    text = server.transcribe(audio_data.astype(np.float32))
    return jsonify({"text": text})


@app.route('/ptt/start', methods=['POST'])
def ptt_start():
    """Start push-to-talk recording."""
    server.start_recording()
    return jsonify({"status": "recording"})


@app.route('/ptt/stop', methods=['POST'])
def ptt_stop():
    """Stop recording and transcribe."""
    text = server.stop_recording()
    if text:
        paste_text(text)
    return jsonify({"text": text})


def handle_ptt_press():
    """CapsLock press - start recording."""
    server.start_recording()


def handle_ptt_release():
    """CapsLock release - stop and transcribe."""
    text = server.stop_recording()
    if text:
        paste_text(text)


def shutdown(signum, frame):
    PID_FILE.unlink(missing_ok=True)
    sys.exit(0)


def main():
    global server

    # Write PID file
    PID_FILE.write_text(str(os.getpid()))

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    ptt_listener = None
    try:
        # Start Kokoro TTS if needed
        ensure_kokoro_running()

        # Load STT model
        server = JarvisServer()

        # Start PTT listener (evdev-based, no device grab)
        ptt_listener = PTTListener(
            on_press=handle_ptt_press,
            on_release=handle_ptt_release
        )
        ptt_listener.start()

        print(f"Jarvis server running on http://{HOST}:{PORT}", flush=True)
        print("Hold CapsLock to record", flush=True)

        app.run(host=HOST, port=PORT, threaded=True, use_reloader=False)
    finally:
        if ptt_listener:
            ptt_listener.stop()
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
