"""Main daemon - PTT via keyd signals."""

import os
import signal
import sys
from pathlib import Path

from iris.audio import AudioRecorder
from iris.stt import SpeechToText
from iris.output import paste_text

PID_FILE = Path("/tmp/iris.pid")


class Daemon:
    def __init__(self):
        self.recorder = AudioRecorder()
        self.stt = SpeechToText()
        self.recording = False

    def start_recording(self, signum=None, frame=None):
        if self.recording:
            return
        self.recording = True
        print("Recording...", flush=True)
        self.recorder.start()

    def stop_recording(self, signum=None, frame=None):
        if not self.recording:
            return
        self.recording = False
        print("Processing...", flush=True)
        audio = self.recorder.stop()
        if audio is not None and len(audio) > 0:
            text = self.stt.transcribe(audio)
            if text:
                print(f"Transcribed: {text}")
                paste_text(text)
            else:
                print("No speech detected")
        else:
            print("No audio captured")

    def shutdown(self, signum=None, frame=None):
        PID_FILE.unlink(missing_ok=True)
        sys.exit(0)

    def run(self):
        # Signal handlers for keyd integration
        signal.signal(signal.SIGUSR1, self.start_recording)  # CapsLock press
        signal.signal(signal.SIGUSR2, self.stop_recording)   # CapsLock release
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

        print(f"Iris ready (PID: {os.getpid()})", flush=True)
        print("Hold CapsLock to record...", flush=True)

        # Keep main thread alive, waiting for signals
        while True:
            signal.pause()


def main():
    # Write PID immediately so keyd can signal us while model loads
    PID_FILE.write_text(str(os.getpid()))

    try:
        daemon = Daemon()
        daemon.run()
    finally:
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
