#!/usr/bin/env python3
"""
hear.py - Continuous streaming transcription with Parakeet-TDT-0.6B-v3
Listens continuously and prints concatenated text without newlines
"""
import os
import sys
import logging
import subprocess
import queue
from threading import Thread

# Fix PyTorch deprecation warning - BEFORE importing torch
if 'PYTORCH_CUDA_ALLOC_CONF' in os.environ:
    os.environ['PYTORCH_ALLOC_CONF'] = os.environ.pop('PYTORCH_CUDA_ALLOC_CONF')

import numpy as np
import sounddevice as sd
import torch

# Setup CUDA compatibility for cuda-python 13.x with NeMo
import cuda_compat

# Suppress NeMo logging
os.environ['HYDRA_FULL_ERROR'] = '0'
os.environ['NEMO_LOG_LEVEL'] = 'ERROR'
logging.getLogger('nemo_logger').setLevel(logging.CRITICAL)
logging.getLogger('nemo').setLevel(logging.CRITICAL)
logging.getLogger('pytorch_lightning').setLevel(logging.CRITICAL)

import nemo.collections.asr as nemo_asr

# Configuration
MODEL_SAMPLE_RATE = 16000  # What the model expects
AUDIO_SAMPLE_RATE = 48000  # What the microphone supports (Arctis 7X+)
CHUNK_DURATION = 0.64  # 640ms chunks for good latency/accuracy balance
CHUNK_SIZE = int(AUDIO_SAMPLE_RATE * CHUNK_DURATION)
VAD_THRESHOLD = 0.01  # Voice activity detection threshold
WAKE_WORD = "jarvis"

# Find Arctis microphone
def find_arctis_mic():
    """Find the Arctis 7X+ microphone device"""
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'arctis' in device['name'].lower() and device['max_input_channels'] > 0:
            return i
    return None  # Use default if not found

# Audio buffer queue
audio_queue = queue.Queue()

def audio_callback(indata, frames, time, status):
    """Called by sounddevice for each audio chunk - runs concurrently"""
    if status:
        print(f"\nAudio status: {status}", file=sys.stderr)
    # Add audio to queue (recording continues while we process)
    audio_queue.put(indata[:, 0].copy())


class StreamingASR:
    """Streaming ASR with cache state management"""

    def __init__(self, model_name="nvidia/parakeet-tdt-0.6b-v3"):
        print("Loading Parakeet-TDT-0.6B-v3 model...", flush=True)
        self.model = nemo_asr.models.ASRModel.from_pretrained(model_name)
        self.model.eval()

        if torch.cuda.is_available():
            self.model = self.model.to('cuda')
            print(f"Model loaded on GPU: {torch.cuda.get_device_name(0)}", flush=True)
        else:
            print("Model loaded on CPU", flush=True)

        # CUDA graphs enabled with cuda-python 12.x for faster inference
        # Change to greedy decoding (required for TDT models)
        if hasattr(self.model, 'change_decoding_strategy'):
            self.model.change_decoding_strategy(decoding_cfg=self.model.cfg.decoding)

        self.preprocessor = self.model.preprocessor
        self.reset_state()

    def reset_state(self):
        """Reset streaming cache state"""
        self.cache_last_channel = None
        self.cache_last_time = None
        self.cache_last_channel_len = None
        self.previous_hypotheses = None
        self.previous_pred_out = None

    def has_speech(self, audio_chunk):
        """Simple energy-based VAD"""
        return np.abs(audio_chunk).max() > VAD_THRESHOLD

    def process_chunk(self, audio_chunk):
        """Process audio chunk with streaming inference"""
        # Skip silence
        if not self.has_speech(audio_chunk):
            return None

        # Resample from 44100 to 16000 Hz
        import scipy.signal as signal
        resampled = signal.resample(audio_chunk, int(len(audio_chunk) * MODEL_SAMPLE_RATE / AUDIO_SAMPLE_RATE))
        resampled = resampled.astype(np.float32)

        # Prepare tensors
        audio_signal = torch.tensor(resampled, dtype=torch.float32).unsqueeze(0)
        audio_signal_len = torch.tensor([len(resampled)], dtype=torch.int32)

        if torch.cuda.is_available():
            audio_signal = audio_signal.cuda()
            audio_signal_len = audio_signal_len.cuda()

        with torch.no_grad():
            # Preprocess audio
            processed_signal, processed_signal_length = self.preprocessor(
                input_signal=audio_signal,
                length=audio_signal_len
            )

            # Streaming step with cache
            (
                self.previous_pred_out,
                transcribed_texts,
                self.cache_last_channel,
                self.cache_last_time,
                self.cache_last_channel_len,
                self.previous_hypotheses,
            ) = self.model.conformer_stream_step(
                processed_signal=processed_signal,
                processed_signal_length=processed_signal_length,
                cache_last_channel=self.cache_last_channel,
                cache_last_time=self.cache_last_time,
                cache_last_channel_len=self.cache_last_channel_len,
                keep_all_outputs=True,
                previous_hypotheses=self.previous_hypotheses,
                previous_pred_out=self.previous_pred_out,
                drop_extra_pre_encoded=None,
                return_transcription=True,
            )

        # Extract text from hypothesis
        text = ""
        if self.previous_hypotheses and len(self.previous_hypotheses) > 0:
            hyp = self.previous_hypotheses[0]
            if hasattr(hyp, 'text'):
                text = hyp.text

        return text


def main():
    """Main continuous transcription loop"""
    print("JARVIS Voice Assistant - Streaming Mode")
    print("=" * 60)

    # Initialize ASR
    asr = StreamingASR()

    # Find Arctis microphone
    mic_device = find_arctis_mic()
    if mic_device is not None:
        print(f"Using microphone: {sd.query_devices(mic_device)['name']}")
    else:
        print("Using default microphone")

    # Start audio stream with callback
    stream = sd.InputStream(
        callback=audio_callback,
        channels=1,
        samplerate=AUDIO_SAMPLE_RATE,
        blocksize=CHUNK_SIZE,
        dtype=np.float32,
        device=mic_device
    )

    print("\nListening continuously...")
    print("Speak naturally - text will appear without gaps")
    print("Press Ctrl+C to stop\n")
    print("-" * 60, flush=True)

    stream.start()

    last_text = ""
    wake_word_detected = False
    silence_chunks = 0
    SILENCE_RESET_THRESHOLD = 5  # Reset after ~3 seconds of silence

    try:
        while True:
            try:
                # Get audio chunk from queue (blocks until available)
                chunk = audio_queue.get(timeout=1.0)

                # Check if there's speech
                has_speech = asr.has_speech(chunk)

                if not has_speech:
                    silence_chunks += 1
                    # Reset state after prolonged silence (end of utterance)
                    if silence_chunks >= SILENCE_RESET_THRESHOLD and last_text:
                        print(" ", flush=True)  # Space after utterance
                        asr.reset_state()
                        last_text = ""
                        silence_chunks = 0
                        wake_word_detected = False
                    continue
                else:
                    silence_chunks = 0

                # Process chunk (while recording continues)
                text = asr.process_chunk(chunk)

                if text and text != last_text:
                    # Print only new text (no newlines, continuous output)
                    new_text = text[len(last_text):] if text.startswith(last_text) else text

                    if new_text:
                        # Print without newline - continuous stream
                        print(new_text, end='', flush=True)

                        # Check for wake word
                        if WAKE_WORD in text.lower() and not wake_word_detected:
                            wake_word_detected = True
                            print(f"\n[Wake word detected!]", flush=True)
                            # Reset for next command
                            asr.reset_state()
                            last_text = ""
                            silence_chunks = 0
                            continue

                    last_text = text

            except queue.Empty:
                continue

    except KeyboardInterrupt:
        print("\n\nShutting down...", flush=True)

    finally:
        stream.stop()
        stream.close()
        print("Stream closed.", flush=True)


if __name__ == "__main__":
    main()
