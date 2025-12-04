"""Parakeet STT model wrapper."""

import numpy as np
import nemo.collections.asr as nemo_asr

MODEL_NAME = "nvidia/parakeet-tdt-0.6b-v2"


class SpeechToText:
    def __init__(self, model_name: str = MODEL_NAME):
        print(f"Loading model: {model_name}")
        self.model = nemo_asr.models.ASRModel.from_pretrained(model_name)
        self.model.eval()
        print("Model loaded")

    def transcribe(self, audio: np.ndarray) -> str:
        result = self.model.transcribe([audio])
        if result and len(result) > 0:
            return result[0].strip()
        return ""
