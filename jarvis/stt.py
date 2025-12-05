"""Canary STT model wrapper."""

import os
import sys
import tempfile
import logging

# Must set before any nemo imports
os.environ['NEMO_LOG_LEVEL'] = 'ERROR'
os.environ['HYDRA_FULL_ERROR'] = '0'
logging.disable(logging.WARNING)

import warnings
warnings.filterwarnings('ignore')

# Suppress stdout/stderr spam during import
_stdout, _stderr = sys.stdout, sys.stderr
sys.stdout = sys.stderr = open(os.devnull, 'w')

import torch
import numpy as np
import soundfile as sf
from nemo.collections.asr.models import EncDecMultiTaskModel

sys.stdout, sys.stderr = _stdout, _stderr
logging.disable(logging.NOTSET)

MODEL_NAME = "nvidia/canary-1b-v2"
SAMPLE_RATE = 16000


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


class SpeechToText:
    def __init__(self, model_name: str = MODEL_NAME):
        print("Listening...", flush=True)
        # Load to CPU first to avoid GPU memory spike, then move to GPU in FP16
        with _quiet():
            self.model = EncDecMultiTaskModel.from_pretrained(model_name, map_location='cpu')
            self.model = self.model.half().cuda()
            self.model.eval()
        print("Ready", flush=True)

    def transcribe(self, audio: np.ndarray) -> str:
        # Canary needs audio file path, not numpy array
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as f:
            sf.write(f.name, audio, SAMPLE_RATE)
            with _quiet():
                result = self.model.transcribe([f.name], source_lang='en', target_lang='en', verbose=False)
        if result and len(result) > 0:
            hyp = result[0]
            text = hyp.text if hasattr(hyp, 'text') else str(hyp)
            return text.strip()
        return ""
