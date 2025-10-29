#!/usr/bin/env python3
"""
Test script for Canary-1B Flash model
Validates model loading, inference speed, and transcription quality
"""
import sys
import time
import wave
import tempfile
import os
from pathlib import Path

# Add source-code to path
sys.path.insert(0, str(Path(__file__).parent / 'source-code'))

import numpy as np
import torch
from core.config import Config
from core.transcription import load_nemo_model, FrameASR

def generate_test_audio(duration: float = 2.0, sample_rate: int = 16000) -> np.ndarray:
    """
    Generate test audio (sine wave)

    Args:
        duration: Duration in seconds
        sample_rate: Sample rate

    Returns:
        Audio data as float32 array
    """
    samples = int(duration * sample_rate)
    t = np.linspace(0, duration, samples, dtype=np.float32)

    # Mix of frequencies to simulate speech
    audio = (
        0.3 * np.sin(2 * np.pi * 440 * t) +  # A4
        0.2 * np.sin(2 * np.pi * 554 * t) +  # C#5
        0.1 * np.sin(2 * np.pi * 659 * t)    # E5
    )

    # Add some amplitude variation
    envelope = np.exp(-t / duration)
    audio *= envelope

    return audio.astype(np.float32)

def save_wav(audio: np.ndarray, filepath: str, sample_rate: int = 16000):
    """Save audio to WAV file"""
    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)

        # Convert float32 to int16
        audio_int16 = np.empty(audio.shape, dtype=np.int16)
        np.multiply(audio, 32768, out=audio_int16, casting='unsafe')
        wf.writeframes(audio_int16.tobytes())

def test_model_loading():
    """Test 1: Model loading"""
    print("=" * 60)
    print("TEST 1: Model Loading")
    print("=" * 60)

    config = Config()

    print(f"Loading model: {config.model_name}")
    print(f"Language: {config.canary_source_lang} → {config.canary_target_lang}")
    print(f"Task: {config.canary_task}")
    print(f"Beam size: {config.canary_beam_size}")

    start = time.time()
    model = load_nemo_model(config)
    elapsed = time.time() - start

    if model is None:
        print("❌ FAILED: Model loading failed")
        return None, None

    print(f"✓ Model loaded in {elapsed:.2f}s")

    # Check GPU
    if torch.cuda.is_available():
        print(f"✓ GPU: {torch.cuda.get_device_name(0)}")
        print(f"✓ VRAM allocated: {torch.cuda.memory_allocated(0) / 1024**3:.2f}GB")
    else:
        print("⚠ Running on CPU")

    return model, config

def test_inference_speed(model, config):
    """Test 2: Inference speed benchmark"""
    print("\n" + "=" * 60)
    print("TEST 2: Inference Speed Benchmark")
    print("=" * 60)

    # Generate test audio
    durations = [1.0, 2.0, 5.0]

    for duration in durations:
        audio = generate_test_audio(duration, config.sample_rate)

        # Create temp WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        save_wav(audio, temp_path, config.sample_rate)

        # Benchmark transcription
        start = time.time()
        result = model.transcribe([temp_path], verbose=False)
        elapsed = time.time() - start

        # Calculate RTFx (Real-Time Factor)
        rtfx = duration / elapsed if elapsed > 0 else 0

        print(f"\nAudio duration: {duration}s")
        print(f"Transcription time: {elapsed*1000:.1f}ms")
        print(f"RTFx: {rtfx:.1f}x real-time")

        if rtfx > 100:
            print("✓ EXCELLENT: >100x real-time")
        elif rtfx > 50:
            print("✓ GOOD: >50x real-time")
        elif rtfx > 10:
            print("⚠ OK: >10x real-time")
        else:
            print("❌ SLOW: <10x real-time")

        # Clean up
        os.unlink(temp_path)

def test_transcription_quality(model, config):
    """Test 3: Basic transcription test"""
    print("\n" + "=" * 60)
    print("TEST 3: Transcription Quality")
    print("=" * 60)

    asr = FrameASR(model, config)

    # Generate silent audio
    print("\nTest 3a: Silence detection")
    silence = np.zeros(16000, dtype=np.float32)  # 1 second of silence
    has_speech = asr.has_speech(silence, debug=True)

    if not has_speech:
        print("✓ Correctly detected silence")
    else:
        print("❌ False positive: detected speech in silence")

    # Generate audio with amplitude
    print("\nTest 3b: Speech detection")
    speech = generate_test_audio(1.0, config.sample_rate)
    has_speech = asr.has_speech(speech, debug=True)

    if has_speech:
        print("✓ Correctly detected speech-like audio")
    else:
        print("⚠ Did not detect speech in test audio")

    print("\nNote: For real transcription quality testing, use actual speech audio")

def test_vram_usage():
    """Test 4: VRAM usage"""
    print("\n" + "=" * 60)
    print("TEST 4: VRAM Usage")
    print("=" * 60)

    if not torch.cuda.is_available():
        print("⚠ GPU not available, skipping VRAM test")
        return

    allocated = torch.cuda.memory_allocated(0) / 1024**3
    reserved = torch.cuda.memory_reserved(0) / 1024**3
    total = torch.cuda.get_device_properties(0).total_memory / 1024**3

    print(f"VRAM allocated: {allocated:.2f}GB")
    print(f"VRAM reserved: {reserved:.2f}GB")
    print(f"Total VRAM: {total:.2f}GB")
    print(f"Usage: {allocated/total*100:.1f}%")

    if allocated < 3.0:
        print("✓ VRAM usage is reasonable (<3GB)")
    else:
        print("⚠ VRAM usage is high (>3GB)")

def main():
    """Run all tests"""
    print("\n" + "🔥" * 30)
    print("Canary-1B Flash Model Validation Suite")
    print("🔥" * 30 + "\n")

    try:
        # Test 1: Load model
        model, config = test_model_loading()
        if model is None:
            print("\n❌ Model loading failed, stopping tests")
            return 1

        # Test 2: Speed benchmark
        test_inference_speed(model, config)

        # Test 3: Transcription quality
        test_transcription_quality(model, config)

        # Test 4: VRAM usage
        test_vram_usage()

        print("\n" + "=" * 60)
        print("✓ All tests completed!")
        print("=" * 60)

        print("\n💡 Next steps:")
        print("1. Test with real voice audio for transcription quality")
        print("2. Run the main Jarvis app: ./jarvis.sh")
        print("3. Benchmark end-to-end latency with voice input")

        return 0

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    exit(main())
