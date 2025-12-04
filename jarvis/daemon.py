"""Main daemon - signal handling and lifecycle."""

import os
import signal
import sys
from pathlib import Path

from jarvis.audio import AudioRecorder
from jarvis.stt import SpeechToText
from jarvis.output import paste_text

PID_FILE = Path("/tmp/jarvis.pid")


class Daemon:
    def __init__(self):
        self.recorder = AudioRecorder()
        self.stt = SpeechToText()
        self.recording = False

    def start_recording(self, signum=None, frame=None):
        if self.recording:
            return
        self.recording = True
        self.recorder.start()

    def stop_recording(self, signum=None, frame=None):
        if not self.recording:
            return
        self.recording = False
        audio = self.recorder.stop()
        if audio is not None and len(audio) > 0:
            text = self.stt.transcribe(audio)
            if text:
                paste_text(text)

    def shutdown(self, signum=None, frame=None):
        PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    def run(self):
        # Write PID file
        PID_FILE.write_text(str(os.getpid()))

        # Register signal handlers
        signal.signal(signal.SIGUSR1, self.start_recording)
        signal.signal(signal.SIGUSR2, self.stop_recording)
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

        print(f"Jarvis daemon running (PID: {os.getpid()})")
        print("Waiting for signals...")

        # Wait forever
        while True:
            signal.pause()


def main():
    daemon = Daemon()
    daemon.run()


if __name__ == "__main__":
    main()
