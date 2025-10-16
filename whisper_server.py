#!/usr/bin/env python3
"""
Persistent Whisper server that loads the model once and processes transcription requests.
Reads audio file paths from stdin and writes transcription results to stdout as JSON.
"""

import sys
import json
import whisper
import os
import traceback

def main():
    try:
        # Load model once at startup (using regular whisper with GPU)
        print("Loading Whisper model (medium) on GPU...", file=sys.stderr)
        sys.stderr.flush()

        # Regular whisper automatically uses CUDA if available
        model = whisper.load_model("medium")

        print("Whisper model loaded on GPU. Ready for requests.", file=sys.stderr)
        sys.stderr.flush()
    except Exception as e:
        print(f"ERROR loading model: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)

    # Process requests line by line
    for line in sys.stdin:
        audio_file = line.strip()

        if not audio_file:
            continue

        if not os.path.exists(audio_file):
            result = {
                "success": False,
                "error": f"Audio file not found: {audio_file}"
            }
            print(json.dumps(result))
            sys.stdout.flush()
            continue

        try:
            # Transcribe audio (English only for faster performance)
            print("[Whisper] Starting transcription...", file=sys.stderr)
            sys.stderr.flush()

            result_data = model.transcribe(audio_file, language="en")
            text = result_data.get("text", "").strip()

            print("[Whisper] Transcription complete!", file=sys.stderr)
            sys.stderr.flush()

            # Log the transcribed text to console
            print(f"[Whisper] TRANSCRIBED: {text}", file=sys.stderr)
            sys.stderr.flush()

            result = {
                "success": True,
                "text": text,
                "file": audio_file
            }
            print(json.dumps(result))
            sys.stdout.flush()

            # Clean up temp file
            try:
                os.remove(audio_file)
            except:
                pass

        except Exception as e:
            print(f"[Whisper] ERROR during transcription: {e}", file=sys.stderr)
            print(f"[Whisper] Traceback: {traceback.format_exc()}", file=sys.stderr)
            sys.stderr.flush()

            result = {
                "success": False,
                "error": str(e),
                "file": audio_file
            }
            print(json.dumps(result))
            sys.stdout.flush()

if __name__ == "__main__":
    main()
