#!/usr/bin/env python3
"""
NeMo ASR server using Parakeet-TDT-1.1B model.
Provides a REST API for audio transcription optimized for RTX 3080.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import nemo.collections.asr as nemo_asr
import torch
import uvicorn
import tempfile
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NeMo ASR Server", version="1.0")

# Global model variable
model = None

@app.on_event("startup")
async def load_model():
    """Load NeMo model on startup"""
    global model
    try:
        logger.info("Loading NeMo Parakeet-TDT-1.1B model on GPU...")

        # Load pretrained model
        model = nemo_asr.models.ASRModel.from_pretrained(
            "nvidia/parakeet-tdt-1.1b"
        )

        # Move to GPU if available
        if torch.cuda.is_available():
            model = model.cuda()
            logger.info(f"Model loaded on GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"GPU Memory allocated: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")
        else:
            logger.warning("CUDA not available, using CPU (will be slower)")

        model.eval()
        logger.info("NeMo model ready for inference!")

    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """
    Transcribe audio file to text.

    Accepts: audio files (wav, mp3, flac, etc.)
    Returns: {"success": true, "text": "transcribed text"}
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Save uploaded file to temp location
    temp_file = None
    try:
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            temp_file = tmp.name
            content = await file.read()
            tmp.write(content)

        logger.info(f"Transcribing file: {temp_file}")

        # Transcribe
        with torch.no_grad():
            transcription = model.transcribe([temp_file])

        # Extract text - NeMo returns a list of tuples/lists
        # Format: [(['text1'], ['text1'])] or similar
        if isinstance(transcription, (list, tuple)) and len(transcription) > 0:
            # Get first element
            first = transcription[0]
            # If it's a tuple/list, get the first text element
            if isinstance(first, (list, tuple)) and len(first) > 0:
                text_elem = first[0]
                # Extract string from nested structure
                if isinstance(text_elem, (list, tuple)) and len(text_elem) > 0:
                    text = str(text_elem[0])
                else:
                    text = str(text_elem)
            else:
                text = str(first)
        else:
            text = str(transcription)

        logger.info(f"Transcribed: {text}")

        return JSONResponse({
            "success": True,
            "text": text.strip()
        })

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )

    finally:
        # Clean up temp file
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "cuda_available": torch.cuda.is_available()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
