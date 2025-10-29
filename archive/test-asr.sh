#!/bin/bash
# Test script for NVIDIA Parakeet-TDT-0.6B-v3 ASR model
# Continuous voice transcription with batched audio processing
# Usage: ./test-asr.sh [duration_seconds]

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Parakeet-TDT-0.6B-v3 Continuous ASR Test ===${NC}"
echo ""

# Find project root and virtual environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${SCRIPT_DIR}/source-code/venv"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}Error: Virtual environment not found at $VENV_PATH${NC}"
    echo "Please run from the jarvis project root directory"
    exit 1
fi

# Use virtual environment Python
PYTHON="${VENV_PATH}/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo -e "${RED}Error: Python not found in virtual environment${NC}"
    exit 1
fi

echo -e "${GREEN}Running indefinitely - Press Ctrl+C to stop${NC}"
echo -e "${YELLOW}Speak into your microphone...${NC}"
echo ""

# Run Python test script with venv Python
"$PYTHON" << PYTHON_SCRIPT
import os
import sys
import time
import wave
import tempfile
import numpy as np
from datetime import datetime
from pathlib import Path

# Suppress NeMo logging
os.environ['HYDRA_FULL_ERROR'] = '0'
os.environ['NEMO_LOG_LEVEL'] = 'ERROR'

import logging
logging.getLogger('nemo_logger').setLevel(logging.CRITICAL)
logging.getLogger('nemo').setLevel(logging.CRITICAL)
logging.getLogger('pytorch_lightning').setLevel(logging.CRITICAL)
logging.getLogger('lhotse').setLevel(logging.CRITICAL)
logging.getLogger('hydra').setLevel(logging.CRITICAL)

print("=" * 80)
print("LOADING PARAKEET-TDT-0.6B-v3 MODEL")
print("=" * 80)

load_start = time.time()

import torch
import nemo.collections.asr as nemo_asr

# Load the model
model = nemo_asr.models.ASRModel.from_pretrained(
    model_name="nvidia/parakeet-tdt-0.6b-v3"
)

# Move to GPU if available
if torch.cuda.is_available():
    model = model.cuda()
    device = f"GPU: {torch.cuda.get_device_name(0)}"
    vram_gb = torch.cuda.memory_allocated(0) / 1024**3
else:
    device = "CPU"
    vram_gb = 0

model.eval()

load_time = time.time() - load_start

print(f"✓ Model loaded in {load_time:.2f}s")
print(f"  Device: {device}")
if torch.cuda.is_available():
    print(f"  VRAM: {vram_gb:.2f} GB")
print(f"  Languages: 25 European languages with auto-detection")
print(f"  Architecture: FastConformer-TDT (600M params)")
print()

# Audio settings
SAMPLE_RATE = 16000
CHUNK_DURATION = 3.0  # Process every 3 seconds of audio
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)
CHANNELS = 1
FORMAT_BYTES = 2  # 16-bit audio

print("=" * 80)
print(f"CONTINUOUS TRANSCRIPTION TEST - INDEFINITE MODE")
print("=" * 80)
print(f"Settings:")
print(f"  Sample rate: {SAMPLE_RATE} Hz")
print(f"  Batch duration: {CHUNK_DURATION}s")
print(f"  Mode: Continuous (Ctrl+C to stop)")
print()

try:
    import pyaudio

    p = pyaudio.PyAudio()

    # Find default input device
    print("🎤 Opening microphone...")

    stream = p.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=1024
    )

    print("✓ Microphone ready")
    print()
    print("=" * 80)
    print("TRANSCRIPTION LOG (batched, no overlap, no gaps)")
    print("=" * 80)
    print()

    # Transcription loop (indefinite)
    batch_num = 0
    start_time = time.time()
    full_transcript = ""

    while True:
        batch_num += 1

        # Read exactly CHUNK_DURATION seconds of audio
        frames_to_read = int(SAMPLE_RATE * CHUNK_DURATION)
        audio_data = stream.read(frames_to_read, exception_on_overflow=False)

        # Convert to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Save to temporary WAV file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        wav_path = temp_file.name
        temp_file.close()

        with wave.open(wav_path, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(FORMAT_BYTES)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes((audio_np * 32768).astype(np.int16).tobytes())

        # Transcribe
        transcribe_start = time.time()

        with torch.no_grad():
            hypotheses = model.transcribe([wav_path], return_hypotheses=True)

        transcribe_time = time.time() - transcribe_start

        # Extract text
        text = ""
        if hypotheses and len(hypotheses) > 0:
            hyp = hypotheses[0]
            if isinstance(hyp, list) and len(hyp) > 0:
                text = hyp[0].text if hasattr(hyp[0], 'text') else str(hyp[0])
            elif hasattr(hyp, 'text'):
                text = hyp.text
            else:
                text = str(hyp)

        # Clean up temp file
        os.unlink(wav_path)

        # Calculate RTFx
        rtfx = CHUNK_DURATION / transcribe_time if transcribe_time > 0 else 0

        # Add to full transcript
        if text.strip():
            full_transcript += " " + text.strip()

        # Log output
        timestamp = datetime.now().strftime("%H:%M:%S")
        elapsed = time.time() - start_time
        batch_start = (batch_num - 1) * CHUNK_DURATION
        batch_end = batch_num * CHUNK_DURATION

        print(f"[{timestamp}] Batch {batch_num} | RTFx: {rtfx:.1f}x")
        print(f"Full transcript: {full_transcript.strip()}")
        print()

except ImportError:
    print()
    print("ERROR: pyaudio not installed")
    print("Install with: pip install pyaudio")
    sys.exit(1)

except KeyboardInterrupt:
    print()
    print("=" * 80)
    print("TRANSCRIPTION STOPPED BY USER")
    print("=" * 80)
    print(f"Total batches processed: {batch_num}")
    print(f"Total time: {time.time() - start_time:.1f}s")
    print()
    print("✓ Shutting down gracefully...")

    # Close audio stream
    try:
        stream.stop_stream()
        stream.close()
        p.terminate()
    except:
        pass

    sys.exit(0)

except Exception as e:
    print()
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

PYTHON_SCRIPT
