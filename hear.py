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

# Configuration - Optimized for Parakeet-TDT-0.6B-v3
MODEL_SAMPLE_RATE = 16000  # What the model expects
AUDIO_SAMPLE_RATE = 48000  # What the microphone supports (Arctis 7X+)
RECORD_CHUNK_DURATION = 0.1  # 100ms recording chunks - small for responsive capture
RECORD_CHUNK_SIZE = int(AUDIO_SAMPLE_RATE * RECORD_CHUNK_DURATION)

# Optimal buffer settings based on NVIDIA recommendations
INFERENCE_CHUNK_DURATION = 2.0  # Primary chunk for inference (1.6-2.0s recommended)
LEFT_CONTEXT_DURATION = 10.0    # Left context for better accuracy (maximum recommended)
RIGHT_CONTEXT_DURATION = 2.0    # Right context (maximum recommended)
TOTAL_BUFFER_DURATION = LEFT_CONTEXT_DURATION + INFERENCE_CHUNK_DURATION + RIGHT_CONTEXT_DURATION

# Calculate buffer sizes in samples (at model rate)
INFERENCE_CHUNK_SIZE = int(MODEL_SAMPLE_RATE * INFERENCE_CHUNK_DURATION)
LEFT_CONTEXT_SIZE = int(MODEL_SAMPLE_RATE * LEFT_CONTEXT_DURATION)
RIGHT_CONTEXT_SIZE = int(MODEL_SAMPLE_RATE * RIGHT_CONTEXT_DURATION)
TOTAL_BUFFER_SIZE = int(MODEL_SAMPLE_RATE * TOTAL_BUFFER_DURATION)

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

# Audio buffer queue - large enough to buffer during inference
audio_queue = queue.Queue(maxsize=50)

def audio_callback(indata, frames, time, status):
    """Called by sounddevice for each audio chunk - runs concurrently"""
    if status:
        print(f"\nAudio status: {status}", file=sys.stderr)
    # Add audio to queue (recording continues while we process)
    audio_queue.put(indata[:, 0].copy())


class SimpleASR:
    """Simple batch ASR optimized for streaming with Parakeet-TDT-0.6B-v3"""

    def __init__(self, model_name="nvidia/parakeet-tdt-0.6b-v3", use_local_attention=True):
        print("Loading Parakeet-TDT-0.6B-v3 model...", flush=True)
        self.model = nemo_asr.models.ASRModel.from_pretrained(model_name)
        self.model.eval()

        if torch.cuda.is_available():
            self.model = self.model.to('cuda')
            print(f"Model loaded on GPU: {torch.cuda.get_device_name(0)}", flush=True)
        else:
            print("Model loaded on CPU", flush=True)

        # Enable local attention for long-form continuous listening (up to 3 hours)
        # This reduces memory footprint and improves streaming performance
        if use_local_attention:
            try:
                self.model.change_attention_model("rel_pos_local_attn", att_context_size=[128, 128])
                self.model.change_subsampling_conv_chunking_factor(1)
                print("Local attention enabled (supports up to 3 hours continuous audio)", flush=True)
            except Exception as e:
                print(f"Note: Could not enable local attention: {e}", flush=True)

    def has_speech(self, audio_chunk):
        """Simple energy-based VAD"""
        return np.abs(audio_chunk).max() > VAD_THRESHOLD

    def transcribe_audio(self, audio_chunk):
        """Transcribe audio chunk using regular batch inference (expects pre-resampled audio at 16kHz)"""
        # Skip silence
        if not self.has_speech(audio_chunk):
            return None

        # Save to temporary file for transcription
        import tempfile
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name
            sf.write(temp_path, audio_chunk, MODEL_SAMPLE_RATE)

        try:
            # Use regular transcribe method - much more reliable (suppress progress bar)
            import logging
            logging.getLogger('nemo_logger').setLevel(logging.CRITICAL)
            transcriptions = self.model.transcribe([temp_path], verbose=False)
            if transcriptions and len(transcriptions) > 0:
                result = transcriptions[0]
                # Extract text from Hypothesis object
                if hasattr(result, 'text'):
                    return result.text
                elif isinstance(result, str):
                    return result
            return None
        finally:
            import os
            os.unlink(temp_path)


def inference_worker(asr, audio_queue, result_queue, stop_event):
    """Worker thread with context-based windowing for optimal inference"""
    import scipy.signal as signal
    DEBUG = os.environ.get('DEBUG_HEAR', '0') == '1'

    # Maintain a sliding window buffer with left context, inference chunk, and right context
    audio_history = []  # All accumulated audio chunks at native sample rate
    history_duration = 0.0

    # Track samples at model rate (after resampling)
    resampled_history = np.array([], dtype=np.float32)

    # Track cumulative transcription to avoid duplicates
    cumulative_text = ""
    last_output_text = ""

    while not stop_event.is_set():
        try:
            # Get audio chunk with timeout so we can check stop_event
            chunk = audio_queue.get(timeout=0.1)

            # Add to history
            audio_history.append(chunk)
            history_duration += RECORD_CHUNK_DURATION

            # Process when we have enough audio for inference chunk + contexts
            if history_duration >= TOTAL_BUFFER_DURATION:
                # Concatenate all chunks
                full_audio = np.concatenate(audio_history)

                # Resample to model rate
                resampled = signal.resample(full_audio, int(len(full_audio) * MODEL_SAMPLE_RATE / AUDIO_SAMPLE_RATE))
                resampled = resampled.astype(np.float32)

                # Update resampled history
                resampled_history = resampled

                # Extract the inference window (with left and right context)
                # We want: [LEFT_CONTEXT | INFERENCE_CHUNK | RIGHT_CONTEXT]
                total_samples = len(resampled)

                # Check if there's speech in the inference chunk region
                inference_start = LEFT_CONTEXT_SIZE
                inference_end = inference_start + INFERENCE_CHUNK_SIZE

                if inference_end > total_samples:
                    # Not enough samples yet, continue accumulating
                    continue

                inference_region = resampled[inference_start:inference_end]
                has_speech = asr.has_speech(inference_region)

                if not has_speech:
                    result_queue.put(('silence', None))
                    # Slide window: keep last (LEFT_CONTEXT + small overlap)
                    keep_duration = LEFT_CONTEXT_DURATION + 0.5  # Keep 2.5s
                    keep_chunks = int(keep_duration / RECORD_CHUNK_DURATION)
                    audio_history = audio_history[-keep_chunks:] if keep_chunks > 0 else []
                    history_duration = len(audio_history) * RECORD_CHUNK_DURATION
                    continue

                if DEBUG:
                    print(f"\n[DEBUG] Processing window: {total_samples/MODEL_SAMPLE_RATE:.2f}s total, {inference_region.shape[0]/MODEL_SAMPLE_RATE:.2f}s inference chunk", file=sys.stderr)

                # Transcribe using the full buffer (with context)
                text = asr.transcribe_audio(resampled)

                if DEBUG and text:
                    print(f"[DEBUG] Inference returned: '{text}'", file=sys.stderr)

                if text:
                    result_queue.put(('text', text))

                # Slide the window forward by keeping left context + half of inference chunk
                # This provides overlap while advancing through the audio
                keep_duration = LEFT_CONTEXT_DURATION + (INFERENCE_CHUNK_DURATION / 2)
                keep_chunks = int(keep_duration / RECORD_CHUNK_DURATION)
                audio_history = audio_history[-keep_chunks:] if keep_chunks > 0 else []
                history_duration = len(audio_history) * RECORD_CHUNK_DURATION

        except queue.Empty:
            # If we have buffered audio but queue is empty, process what we have
            if history_duration >= (LEFT_CONTEXT_DURATION + 0.8):  # At least 0.8s of inference chunk
                full_audio = np.concatenate(audio_history)
                resampled = signal.resample(full_audio, int(len(full_audio) * MODEL_SAMPLE_RATE / AUDIO_SAMPLE_RATE))
                resampled = resampled.astype(np.float32)

                if asr.has_speech(resampled):
                    text = asr.transcribe_audio(resampled)
                    if text:
                        result_queue.put(('text', text))

                # Clear most of the buffer but keep some context
                keep_chunks = int(LEFT_CONTEXT_DURATION / RECORD_CHUNK_DURATION)
                audio_history = audio_history[-keep_chunks:] if keep_chunks > 0 else []
                history_duration = len(audio_history) * RECORD_CHUNK_DURATION
            continue
        except Exception as e:
            print(f"\n[ERROR] Inference worker: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            audio_history = []
            history_duration = 0.0
            resampled_history = np.array([], dtype=np.float32)
            continue


def main():
    """Main continuous transcription loop"""
    print("JARVIS Voice Assistant - Streaming Mode (Optimized)")
    print("=" * 60)
    print(f"Buffer Config: {INFERENCE_CHUNK_DURATION}s chunk + {LEFT_CONTEXT_DURATION}s left + {RIGHT_CONTEXT_DURATION}s right context")
    print(f"Total window: {TOTAL_BUFFER_DURATION}s")
    print("=" * 60)

    # Initialize ASR with local attention for long-form listening
    asr = SimpleASR(use_local_attention=True)

    # Find Arctis microphone
    mic_device = find_arctis_mic()
    if mic_device is not None:
        print(f"Using microphone: {sd.query_devices(mic_device)['name']}")
    else:
        print("Using default microphone")

    # Start audio stream with callback (small chunks for responsive capture)
    stream = sd.InputStream(
        callback=audio_callback,
        channels=1,
        samplerate=AUDIO_SAMPLE_RATE,
        blocksize=RECORD_CHUNK_SIZE,
        dtype=np.float32,
        device=mic_device
    )

    print("\nListening continuously...")
    print("Speak naturally - text will appear without gaps")
    print("Press Ctrl+C to stop\n")
    print("-" * 60, flush=True)

    stream.start()

    # Start inference worker thread
    result_queue = queue.Queue()
    stop_event = Thread._stop = False
    from threading import Event
    stop_event = Event()

    worker = Thread(target=inference_worker, args=(asr, audio_queue, result_queue, stop_event), daemon=True)
    worker.start()

    last_text = ""
    wake_word_detected = False
    silence_chunks = 0
    SILENCE_RESET_THRESHOLD = 5  # Reset after ~3 seconds of silence

    # Debug mode
    DEBUG = os.environ.get('DEBUG_HEAR', '0') == '1'

    try:
        while True:
            try:
                # Get results from inference worker (non-blocking check)
                event_type, data = result_queue.get(timeout=0.1)

                if event_type == 'silence':
                    silence_chunks += 1
                    # Reset state after prolonged silence (end of utterance)
                    if silence_chunks >= SILENCE_RESET_THRESHOLD and last_text:
                        print("\n", flush=True)  # Newline after utterance
                        last_text = ""
                        silence_chunks = 0
                        wake_word_detected = False
                    continue

                elif event_type == 'text':
                    silence_chunks = 0
                    text = data

                    if DEBUG and text:
                        print(f"\n[DEBUG] Main loop got: '{text}' (len={len(text)})", file=sys.stderr)
                        print(f"[DEBUG] Last text was: '{last_text}' (len={len(last_text)})", file=sys.stderr)

                    if text and text != last_text:
                        # Print new text only (continuous stream)
                        if last_text and text.startswith(last_text):
                            # Print only the new part
                            new_part = text[len(last_text):]
                            print(new_part, end='', flush=True)
                        else:
                            # Different text, print with space separator
                            if last_text:
                                print(' ', end='', flush=True)
                            print(text, end='', flush=True)

                        # Check for wake word
                        if WAKE_WORD in text.lower() and not wake_word_detected:
                            wake_word_detected = True
                            print(f"\n[Wake word detected!]", flush=True)
                            # Reset for next command
                            last_text = ""
                            silence_chunks = 0
                            continue

                        last_text = text

            except queue.Empty:
                continue

    except KeyboardInterrupt:
        print("\n\nShutting down...", flush=True)

    finally:
        stop_event.set()
        worker.join(timeout=2.0)
        stream.stop()
        stream.close()
        print("Stream closed.", flush=True)


if __name__ == "__main__":
    main()
