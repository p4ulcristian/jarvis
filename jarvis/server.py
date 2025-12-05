"""Unified Jarvis server - STT + TTS with HTTP API."""

import os
import sys
import signal
import logging
import tempfile
import threading
import queue
import subprocess
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
from nemo.collections.tts.models import FastPitchModel, HifiGanModel

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

# Models
STT_MODEL = "nvidia/canary-1b-v2"
TTS_FASTPITCH = "nvidia/tts_en_fastpitch"
TTS_HIFIGAN = "nvidia/tts_hifigan"
STT_SAMPLE_RATE = 16000
TTS_SAMPLE_RATE = 22050

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


class JarvisServer:
    def __init__(self):
        self.stt_model = None
        self.tts_spec = None
        self.tts_vocoder = None
        self.recorder = AudioRecorder()
        self.recording = False
        self._load_models()

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
            except Exception as e:
                print(f"Playback error: {e}", flush=True)
            finally:
                self._audio_queue.task_done()

    def queue_speak(self, text: str):
        """Synthesize text and queue for playback."""
        audio_buffer = self.synthesize(text)
        self._audio_queue.put(audio_buffer.read())

    def _load_models(self):
        print("Loading STT model (Canary)...", flush=True)
        with _quiet():
            self.stt_model = EncDecMultiTaskModel.from_pretrained(STT_MODEL, map_location='cpu')
            self.stt_model = self.stt_model.half().cuda()
            self.stt_model.eval()
        print("STT ready", flush=True)

        print("Loading TTS models (FastPitch + HiFi-GAN)...", flush=True)
        with _quiet():
            self.tts_spec = FastPitchModel.from_pretrained(TTS_FASTPITCH)
            self.tts_spec = self.tts_spec.half().cuda()
            self.tts_spec.eval()

            self.tts_vocoder = HifiGanModel.from_pretrained(TTS_HIFIGAN)
            self.tts_vocoder = self.tts_vocoder.half().cuda()
            self.tts_vocoder.eval()
        print("TTS ready", flush=True)

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

    def synthesize(self, text: str) -> bytes:
        """Convert text to speech, return WAV bytes."""
        with torch.no_grad():
            parsed = self.tts_spec.parse(text)
            spectrogram = self.tts_spec.generate_spectrogram(tokens=parsed)
            audio = self.tts_vocoder.convert_spectrogram_to_audio(spec=spectrogram)
        audio_np = audio.cpu().float().numpy()[0]

        import io
        buffer = io.BytesIO()
        sf.write(buffer, audio_np, TTS_SAMPLE_RATE, format='WAV')
        buffer.seek(0)
        return buffer

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
    """TTS endpoint. POST {"text": "..."} -> queues audio for playback"""
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "missing 'text' field"}), 400

    text = data['text']
    server.queue_speak(text)
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
