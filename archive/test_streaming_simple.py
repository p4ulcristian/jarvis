#!/home/paul/Work/jarvis/source-code/venv/bin/python
"""
Simple streaming test - shows what the model returns
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'source-code'))

import time
import numpy as np
import torch
import nemo.collections.asr as nemo_asr
from core import Config, AudioCapture

print("Loading model...")
config = Config()
model = nemo_asr.models.ASRModel.from_pretrained(config.model_name)
if torch.cuda.is_available():
    model = model.cuda()
model.eval()

print("Initializing audio...")
audio_capture = AudioCapture(config)

# Initialize streaming state
cache_last_channel = None
cache_last_time = None
cache_last_channel_len = None
previous_hypotheses = None
previous_pred_out = None

preprocessor = model.preprocessor

print("\n" + "="*60)
print("SPEAK NOW - Recording for 3 seconds...")
print("="*60 + "\n")

chunk_count = 0
for i in range(30):  # 3 seconds
    chunk = audio_capture.capture_chunk()
    if chunk is None:
        continue

    chunk_count += 1

    # Prepare audio
    audio_signal = torch.tensor(chunk, dtype=torch.float32).unsqueeze(0)
    audio_signal_len = torch.tensor([len(chunk)], dtype=torch.int32)

    if torch.cuda.is_available():
        audio_signal = audio_signal.cuda()
        audio_signal_len = audio_signal_len.cuda()

    with torch.no_grad():
        processed_signal, processed_signal_length = preprocessor(
            input_signal=audio_signal,
            length=audio_signal_len
        )

        (
            previous_pred_out,
            transcribed_texts,
            cache_last_channel,
            cache_last_time,
            cache_last_channel_len,
            previous_hypotheses,
        ) = model.conformer_stream_step(
            processed_signal=processed_signal,
            processed_signal_length=processed_signal_length,
            cache_last_channel=cache_last_channel,
            cache_last_time=cache_last_time,
            cache_last_channel_len=cache_last_channel_len,
            keep_all_outputs=True,
            previous_hypotheses=previous_hypotheses,
            previous_pred_out=previous_pred_out,
            drop_extra_pre_encoded=None,
            return_transcription=True,
        )

    # Extract text
    text = ""
    if previous_hypotheses and len(previous_hypotheses) > 0:
        hyp = previous_hypotheses[0]
        if hasattr(hyp, 'text'):
            text = hyp.text

    # Show output
    if text:
        print(f"[Chunk {chunk_count:2d}] TEXT: '{text}'")
    else:
        print(f"[Chunk {chunk_count:2d}] (empty)")

    time.sleep(0.05)

print("\n" + "="*60)
print("Done!")
print("="*60)
