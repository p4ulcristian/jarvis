"""Main daemon - PTT with evdev hotkey."""

import os
import signal
import sys
from pathlib import Path
from evdev import ecodes

from jarvis.audio import AudioRecorder
from jarvis.stt import SpeechToText
from jarvis.output import paste_text
from jarvis.hotkey import start_hotkey_thread

PID_FILE = Path("/tmp/jarvis.pid")
HOTKEY = ecodes.KEY_CAPSLOCK


class Daemon:
    def __init__(self):
        self.recorder = AudioRecorder()
        self.stt = SpeechToText()
        self.recording = False

    def start_recording(self):
        if self.recording:
            return
        self.recording = True
        print("Recording...", flush=True)
        self.recorder.start()

    def stop_recording(self):
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
        PID_FILE.write_text(str(os.getpid()))

        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

        print(f"Jarvis daemon running (PID: {os.getpid()})", flush=True)
        print("Hold CapsLock to record...", flush=True)

        # Start hotkey listener
        start_hotkey_thread(
            HOTKEY,
            on_press=self.start_recording,
            on_release=self.stop_recording
        )

        # Keep main thread alive
        signal.pause()


def main():
    daemon = Daemon()
    daemon.run()


if __name__ == "__main__":
    main()
