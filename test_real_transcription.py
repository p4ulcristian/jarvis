#!/usr/bin/env python3
"""
Test transcription with real audio capture
"""
import sys
sys.path.insert(0, 'source-code')

from core import Config, AudioCapture, setup_logging
from core.transcription import load_nemo_model, FrameASR
import logging

# Enable ALL logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)-8s | %(message)s')

print("="*60)
print("REAL TRANSCRIPTION TEST")
print("="*60)

config = Config()
print(f"\n1. Loading model: {config.model_name}")
model = load_nemo_model(config)

if not model:
    print("ERROR: Model failed to load!")
    sys.exit(1)

print("\n2. Creating FrameASR...")
frame_asr = FrameASR(model, config)

print("\n3. Creating AudioCapture...")
audio = AudioCapture(config)

print("\n4. Capturing and transcribing 10 chunks...")
print("(Netflix should be playing NOW)")
print()

for i in range(10):
    print(f"\n--- Chunk {i+1}/10 ---")

    # Capture audio
    chunk = audio.capture_chunk()
    if chunk is None:
        print("ERROR: Failed to capture audio")
        continue

    # Check energy
    max_amp, avg_amp = AudioCapture.calculate_energy(chunk)
    print(f"  Audio: max={max_amp:5.0f}, avg={avg_amp:5.1f}")

    # Transcribe
    try:
        text = frame_asr.transcribe_chunk(chunk)
        if text:
            print(f"  ✓ GOT TEXT: '{text}'")
        else:
            print(f"  ✗ No text (empty result)")
    except Exception as e:
        print(f"  ERROR during transcription: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*60)
print("Test complete!")
print("="*60)
