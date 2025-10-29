#!/home/paul/Work/jarvis/source-code/venv/bin/python
"""
Test the buffering and transcription logic
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'source-code'))

import time
import logging
import numpy as np
import torch
import nemo.collections.asr as nemo_asr
from core import Config, AudioCapture
from core.transcription import FrameASR

# Setup logging to see everything
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("="*60)
print("BUFFERING TEST")
print("="*60)

# Load config and model
config = Config()
print(f"\nLoading model: {config.model_name}")
model = nemo_asr.models.ASRModel.from_pretrained(config.model_name)
if torch.cuda.is_available():
    model = model.cuda()
    print(f"Model on GPU: {torch.cuda.get_device_name(0)}")
else:
    print("Model on CPU")

model.eval()

# Initialize components
print("\nInitializing audio capture...")
audio_capture = AudioCapture(config)

print("Initializing ASR...")
frame_asr = FrameASR(model, config)

print("\n" + "="*60)
print("SPEAK NOW - Recording for 5 seconds...")
print("="*60 + "\n")

# Simulate the main loop
start_time = time.time()
chunk_count = 0
transcription_count = 0

while time.time() - start_time < 5.0:
    # Capture chunk
    audio_chunk = audio_capture.capture_chunk()
    if audio_chunk is None:
        continue

    chunk_count += 1

    # Calculate audio level
    max_amp = np.max(np.abs(audio_chunk * 32768))

    # Check for speech
    has_speech = frame_asr.has_speech(audio_chunk, debug=False)

    if has_speech:
        print(f"[Chunk {chunk_count:3d}] SPEECH detected (max_amp: {max_amp:.0f})")
        frame_asr.add_speech_chunk(audio_chunk)
    else:
        print(f"[Chunk {chunk_count:3d}] silence (max_amp: {max_amp:.0f})")
        frame_asr.silence_count += 1

    # Check if should transcribe
    if frame_asr.should_transcribe():
        buffered_audio = frame_asr.get_buffered_audio()

        if len(buffered_audio) > 0:
            duration = len(buffered_audio) / config.sample_rate
            print(f"\n{'='*60}")
            print(f"TRANSCRIBING {duration:.2f}s of audio...")
            print(f"{'='*60}")

            text = frame_asr.transcribe_chunk(buffered_audio)
            transcription_count += 1

            print(f"\n>>> TRANSCRIPTION #{transcription_count}: '{text}'")
            print(f"{'='*60}\n")

    time.sleep(0.01)

print("\n" + "="*60)
print(f"TEST COMPLETE")
print(f"Total chunks: {chunk_count}")
print(f"Total transcriptions: {transcription_count}")
print("="*60)
