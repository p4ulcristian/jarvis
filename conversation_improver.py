#!/usr/bin/env python3
"""
Conversation Improver - Processes raw transcriptions using Ollama LLM

Watches conversation.json for new entries, batches them, sends to Ollama
for cleanup/improvement, and outputs to conversation_improved.json
"""

import json
import time
from pathlib import Path
from datetime import datetime
from collections import deque
import requests


# Configuration
INPUT_LOG = "chat.txt"
OUTPUT_LOG = "chat-revised.txt"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b-instruct"  # Qwen2.5 3B for better instruction following
BATCH_DURATION = 10  # Process every 10 seconds

# System prompt for Ollama
SYSTEM_PROMPT = """You are a transcription cleanup assistant. Clean up raw speech-to-text output from audio recordings (often interviews, conversations, or ambient audio).

STRICT RULES - YOU MUST FOLLOW THESE:
1. Output ONLY the cleaned transcription - NO meta-commentary, NO explanations
2. DO NOT write "Here is the improved text", "I'm ready to help", "What's the raw transcription?", or ANY similar phrases
3. DO NOT ask questions back to the system
4. DO NOT add content that isn't in the original - only fix transcription errors
5. If text is completely incomprehensible gibberish, output nothing (empty string)
6. Remove filler words (um, uh, mmhmm, mhm, yeah, oh, etc.) unless contextually important
7. Fix obvious mishearings (e.g., "one nine sixty eight" might be a year like "1968" or might be gibberish to ignore)
8. Add proper punctuation, capitalization, and sentence structure
9. Preserve interview format if present (questions and answers)
10. Make it sound like natural human speech

EXAMPLES:

Input: "mmhmm yeah the lady across the street on the phone hit me with the phone uh her children were"
Output: "The lady across the street hit me with the phone. Her children were"

Input: "mhm mhm oh gosh where is that mmhmm"
Output: "Where is that?"

Input: "good morning i'm good with the sheriff's office i think we're investigating this"
Output: "Good morning, I'm with the Sheriff's Office. We're investigating this."

Now clean this transcription (output ONLY the cleaned text):"""


# Meta-commentary patterns to filter out
META_PATTERNS = [
    r"^I'm ready to help\.?\s*",
    r"^I'm ready to improve the text\.?\s*",
    r"^What's the raw transcription\??\s*",
    r"^Here is the improved text:?\s*",
    r"^Here's the improved text:?\s*",
    r"^Let's try to improve the text\.?\s*",
    r"^I'd be happy to help\.?\s*",
    r"^I'm happy to help\.?\s*",
    r"^Please provide the raw transcription\.?\s*",
    r"^I don't have anything to output\.?\s*",
    r"^Transcription:\s*",
    r"^Cleaned Transcription:\s*",
    r"^Raw transcription:\s*",
    r"^Improved text:\s*",
    r"^Output:\s*",
    r"It seems like there was some confusion.*?corrected text\.?\s*",
    r"I'm sorry I can't provide information or guidance on illegal or harmful activities\..*?",
    r"Can I help you with something else\??\s*",
    r"I apologize.*?raw transcription provided.*?\.",
]


def filter_meta_commentary(text):
    """Remove meta-commentary from LLM output using regex patterns"""
    import re

    if not text:
        return text

    # Apply each pattern
    for pattern in META_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

    # Remove empty lines at the start
    text = text.lstrip()

    # Remove multiple consecutive spaces
    text = re.sub(r' {2,}', ' ', text)

    return text


class TranscriptionBuffer:
    """Buffer for accumulating transcription text"""

    def __init__(self):
        self.text = ""
        self.last_processed_time = time.time()

    def add(self, text):
        """Add new text to the buffer"""
        self.text += text

    def should_process(self):
        """Check if we should process the buffer"""
        elapsed = time.time() - self.last_processed_time
        return elapsed >= BATCH_DURATION and len(self.text) > 0

    def get_batch(self):
        """Get all text and clear the buffer"""
        batch = self.text
        self.text = ""
        self.last_processed_time = time.time()
        return batch

    def is_empty(self):
        return len(self.text) == 0


class ConversationImprover:
    """Main processor for improving transcriptions"""

    def __init__(self):
        self.input_path = Path(INPUT_LOG)
        self.output_path = Path(OUTPUT_LOG)
        self.buffer = TranscriptionBuffer()
        self.last_position = 0

        # Create output file if it doesn't exist
        if not self.output_path.exists():
            self.output_path.touch()

        # Track last read position
        # If output file is empty, start from beginning to process existing entries
        if self.output_path.stat().st_size == 0:
            self.last_position = 0
        elif self.input_path.exists():
            self.last_position = self.input_path.stat().st_size
        else:
            self.last_position = 0

        print(f"[INIT] Watching: {self.input_path}")
        print(f"[INIT] Output: {self.output_path}")
        print(f"[INIT] Model: {OLLAMA_MODEL}")
        print(f"[INIT] Processing every {BATCH_DURATION}s")

    def check_ollama(self):
        """Check if Ollama is running and model is available"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]

                if not any(OLLAMA_MODEL in name for name in model_names):
                    print(f"[WARNING] Model '{OLLAMA_MODEL}' not found in Ollama")
                    print(f"[INFO] Available models: {', '.join(model_names)}")
                    print(f"[INFO] Run: ollama pull {OLLAMA_MODEL}")
                    return False

                print(f"[OK] Ollama is running with {OLLAMA_MODEL}")
                return True
            else:
                print("[ERROR] Ollama API returned unexpected status")
                return False
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Cannot connect to Ollama: {e}")
            print("[INFO] Make sure Ollama is running: ollama serve")
            return False

    def read_new_text(self):
        """Read new text from the input log"""
        if not self.input_path.exists():
            return ""

        try:
            with open(self.input_path, 'r') as f:
                f.seek(self.last_position)
                new_content = f.read()
                self.last_position = f.tell()

            return new_content.strip()

        except Exception as e:
            print(f"[ERROR] Failed to read input: {e}")
            return ""

    def improve_text(self, raw_text):
        """Send text to Ollama for improvement"""
        if not raw_text:
            return None

        # Create prompt
        prompt = f"{SYSTEM_PROMPT}\n\nRaw transcription:\n{raw_text}\n\nImproved text:"

        try:
            # Call Ollama API
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Lower temperature for more consistent output
                    "top_p": 0.9
                }
            }

            print(f"[PROCESSING] {len(raw_text)} chars...")
            start_time = time.time()

            response = requests.post(OLLAMA_URL, json=payload, timeout=60)

            if response.status_code == 200:
                result = response.json()
                improved_text = result.get('response', '').strip()

                # Apply meta-commentary filter
                improved_text = filter_meta_commentary(improved_text)

                elapsed = time.time() - start_time

                print(f"[OK] Processed in {elapsed:.1f}s")
                return improved_text
            else:
                print(f"[ERROR] Ollama API error: {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            print("[ERROR] Ollama request timed out")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to process with Ollama: {e}")
            return None

    def write_output(self, improved_text):
        """Write improved text to output log"""
        if not improved_text:
            return

        try:
            with open(self.output_path, 'a') as f:
                f.write(improved_text + ' ')

            print(f"[SAVED] Output written")
            print(f"[PREVIEW] {improved_text[:100]}...")

        except Exception as e:
            print(f"[ERROR] Failed to write output: {e}")

    def process_buffer(self):
        """Process accumulated buffer"""
        batch = self.buffer.get_batch()

        if not batch:
            return

        # Improve text with Ollama
        improved = self.improve_text(batch)

        if improved:
            self.write_output(improved)

    def run(self):
        """Main loop"""
        print("\n" + "="*60)
        print("Conversation Improver Starting")
        print("="*60 + "\n")

        # Check Ollama availability
        if not self.check_ollama():
            print("\n[ERROR] Cannot proceed without Ollama")
            return False

        print("\n[LISTENING] Monitoring for new transcriptions...")
        print("[INFO] Press Ctrl+C to stop\n")

        try:
            while True:
                # Read new text
                new_text = self.read_new_text()

                # Add to buffer
                if new_text:
                    self.buffer.add(new_text)

                # Check if we should process
                if self.buffer.should_process():
                    self.process_buffer()

                # Sleep briefly
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\n[SHUTDOWN] Stopping...")

            # Process remaining buffer
            if not self.buffer.is_empty():
                print("[INFO] Processing remaining text...")
                self.process_buffer()

        print("[OK] Goodbye!")
        return True


def main():
    improver = ConversationImprover()
    success = improver.run()
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
