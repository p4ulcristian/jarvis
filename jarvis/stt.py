"""Canary STT model wrapper."""

import tempfile
import torch
import numpy as np
import soundfile as sf
from nemo.collections.asr.models import ASRModel

MODEL_NAME = "nvidia/canary-1b-v2"
SAMPLE_RATE = 16000


class SpeechToText:
    def __init__(self, model_name: str = MODEL_NAME):
        print(f"Loading model: {model_name}", flush=True)
        # Load to CPU first to avoid GPU memory spike, then move to GPU in FP16
        self.model = ASRModel.from_pretrained(model_name, map_location='cpu')
        self.model = self.model.half().cuda()
        self.model.eval()
        print("Model loaded", flush=True)

    def transcribe(self, audio: np.ndarray) -> str:
        # Canary needs audio file path, not numpy array
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as f:
            sf.write(f.name, audio, SAMPLE_RATE)
            result = self.model.transcribe([f.name], source_lang='en', target_lang='en')
        if result and len(result) > 0:
            hyp = result[0]
            text = hyp.text if hasattr(hyp, 'text') else str(hyp)
            return text.strip()
        return ""
