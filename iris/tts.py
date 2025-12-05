"""FastPitch + HiFi-GAN TTS wrapper."""

import os
import sys
import logging

# Suppress NeMo logging spam
os.environ['NEMO_LOG_LEVEL'] = 'ERROR'
os.environ['HYDRA_FULL_ERROR'] = '0'
logging.disable(logging.WARNING)

import warnings
warnings.filterwarnings('ignore')

# Suppress stdout/stderr during import
_stdout, _stderr = sys.stdout, sys.stderr
sys.stdout = sys.stderr = open(os.devnull, 'w')

import torch
import soundfile as sf
from nemo.collections.tts.models import FastPitchModel, HifiGanModel

sys.stdout, sys.stderr = _stdout, _stderr
logging.disable(logging.NOTSET)

FASTPITCH_MODEL = "nvidia/tts_en_fastpitch"
HIFIGAN_MODEL = "nvidia/tts_hifigan"
SAMPLE_RATE = 22050


def _quiet():
    """Context manager to suppress stdout/stderr."""
    class Quiet:
        def __enter__(self):
            self._stdout, self._stderr = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = open(os.devnull, 'w')
            return self
        def __exit__(self, *args):
            sys.stdout, sys.stderr = self._stdout, self._stderr
    return Quiet()


class TextToSpeech:
    _instance = None

    def __init__(self):
        print("Loading TTS models...", file=sys.stderr, flush=True)
        with _quiet():
            # Load FastPitch (spectrogram generator)
            self.spec_gen = FastPitchModel.from_pretrained(FASTPITCH_MODEL)
            self.spec_gen = self.spec_gen.half().cuda()
            self.spec_gen.eval()

            # Load HiFi-GAN (vocoder)
            self.vocoder = HifiGanModel.from_pretrained(HIFIGAN_MODEL)
            self.vocoder = self.vocoder.half().cuda()
            self.vocoder.eval()
        print("TTS ready", file=sys.stderr, flush=True)

    @classmethod
    def get_instance(cls):
        """Get singleton instance for reuse."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def synthesize(self, text: str, output_path: str = None) -> bytes:
        """Convert text to speech audio.

        Args:
            text: Text to speak
            output_path: Optional path to save WAV file

        Returns:
            Audio bytes if no output_path, else None
        """
        with torch.no_grad():
            # Parse text to tokens
            parsed = self.spec_gen.parse(text)

            # Generate mel spectrogram
            spectrogram = self.spec_gen.generate_spectrogram(tokens=parsed)

            # Convert to audio waveform
            audio = self.vocoder.convert_spectrogram_to_audio(spec=spectrogram)

        # Get numpy array
        audio_np = audio.cpu().float().numpy()[0]

        if output_path:
            sf.write(output_path, audio_np, SAMPLE_RATE)
            return None
        else:
            import io
            buffer = io.BytesIO()
            sf.write(buffer, audio_np, SAMPLE_RATE, format='WAV')
            return buffer.getvalue()


def speak(text: str, output_path: str = "/tmp/tts_output.wav"):
    """Simple function to speak text."""
    tts = TextToSpeech.get_instance()
    tts.synthesize(text, output_path)
    return output_path


if __name__ == "__main__":
    import subprocess

    if len(sys.argv) < 2:
        print("Usage: python -m iris.tts 'text to speak'")
        sys.exit(1)

    text = " ".join(sys.argv[1:])
    output = speak(text)

    # Play with mpv
    subprocess.run(["mpv", "--no-video", "--really-quiet", output], check=True)
