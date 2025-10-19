#!/home/paul/Work/jarvis/source-code/venv/bin/python
"""
Test NeMo FastConformer streaming API to see what it returns
"""
import sys
import os
from pathlib import Path

# Add source-code to path
sys.path.insert(0, str(Path(__file__).parent / 'source-code'))

import time
import logging
import numpy as np
import torch
import nemo.collections.asr as nemo_asr

# Import from JARVIS core
from core import Config, AudioCapture

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_streaming_model():
    """Test the streaming model and inspect outputs"""

    # Load config
    config = Config()

    logger.info("Initializing audio capture...")
    audio_capture = AudioCapture(config)

    logger.info("Loading NeMo FastConformer Streaming model...")
    model = nemo_asr.models.ASRModel.from_pretrained(config.model_name)

    if torch.cuda.is_available():
        model = model.cuda()
        logger.info(f"Model loaded on GPU: {torch.cuda.get_device_name(0)}")
    else:
        logger.info("Model loaded on CPU")

    model.eval()

    # Check streaming support
    has_stream_step = hasattr(model, 'conformer_stream_step')
    logger.info(f"Has conformer_stream_step: {has_stream_step}")

    if not has_stream_step:
        logger.error("Model doesn't support conformer_stream_step!")
        return

    # Initialize streaming state
    cache_last_channel = None
    cache_last_time = None
    cache_last_channel_len = None
    previous_hypotheses = None
    previous_pred_out = None

    # Capture audio for 2 seconds
    logger.info("Recording 2 seconds of audio... SPEAK NOW!")
    chunks = []
    for i in range(20):  # 20 chunks = 2 seconds
        chunk = audio_capture.capture_chunk()
        if chunk is not None:
            chunks.append(chunk)
        time.sleep(0.05)

    logger.info(f"Captured {len(chunks)} audio chunks")

    # Process each chunk
    preprocessor = model.preprocessor

    for i, chunk in enumerate(chunks):
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing chunk {i+1}/{len(chunks)}")
        logger.info(f"Chunk shape: {chunk.shape}, max: {np.max(np.abs(chunk)):.3f}")

        # Prepare audio
        audio_signal = torch.tensor(chunk, dtype=torch.float32).unsqueeze(0)
        audio_signal_len = torch.tensor([len(chunk)], dtype=torch.int32)

        if torch.cuda.is_available():
            audio_signal = audio_signal.cuda()
            audio_signal_len = audio_signal_len.cuda()

        with torch.no_grad():
            # Preprocess
            processed_signal, processed_signal_length = preprocessor(
                input_signal=audio_signal,
                length=audio_signal_len
            )

            # Call streaming API
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

        # INSPECT THE OUTPUTS
        logger.info(f"\n--- Output Inspection ---")
        logger.info(f"previous_hypotheses type: {type(previous_hypotheses)}")
        logger.info(f"previous_hypotheses: {previous_hypotheses}")

        if previous_hypotheses:
            if isinstance(previous_hypotheses, list):
                logger.info(f"  Length: {len(previous_hypotheses)}")
                if len(previous_hypotheses) > 0:
                    hyp = previous_hypotheses[0]
                    logger.info(f"  First element type: {type(hyp)}")
                    logger.info(f"  First element: {hyp}")
                    logger.info(f"  Dir: {[attr for attr in dir(hyp) if not attr.startswith('_')]}")

                    # Try to extract text
                    if hasattr(hyp, 'text'):
                        logger.info(f"  ✓ hyp.text = '{hyp.text}'")
                    if hasattr(hyp, 'y_sequence'):
                        logger.info(f"  hyp.y_sequence = {hyp.y_sequence}")
                    if hasattr(hyp, 'score'):
                        logger.info(f"  hyp.score = {hyp.score}")

        logger.info(f"\ntranscribed_texts type: {type(transcribed_texts)}")
        logger.info(f"transcribed_texts: {transcribed_texts}")

        if transcribed_texts:
            if isinstance(transcribed_texts, list):
                logger.info(f"  Length: {len(transcribed_texts)}")
                if len(transcribed_texts) > 0:
                    result = transcribed_texts[0]
                    logger.info(f"  First element type: {type(result)}")
                    logger.info(f"  First element: {result}")
                    if hasattr(result, 'text'):
                        logger.info(f"  ✓ result.text = '{result.text}'")

        logger.info(f"previous_pred_out type: {type(previous_pred_out)}")
        if previous_pred_out is not None:
            if isinstance(previous_pred_out, torch.Tensor):
                logger.info(f"  Shape: {previous_pred_out.shape}")

        time.sleep(0.05)

if __name__ == "__main__":
    try:
        test_streaming_model()
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
