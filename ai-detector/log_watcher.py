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


class ConversationLogHandler(FileSystemEventHandler):
    """Handles changes to the conversation log file."""

    def __init__(self, log_path: str, detector: AIDetector, detection_log_path: str):
        self.log_path = Path(log_path)
        self.detector = detector
        self.detection_log_path = detection_log_path

        # Track the last read position
        self.last_position = 0

        # Initialize position (read existing file if it exists)
        if self.log_path.exists():
            self.last_position = self.log_path.stat().st_size

        print(f"Watching: {self.log_path}")
        print(f"Detection log: {self.detection_log_path}")

    def on_modified(self, event):
        """Called when the log file is modified."""

        if event.src_path != str(self.log_path):
            return

        self.process_new_lines()

    def process_new_lines(self):
        """Process new lines added to the log file."""

        if not self.log_path.exists():
            return

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
                message = data.get('message', '')
                user = data.get('user', 'Unknown')
                timestamp = data.get('timestamp', datetime.now().isoformat())

                # Skip if no message
                if not message:
                    continue

                # Run detection
                is_for_ai = self.detector.is_message_for_ai(message)

                # Log result
                self.log_detection(timestamp, user, message, is_for_ai)

                # Trigger function if detected
                if is_for_ai:
                    self.trigger_function(timestamp, user, message)

            except json.JSONDecodeError as e:
                print(f"Error parsing JSON line: {e}")
                continue
            except Exception as e:
                print(f"Error processing message: {e}")
                continue

    def log_detection(self, timestamp: str, user: str, message: str, detected: bool):
        """Log detection result to file."""

        status = "DETECTED" if detected else "IGNORED"
        log_entry = f"[{timestamp}] {status} | {user}: {message}\n"

        with open(self.detection_log_path, 'a') as f:
            f.write(log_entry)

        # Also print to console
        if detected:
            print(f"🔔 {status} | {user}: {message}")
        else:
            print(f"   {status} | {user}: {message}")

    def trigger_function(self, timestamp: str, user: str, message: str):
        """
        Called when AI is detected in a message.
        Override this method to add custom functionality.
        """

        print(f"\n{'='*60}")
        print(f"AI TRIGGER ACTIVATED!")
        print(f"Time: {timestamp}")
        print(f"User: {user}")
        print(f"Message: {message}")
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
    event_handler = ConversationLogHandler(log_path, detector, detection_log_path)
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
