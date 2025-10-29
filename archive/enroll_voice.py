#!/usr/bin/env python3
"""
Voice Enrollment Script
Records samples of your voice to create a speaker profile
"""
import sys
import time
import numpy as np
import sounddevice as sd
from pathlib import Path
from tqdm import tqdm

# Add source-code to path
sys.path.insert(0, str(Path(__file__).parent / "source-code"))

from core.speaker_recognition import SpeakerRecognition, SPEAKER_REC_AVAILABLE
from core import setup_logging


# Sample sentences for enrollment (cover different phonemes)
ENROLLMENT_SENTENCES = [
    "The quick brown fox jumps over the lazy dog.",
    "How much wood would a woodchuck chuck if a woodchuck could chuck wood?",
    "She sells seashells by the seashore.",
    "Peter Piper picked a peck of pickled peppers.",
    "Hello Jarvis, I need your help with something.",
    "Can you help me refactor this code please?",
    "What's the weather like today?",
    "Tell me about machine learning and artificial intelligence.",
    "I want to create a new Python script for data analysis.",
    "Please transcribe everything I'm saying right now.",
]


def record_audio(duration: float, sample_rate: int = 16000) -> np.ndarray:
    """
    Record audio from microphone

    Args:
        duration: Recording duration in seconds
        sample_rate: Sample rate

    Returns:
        Audio as float32 array
    """
    print(f"  Recording for {duration:.1f} seconds...")

    # Record
    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype='float32',
        blocking=True
    )

    audio = audio.flatten()
    print(f"  ✓ Recorded {len(audio)} samples")

    # Check if audio has content
    max_amplitude = np.abs(audio).max()
    if max_amplitude < 0.01:
        print("  ⚠️  Warning: Very low audio level detected!")
        print("     Make sure your microphone is working and not muted.")

    return audio


def main():
    """Main enrollment process"""
    print("=" * 60)
    print("Voice Enrollment for JARVIS")
    print("=" * 60)
    print()

    # Check if resemblyzer is available
    if not SPEAKER_REC_AVAILABLE:
        print("❌ Error: resemblyzer not installed")
        print()
        print("Please install the conversational requirements:")
        print("  pip install -r source-code/requirements-conversational.txt")
        print()
        return 1

    print("This script will record samples of your voice to create a profile.")
    print("The profile allows JARVIS to recognize YOUR voice specifically,")
    print("and ignore other voices (movies, music, other people).")
    print()

    # Get user info
    user_name = input("Enter your name (optional, press Enter to skip): ").strip()
    if not user_name:
        user_name = "user"

    print()
    print(f"Enrolling: {user_name}")
    print()

    # Setup
    profile_path = "source-code/data/user_voice_profile.pkl"
    sample_rate = 16000
    recording_duration = 3.0  # 3 seconds per sample

    print(f"Profile will be saved to: {profile_path}")
    print(f"Sample rate: {sample_rate} Hz")
    print(f"Recording duration per sample: {recording_duration} seconds")
    print()

    # Microphone test
    print("First, let's test your microphone...")
    input("Press Enter when ready to record a test...")
    print()

    test_audio = record_audio(2.0, sample_rate)
    test_level = np.abs(test_audio).max()

    print()
    print(f"Audio level: {test_level:.3f}")

    if test_level < 0.01:
        print("❌ Audio level too low!")
        print("   Please check:")
        print("   - Is your microphone plugged in?")
        print("   - Is it selected as default input device?")
        print("   - Is it muted?")
        print()
        return 1
    elif test_level < 0.1:
        print("⚠️  Audio level is low, but might be okay")
        print("   Speak louder during enrollment for best results")
    else:
        print("✓ Audio level good!")

    print()

    # Start enrollment
    print("-" * 60)
    print("Voice Enrollment")
    print("-" * 60)
    print()
    print(f"You will read {len(ENROLLMENT_SENTENCES)} sentences.")
    print("Speak naturally and clearly.")
    print()

    input("Press Enter to start enrollment...")
    print()

    audio_samples = []

    for i, sentence in enumerate(ENROLLMENT_SENTENCES, 1):
        print(f"[{i}/{len(ENROLLMENT_SENTENCES)}] Please read:")
        print()
        print(f"  \"{sentence}\"")
        print()

        input("  Press Enter when ready to record...")

        # Countdown
        for count in [3, 2, 1]:
            print(f"  {count}...")
            time.sleep(0.8)

        print("  🎤 RECORDING...")
        print()

        # Record
        audio = record_audio(recording_duration, sample_rate)
        audio_samples.append(audio)

        print()
        time.sleep(0.5)

    # Create speaker recognition system
    print("-" * 60)
    print("Creating voice profile...")
    print("-" * 60)
    print()

    sr = SpeakerRecognition(
        profile_path=profile_path,
        similarity_threshold=0.65,
        enabled=True
    )

    # Enroll
    print("Processing audio samples...")
    success = sr.enroll_user(
        audio_samples=audio_samples,
        sample_rate=sample_rate,
        name=user_name
    )

    print()

    if success:
        print("=" * 60)
        print("✅ Enrollment Successful!")
        print("=" * 60)
        print()
        print(f"Voice profile saved to: {profile_path}")
        print()
        print("JARVIS will now:")
        print("  ✓ Respond only to YOUR voice")
        print("  ✓ Ignore movies, music, and other voices")
        print("  ✓ Filter out background dialogue")
        print()
        print("You can re-run this script anytime to update your profile.")
        print()
        return 0
    else:
        print("=" * 60)
        print("❌ Enrollment Failed")
        print("=" * 60)
        print()
        print("Please check the error messages above and try again.")
        print()
        return 1


if __name__ == "__main__":
    setup_logging(debug=False, name='enrollment')
    sys.exit(main())
