"""PipeWire/PulseAudio audio recording."""

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000  # Parakeet expects 16kHz


class AudioRecorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.buffer: list[np.ndarray] = []
        self.stream = None

    def _callback(self, indata, frames, time, status):
        self.buffer.append(indata.copy())

    def start(self):
        self.buffer = []
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            callback=self._callback,
        )
        self.stream.start()

    def stop(self) -> np.ndarray | None:
        if self.stream is None:
            return None
        self.stream.stop()
        self.stream.close()
        self.stream = None
        if not self.buffer:
            return None
        return np.concatenate(self.buffer, axis=0).flatten()
