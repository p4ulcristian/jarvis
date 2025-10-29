#!/usr/bin/env python3
"""
Isolated Transcription Test
Tests ONLY the transcription pipeline: audio capture -> VAD -> transcription
Perfect for testing with Netflix or other audio playing
"""
import sys
import time
import logging
from pathlib import Path

# Add source-code to path
sys.path.insert(0, str(Path(__file__).parent / 'source-code'))

# Set up logging to see everything
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger('test')

def main():
    logger.info("="*70)
    logger.info("TRANSCRIPTION TEST - Isolated Test")
    logger.info("="*70)

    # Step 1: Load config
    logger.info("\n[1/4] Loading configuration...")
    try:
        from core.config import Config
        config = Config()
        logger.info(f"✓ Config loaded: sample_rate={config.sample_rate}, chunk_size={config.chunk_size}")
        logger.info(f"✓ VAD settings: threshold={config.silence_threshold}, min_speech_ratio={config.min_speech_ratio}")
        logger.info(f"✓ Model: {config.model_name}")
    except Exception as e:
        logger.error(f"✗ Failed to load config: {e}")
        return 1

    # Step 2: Load NeMo model
    logger.info("\n[2/4] Loading NeMo model (this takes 10-60 seconds)...")
    try:
        from core.transcription import load_nemo_model, FrameASR

        model = load_nemo_model(config)
        if model is None:
            logger.error("✗ Model failed to load!")
            return 1

        logger.info("✓ Model loaded successfully")

        # Initialize FrameASR
        frame_asr = FrameASR(model, config)
        logger.info("✓ FrameASR initialized")
        logger.info(f"✓ Streaming support: {frame_asr.supports_streaming}")

    except Exception as e:
        logger.error(f"✗ Failed to load model: {e}", exc_info=True)
        return 1

    # Step 3: Initialize audio capture
    logger.info("\n[3/4] Initializing audio capture...")
    try:
        from core import AudioCapture

        audio_capture = AudioCapture(config)
        logger.info(f"✓ Audio capture initialized")
        logger.info(f"✓ Device sample rate: {config.device_sample_rate} Hz")
        logger.info(f"✓ Model sample rate: {config.sample_rate} Hz")
        logger.info(f"✓ Chunk size: {config.chunk_size} samples")

    except Exception as e:
        logger.error(f"✗ Failed to initialize audio: {e}", exc_info=True)
        return 1

    # Step 4: Start transcription test
    logger.info("\n[4/4] Starting transcription test...")
    logger.info("="*70)
    logger.info("LISTENING... (Play Netflix or speak)")
    logger.info("Press Ctrl+C to stop")
    logger.info("="*70)

    chunk_count = 0
    speech_count = 0
    transcription_count = 0

    try:
        while True:
            # Capture audio chunk
            audio_chunk = audio_capture.capture_chunk()
            if audio_chunk is None:
                continue

            chunk_count += 1

            # Calculate audio levels
            max_amp, avg_amp = AudioCapture.calculate_energy(audio_chunk)

            # Check for speech using VAD
            has_speech = frame_asr.has_speech(audio_chunk, debug=True)

            if has_speech:
                speech_count += 1
                logger.info(f"🎤 SPEECH DETECTED | Chunk #{chunk_count} | Max: {max_amp:.0f} | Avg: {avg_amp:.1f}")

                # Transcribe the chunk
                logger.info("   Transcribing...")
                start_time = time.time()
                text = frame_asr.transcribe_chunk(audio_chunk)
                elapsed = time.time() - start_time

                if text:
                    transcription_count += 1
                    logger.info(f"   ✓ TRANSCRIPTION: '{text}' ({elapsed*1000:.0f}ms)")
                    logger.info("")
                else:
                    logger.warning(f"   ✗ No text returned ({elapsed*1000:.0f}ms)")
                    logger.info("")
            else:
                # Just show audio level for silence (every 10th chunk)
                if chunk_count % 10 == 0:
                    logger.debug(f"Silence | Chunk #{chunk_count} | Max: {max_amp:.0f} | Avg: {avg_amp:.1f}")

    except KeyboardInterrupt:
        logger.info("\n" + "="*70)
        logger.info("TEST SUMMARY")
        logger.info("="*70)
        logger.info(f"Total chunks captured: {chunk_count}")
        logger.info(f"Chunks with speech detected: {speech_count}")
        logger.info(f"Successful transcriptions: {transcription_count}")

        if speech_count == 0:
            logger.warning("\n⚠️  No speech detected!")
            logger.warning("   - Check that audio is playing (Netflix, YouTube, etc.)")
            logger.warning("   - Check microphone/system audio capture")
            logger.warning(f"   - VAD threshold may be too high (current: {config.silence_threshold})")
        elif transcription_count == 0:
            logger.warning("\n⚠️  Speech detected but no transcriptions!")
            logger.warning("   - Model may not be returning text")
            logger.warning("   - Filtering may be too aggressive")
            logger.warning("   - Check logs above for details")
        else:
            logger.info(f"\n✓ SUCCESS! Transcribed {transcription_count} chunks")

        logger.info("="*70)

    except Exception as e:
        logger.error(f"\n✗ Test failed: {e}", exc_info=True)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
