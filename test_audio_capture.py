#!/usr/bin/env python3
"""
Quick test to see if audio is being captured and at what levels
"""
import sys
sys.path.insert(0, 'source-code')

from core import Config, AudioCapture
import time

config = Config()
audio = AudioCapture(config)

print("Capturing 5 audio chunks to check levels...")
print("(Netflix should be playing)")
print()

for i in range(5):
    chunk = audio.capture_chunk()
    if chunk is not None:
        max_amp, avg_amp = AudioCapture.calculate_energy(chunk)
        print(f"Chunk {i+1}: max={max_amp:6.0f}, avg={avg_amp:6.1f}  ", end="")

        if max_amp > 1000:
            print("✓ LOUD - Should be detected")
        elif max_amp > 100:
            print("~ Medium - Might be detected")
        else:
            print("✗ Too quiet - Won't be detected")
    else:
        print(f"Chunk {i+1}: ERROR capturing audio")

    time.sleep(0.1)

print()
print("If all chunks show 'Too quiet', then:")
print("1. Microphone is not picking up Netflix audio")
print("2. Check: Is Netflix playing through speakers?")
print("3. Try: Increase speaker volume or move mic closer")
print("4. Or: Configure a loopback device to capture system audio")
