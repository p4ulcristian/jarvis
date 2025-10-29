#!/usr/bin/env python3
"""
Log Watcher - Monitors conversation logs and triggers AI detection.
"""

import json
import time
import yaml
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from ai_detector import AIDetector
from difflib import SequenceMatcher


class ConversationLogHandler(FileSystemEventHandler):
    """Handles changes to the conversation log file."""

    def __init__(self, log_path: str, detector: AIDetector, detection_log_path: str, improved_log_path: str = None):
        self.log_path = Path(log_path)
        self.detector = detector
        self.detection_log_path = detection_log_path
        self.improved_log_path = Path(improved_log_path) if improved_log_path else None

        # Track the last read position
        self.last_position = 0

        # Cache for improved text entries
        self.improved_cache = []
        self.improved_last_position = 0

        # Initialize position (read existing file if it exists)
        if self.log_path.exists():
            self.last_position = self.log_path.stat().st_size

        print(f"Watching: {self.log_path}")
        print(f"Detection log: {self.detection_log_path}")
        if self.improved_log_path:
            print(f"Improved text log: {self.improved_log_path}")
            # Load existing improved entries on startup
            if self.improved_log_path.exists():
                self.load_improved_entries()

    def on_modified(self, event):
        """Called when the log file is modified."""

        if event.src_path != str(self.log_path):
            return

        self.process_new_lines()

    def load_improved_entries(self):
        """Load new improved text entries from conversation_improved.json"""
        if not self.improved_log_path or not self.improved_log_path.exists():
            return

        try:
            with open(self.improved_log_path, 'r') as f:
                f.seek(self.improved_last_position)
                new_content = f.read()
                self.improved_last_position = f.tell()

            if not new_content.strip():
                return

            # Parse new improved entries
            for line in new_content.strip().split('\n'):
                if line.strip():
                    try:
                        entry = json.loads(line)
                        self.improved_cache.append(entry)
                    except json.JSONDecodeError:
                        pass

            # Keep only recent entries (last 100)
            if len(self.improved_cache) > 100:
                self.improved_cache = self.improved_cache[-100:]

        except Exception as e:
            pass  # Silent fail

    def find_improved_text(self, raw_text: str, timestamp: str = None) -> dict:
        """Find the best matching improved text for a raw message

        Returns dict with:
            - improved_text: The improved version
            - original_batch: The full original batch text (for context)
        """
        if not self.improved_cache:
            return None

        # First try: match by timestamp if provided
        if timestamp:
            for entry in self.improved_cache:
                timestamp_start = entry.get('timestamp_start', '')
                timestamp_end = entry.get('timestamp_end', '')

                # Check if message timestamp falls within improved batch range
                if timestamp_start <= timestamp <= timestamp_end:
                    return {
                        'improved_text': entry.get('improved_text'),
                        'original_batch': entry.get('original_text')
                    }

        # Second try: check if raw text is contained in original_text
        best_match = None
        best_score = 0.0

        for entry in self.improved_cache:
            original = entry.get('original_text', '')

            # Check if raw text is a substring (after normalizing)
            if raw_text.lower().strip() in original.lower():
                return {
                    'improved_text': entry.get('improved_text'),
                    'original_batch': original
                }

            # Calculate similarity as fallback
            similarity = SequenceMatcher(None, raw_text.lower(), original.lower()).ratio()

            if similarity > best_score:
                best_score = similarity
                best_match = entry

        # Return improved text if similarity is reasonable (>30% since messages are fragments)
        if best_score > 0.3 and best_match:
            return {
                'improved_text': best_match.get('improved_text'),
                'original_batch': best_match.get('original_text')
            }

        return None

    def process_new_lines(self):
        """Process new lines added to the log file."""

        if not self.log_path.exists():
            return

        # Load any new improved entries first
        self.load_improved_entries()

        # Read new content from last position
        with open(self.log_path, 'r') as f:
            f.seek(self.last_position)
            new_content = f.read()
            self.last_position = f.tell()

        if not new_content.strip():
            return

        # Process each new line
        for line in new_content.strip().split('\n'):
            if not line.strip():
                continue

            try:
                # Parse JSON line
                data = json.loads(line)
                text = data.get('text', '')
                timestamp = data.get('timestamp', datetime.now().isoformat())

                # Skip if no text
                if not text:
                    continue

                # Run detection
                is_for_ai = self.detector.is_message_for_ai(text, use_sentences=False)

                # Find improved text
                improved_data = self.find_improved_text(text, timestamp)

                # Log result
                self.log_detection(timestamp, text, is_for_ai, improved_data)

                # Trigger function if detected
                if is_for_ai:
                    improved_text = improved_data.get('improved_text') if improved_data else None
                    self.trigger_function(timestamp, text, improved_text)

            except json.JSONDecodeError as e:
                print(f"Error parsing JSON line: {e}")
                continue
            except Exception as e:
                print(f"Error processing message: {e}")
                continue

    def log_detection(self, timestamp: str, message: str, detected: bool, improved_data: dict = None):
        """Log detection result to file."""

        status = "DETECTED" if detected else "IGNORED"

        # Extract improved text and batch from data
        improved_text = improved_data.get('improved_text') if improved_data else None
        original_batch = improved_data.get('original_batch') if improved_data else None

        # Create log entry with improved text if available
        log_entry = f"[{timestamp}] {status} | RAW: {message}"
        if improved_text:
            log_entry += f" | IMPROVED: {improved_text}"
        log_entry += "\n"

        with open(self.detection_log_path, 'a') as f:
            f.write(log_entry)

        # Print to console with flush
        import sys
        if detected:
            print("Ai: me", flush=True)
        else:
            print("Ai: not me", flush=True)

        # Always show raw text
        print(f"  Raw: {message}", flush=True)

        # Show batch context if available
        if original_batch:
            # Truncate if too long (show first 150 chars)
            batch_display = original_batch if len(original_batch) <= 150 else original_batch[:150] + "..."
            print(f"  Batch: {batch_display}", flush=True)

        # Show improved text
        if improved_text:
            print(f"  Improved: {improved_text}", flush=True)
        else:
            print(f"  Improved: (not available yet)", flush=True)

    def trigger_function(self, timestamp: str, message: str, improved_text: str = None):
        """
        Called when AI is detected in a message.
        Override this method to add custom functionality.
        """

        print(f"\n{'='*60}")
        print(f"AI TRIGGER ACTIVATED!")
        print(f"Time: {timestamp}")
        print(f"Raw message: {message}")
        if improved_text:
            print(f"Improved text: {improved_text}")
        print(f"{'='*60}\n")

        # TODO: Add your custom function call here
        # Examples:
        # - Send notification
        # - Call API endpoint
        # - Execute script
        # - etc.


def main():
    """Main daemon loop."""

    # Load configuration
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    log_path = config['log_file']
    detection_log_path = config['output']['detection_log']

    # Derive improved log path (same directory as conversation log)
    improved_log_path = str(Path(log_path).parent / "conversation_improved.json")

    # Create log directory if needed
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    Path(detection_log_path).parent.mkdir(parents=True, exist_ok=True)

    # Create empty log file if it doesn't exist
    if not Path(log_path).exists():
        Path(log_path).touch()
        print(f"Created new log file: {log_path}")

    print("\n" + "="*60)
    print("AI Detection System Starting")
    print("="*60)

    # Initialize detector
    print("Initializing AI detector...")
    detector = AIDetector()

    # Set up file watcher
    event_handler = ConversationLogHandler(log_path, detector, detection_log_path, improved_log_path)
    observer = Observer()
    observer.schedule(event_handler, path=str(Path(log_path).parent), recursive=False)

    print("\n" + "="*60)
    print("System Ready - Monitoring for messages")
    print("="*60)
    print("Press Ctrl+C to stop\n")

    # Start watching
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        observer.stop()

    observer.join()
    detector.close()
    print("Stopped.")


if __name__ == "__main__":
    main()
