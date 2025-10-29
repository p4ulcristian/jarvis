#!/usr/bin/env python3
"""Test that all imports work correctly"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'source-code'))

print("Testing imports...")

try:
    from core.config import Config
    print("✓ Config imported")
except Exception as e:
    print(f"✗ Config import failed: {e}")
    exit(1)

try:
    from nemo.collections.asr.models import EncDecMultiTaskModel
    print("✓ EncDecMultiTaskModel imported")
except Exception as e:
    print(f"✗ EncDecMultiTaskModel import failed: {e}")
    exit(1)

try:
    from core.transcription import load_nemo_model, FrameASR
    print("✓ transcription module imported")
except Exception as e:
    print(f"✗ transcription import failed: {e}")
    exit(1)

print("\n✓ All imports successful!")
print("\nReady to load Canary-1B Flash model")
print("Note: First run will download ~1.7GB model from HuggingFace")
