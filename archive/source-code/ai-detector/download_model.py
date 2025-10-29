#!/usr/bin/env python3
"""
Download Llama 3.2 1B quantized model for AI detection.
"""

import os
import urllib.request
import sys
from pathlib import Path


def download_with_progress(url: str, output_path: str):
    """Download file with progress bar."""

    def reporthook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(downloaded * 100.0 / total_size, 100)
            sys.stdout.write(f"\rDownloading: {percent:.1f}% ({downloaded / 1024 / 1024:.1f}MB / {total_size / 1024 / 1024:.1f}MB)")
            sys.stdout.flush()

    print(f"Downloading model to {output_path}...")
    urllib.request.urlretrieve(url, output_path, reporthook)
    print("\n✓ Download complete!")


def main():
    # Create models directory
    models_dir = Path(__file__).parent / "models"
    models_dir.mkdir(exist_ok=True)

    # Model URL (Llama 3.2 1B Q4_K_M quantized)
    # Using TheBloke's quantized versions from HuggingFace
    model_filename = "llama-3.2-1b-q4_k_m.gguf"
    model_path = models_dir / model_filename

    if model_path.exists():
        print(f"Model already exists at {model_path}")
        print("Delete it if you want to re-download.")
        return

    # HuggingFace URL for Llama 3.2 1B Instruct GGUF
    # Note: This is a placeholder URL structure. In practice, you'd use the actual model from:
    # https://huggingface.co/TheBloke or similar quantized model repositories

    print("=" * 60)
    print("MANUAL DOWNLOAD REQUIRED")
    print("=" * 60)
    print()
    print("Please download the Llama 3.2 1B quantized model manually:")
    print()
    print("1. Visit: https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF")
    print()
    print("2. Download the file: 'Llama-3.2-1B-Instruct-Q4_K_M.gguf'")
    print()
    print(f"3. Save it to: {model_path}")
    print()
    print("Alternative smaller model:")
    print("   https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF")
    print("   Download: tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
