#!/usr/bin/env python3
"""
Test script for FastConformer streaming implementation
Verifies that the streaming API is working correctly
"""

import sys
import time
import logging
from pathlib import Path

# Add source-code to path
sys.path.insert(0, str(Path(__file__).parent / 'source-code'))

from core import Config, setup_logging
from core.transcription import load_nemo_model, FrameASR
import numpy as np

def test_model_loading():
    """Test that the model loads with streaming support"""
    print("\n" + "="*60)
    print("TEST 1: Model Loading and Streaming Support")
    print("="*60)

    config = Config()
    config.enable_model = True

    print(f"Loading model: {config.model_name}")
    model = load_nemo_model(config)

    if model is None:
        print("❌ FAIL: Model failed to load")
        return False

    print("✓ Model loaded successfully")

    # Check for streaming support
    has_stream_step = hasattr(model, 'conformer_stream_step')
    has_set_streaming = hasattr(model, 'set_streaming_mode')

    print(f"  - has conformer_stream_step: {has_stream_step}")
    print(f"  - has set_streaming_mode: {has_set_streaming}")

    if not has_stream_step:
        print("⚠ WARNING: Model doesn't support conformer_stream_step")
        print("  This might not be a streaming model!")
        return False

    print("✓ Model supports streaming API")
    return True


def test_frame_asr_initialization():
    """Test FrameASR initialization"""
    print("\n" + "="*60)
    print("TEST 2: FrameASR Initialization")
    print("="*60)

    config = Config()
    config.enable_model = True

    model = load_nemo_model(config)
    if model is None:
        print("❌ FAIL: Could not load model")
        return False

    print("Creating FrameASR instance...")
    frame_asr = FrameASR(model, config)

    # Check state initialization
    print("Checking state variables:")
    print(f"  - supports_streaming: {frame_asr.supports_streaming}")
    print(f"  - cache_last_channel: {frame_asr.cache_last_channel}")
    print(f"  - cache_last_time: {frame_asr.cache_last_time}")
    print(f"  - previous_hypotheses: {frame_asr.previous_hypotheses}")
    print(f"  - previous_pred_out: {frame_asr.previous_pred_out}")

    if not frame_asr.supports_streaming:
        print("⚠ WARNING: Streaming not supported")
        return False

    print("✓ FrameASR initialized with streaming support")
    return True


def test_dummy_transcription():
    """Test transcription with dummy audio data"""
    print("\n" + "="*60)
    print("TEST 3: Dummy Audio Transcription")
    print("="*60)

    config = Config()
    config.enable_model = True

    model = load_nemo_model(config)
    if model is None:
        print("❌ FAIL: Could not load model")
        return False

    frame_asr = FrameASR(model, config)

    # Create dummy audio chunk (1.6 seconds of silence)
    chunk_size = int(config.sample_rate * 1.6)
    dummy_audio = np.zeros(chunk_size, dtype=np.float32)

    print(f"Created dummy audio: {len(dummy_audio)} samples ({len(dummy_audio)/config.sample_rate:.1f}s)")

    # Test VAD (should return False for silence)
    print("\nTesting VAD on silence...")
    has_speech = frame_asr.has_speech(dummy_audio, debug=True)
    print(f"  - VAD result: {has_speech} (expected: False)")

    if has_speech:
        print("⚠ WARNING: VAD detected speech in silence (check thresholds)")
    else:
        print("✓ VAD correctly detected silence")

    # Test transcription (should be fast even with no speech)
    print("\nTesting transcription on silence...")
    start_time = time.time()

    try:
        text = frame_asr.transcribe_chunk(dummy_audio)
        elapsed = (time.time() - start_time) * 1000

        print(f"  - Transcription time: {elapsed:.1f}ms")
        print(f"  - Result: '{text}' (expected: empty)")

        if elapsed > 500:
            print(f"⚠ WARNING: Transcription took {elapsed:.1f}ms (expected <200ms)")
        else:
            print(f"✓ Transcription completed in {elapsed:.1f}ms")

        # Check cache state after first chunk
        print("\nCache state after first chunk:")
        print(f"  - cache_last_channel is None: {frame_asr.cache_last_channel is None}")
        print(f"  - cache_last_time is None: {frame_asr.cache_last_time is None}")
        print(f"  - previous_hypotheses is None: {frame_asr.previous_hypotheses is None}")

        # Process second chunk to test cache reuse
        print("\nProcessing second chunk (should use cache)...")
        start_time = time.time()
        text2 = frame_asr.transcribe_chunk(dummy_audio)
        elapsed2 = (time.time() - start_time) * 1000

        print(f"  - Second transcription time: {elapsed2:.1f}ms")
        print(f"  - Cache is being used: {frame_asr.cache_last_channel is not None}")

        if frame_asr.cache_last_channel is None:
            print("⚠ WARNING: Cache is not being maintained between chunks!")
        else:
            print("✓ Cache is maintained between chunks")

        return True

    except Exception as e:
        print(f"❌ FAIL: Transcription failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cache_reset():
    """Test cache reset functionality"""
    print("\n" + "="*60)
    print("TEST 4: Cache Reset")
    print("="*60)

    config = Config()
    config.enable_model = True

    model = load_nemo_model(config)
    if model is None:
        print("❌ FAIL: Could not load model")
        return False

    frame_asr = FrameASR(model, config)

    # Process a chunk to create cache
    chunk_size = int(config.sample_rate * 1.6)
    dummy_audio = np.zeros(chunk_size, dtype=np.float32)

    print("Processing chunk to create cache...")
    frame_asr.transcribe_chunk(dummy_audio)

    has_cache = frame_asr.cache_last_channel is not None
    print(f"  - Cache exists: {has_cache}")

    # Reset cache
    print("\nResetting cache...")
    frame_asr.reset()

    cache_cleared = (
        frame_asr.cache_last_channel is None and
        frame_asr.cache_last_time is None and
        frame_asr.previous_hypotheses is None and
        frame_asr.previous_pred_out is None
    )

    print(f"  - All cache variables cleared: {cache_cleared}")

    if cache_cleared:
        print("✓ Cache reset successful")
        return True
    else:
        print("❌ FAIL: Cache not fully cleared")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print(" FastConformer Streaming Implementation Test Suite")
    print("="*70)

    # Set up logging
    logger = setup_logging(debug=True, name='test')

    # Run tests
    results = []

    try:
        results.append(("Model Loading", test_model_loading()))
        results.append(("FrameASR Init", test_frame_asr_initialization()))
        results.append(("Dummy Transcription", test_dummy_transcription()))
        results.append(("Cache Reset", test_cache_reset()))
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Print summary
    print("\n" + "="*70)
    print(" Test Summary")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        print(f"{status:8} - {name}")

    print("-"*70)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
