#!/bin/bash
# Jarvis Voice Assistant
# Continuous voice assistant with wake word detection
# Usage: ./jarvis-voice.sh

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    JARVIS VOICE ASSISTANT                                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Find project root and virtual environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${SCRIPT_DIR}/source-code/venv"
SAY_SCRIPT="${SCRIPT_DIR}/source-code/services/say.sh"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}Error: Virtual environment not found at $VENV_PATH${NC}"
    exit 1
fi

# Check if say.sh exists
if [ ! -f "$SAY_SCRIPT" ]; then
    echo -e "${RED}Error: say.sh not found at $SAY_SCRIPT${NC}"
    exit 1
fi

# Check if Claude CLI is available
if ! command -v claude &> /dev/null; then
    echo -e "${RED}Error: Claude CLI not found${NC}"
    echo "Please install Claude CLI first"
    exit 1
fi

# Use virtual environment Python
PYTHON="${VENV_PATH}/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo -e "${RED}Error: Python not found in virtual environment${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Virtual environment found${NC}"
echo -e "${GREEN}✓ Claude CLI found${NC}"
echo -e "${GREEN}✓ TTS (say.sh) found${NC}"
echo ""
echo -e "${CYAN}Initializing voice assistant...${NC}"
echo -e "${YELLOW}Say 'Jarvis' to activate, then ask your question${NC}"
echo -e "${YELLOW}Press Ctrl+C to exit${NC}"
echo ""

# Export paths for Python script
export SAY_SCRIPT="$SAY_SCRIPT"

# Run Python voice assistant
"$PYTHON" << 'PYTHON_SCRIPT'
import os
import sys
import time
import wave
import tempfile
import numpy as np
import subprocess
from datetime import datetime
from enum import Enum

# Suppress NeMo logging
os.environ['HYDRA_FULL_ERROR'] = '0'
os.environ['NEMO_LOG_LEVEL'] = 'ERROR'

import logging
for logger_name in ['nemo_logger', 'nemo', 'pytorch_lightning', 'lhotse', 'hydra']:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

# Configuration
SAMPLE_RATE = 16000
CHUNK_DURATION = 3.0  # Process every 3 seconds of audio
CHANNELS = 1
FORMAT_BYTES = 2  # 16-bit audio
SILENCE_THRESHOLD = 1  # Number of silent batches to consider question complete
WAKE_WORD = "jarvis"

# State machine
class State(Enum):
    LISTENING_FOR_WAKE_WORD = 1
    CAPTURING_QUESTION = 2
    PROCESSING = 3

# Print with colors
def print_info(msg):
    print(f"\033[0;36m{msg}\033[0m")

def print_success(msg):
    print(f"\033[0;32m✓ {msg}\033[0m")

def print_warning(msg):
    print(f"\033[1;33m⚠ {msg}\033[0m")

def print_error(msg):
    print(f"\033[0;31m✗ {msg}\033[0m")

def print_wake_word():
    print(f"\033[0;35m🎤 JARVIS ACTIVATED\033[0m")

def print_listening():
    print(f"\033[0;36m👂 Listening for your question...\033[0m")

# Load model
print_info("Loading Parakeet-TDT-0.6B-v3 model...")
load_start = time.time()

import torch
import nemo.collections.asr as nemo_asr

model = nemo_asr.models.ASRModel.from_pretrained(
    model_name="nvidia/parakeet-tdt-0.6b-v3"
)

if torch.cuda.is_available():
    model = model.cuda()
    device_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.memory_allocated(0) / 1024**3
    device_info = f"GPU: {device_name} ({vram_gb:.2f} GB)"
else:
    device_info = "CPU"

model.eval()
load_time = time.time() - load_start

print_success(f"Model loaded in {load_time:.2f}s")
print_info(f"Device: {device_info}")
print()

# Initialize PyAudio
try:
    import pyaudio

    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=1024
    )

    print_success("Microphone ready")
    print()
    print("=" * 80)
    print_info("🎯 JARVIS IS LISTENING - Say 'Jarvis' to activate")
    print("=" * 80)
    print()

except ImportError:
    print_error("pyaudio not installed")
    print("Install with: pip install pyaudio")
    sys.exit(1)
except Exception as e:
    print_error(f"Failed to initialize microphone: {e}")
    sys.exit(1)

# State machine variables
current_state = State.LISTENING_FOR_WAKE_WORD
question_text = ""
silence_count = 0
batch_num = 0
current_tts_process = None

def transcribe_audio(audio_np):
    """Transcribe audio chunk"""
    # Save to temporary WAV file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
    wav_path = temp_file.name
    temp_file.close()

    with wave.open(wav_path, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(FORMAT_BYTES)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes((audio_np * 32768).astype(np.int16).tobytes())

    try:
        with torch.no_grad():
            hypotheses = model.transcribe([wav_path], return_hypotheses=True)

        # Extract text
        text = ""
        if hypotheses and len(hypotheses) > 0:
            hyp = hypotheses[0]
            if isinstance(hyp, list) and len(hyp) > 0:
                text = hyp[0].text if hasattr(hyp[0], 'text') else str(hyp[0])
            elif hasattr(hyp, 'text'):
                text = hyp.text
            else:
                text = str(hyp)

        return text.strip()
    finally:
        os.unlink(wav_path)

def ask_claude(question):
    """Send question to Claude and get response"""
    try:
        # Add context to make Claude act like a voice assistant
        prompt = f"""You are Jarvis, a helpful voice assistant. Answer in a conversational, friendly, and concise way - as if speaking out loud. Keep responses short (1-3 sentences) unless more detail is specifically requested. Be direct and helpful.

Question: {question}"""

        print_info(f"Running: claude --print \"{question[:50]}...\"")

        result = subprocess.run(
            ['claude', '--print', prompt],
            capture_output=True,
            text=True,
            timeout=60,
            env=os.environ.copy()
        )

        print_info(f"Claude exit code: {result.returncode}")

        if result.returncode == 0:
            response = result.stdout.strip()
            print_info(f"Claude response length: {len(response)} chars")
            return response
        else:
            print_error(f"Claude failed with exit code {result.returncode}")
            if result.stderr:
                print_error(f"stderr: {result.stderr[:200]}")
            if result.stdout:
                print_info(f"stdout: {result.stdout[:200]}")
            return None
    except subprocess.TimeoutExpired:
        print_error("Claude request timed out after 60s")
        return None
    except FileNotFoundError:
        print_error("Claude CLI not found in PATH")
        return None
    except Exception as e:
        print_error(f"Failed to call Claude: {e}")
        import traceback
        traceback.print_exc()
        return None

def stop_tts():
    """Stop any running TTS processes"""
    global current_tts_process

    if current_tts_process and current_tts_process.poll() is None:
        print_info("Stopping current TTS...")
        try:
            current_tts_process.terminate()
            current_tts_process.wait(timeout=1)
        except:
            current_tts_process.kill()

        current_tts_process = None

    # Also kill any mpv processes (say.sh uses mpv)
    try:
        subprocess.run(['pkill', '-9', 'mpv'], stderr=subprocess.DEVNULL)
    except:
        pass

def speak_text(text):
    """Speak text using say.sh"""
    global current_tts_process

    say_script = os.getenv('SAY_SCRIPT')

    if not say_script:
        print_error("SAY_SCRIPT environment variable not set")
        return False

    if not os.path.exists(say_script):
        print_error(f"say.sh not found at: {say_script}")
        return False

    try:
        print_info(f"Speaking with: {say_script}")
        current_tts_process = subprocess.Popen([say_script, text])
        current_tts_process.wait(timeout=30)
        current_tts_process = None
        return True
    except subprocess.TimeoutExpired:
        print_error("TTS timed out after 30s")
        if current_tts_process:
            current_tts_process.kill()
            current_tts_process = None
        return False
    except Exception as e:
        print_error(f"Failed to speak: {e}")
        return False

# Main loop
try:
    while True:
        batch_num += 1

        # Read audio
        frames_to_read = int(SAMPLE_RATE * CHUNK_DURATION)
        audio_data = stream.read(frames_to_read, exception_on_overflow=False)
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Transcribe
        text = transcribe_audio(audio_np)

        timestamp = datetime.now().strftime("%H:%M:%S")

        # State machine logic
        if current_state == State.LISTENING_FOR_WAKE_WORD:
            # Show what we're hearing
            if text:
                print(f"[{timestamp}] Heard: {text}")
            else:
                print(f"[{timestamp}] (silence)")

            if text and WAKE_WORD in text.lower():
                # Stop any running TTS immediately
                stop_tts()

                print()
                print_wake_word()
                print_listening()
                print()
                current_state = State.CAPTURING_QUESTION
                question_text = ""
                silence_count = 0

        elif current_state == State.CAPTURING_QUESTION:
            if text:
                question_text += " " + text
                silence_count = 0
                print(f"[{timestamp}] Capturing: {text}")
            else:
                silence_count += 1
                print(f"[{timestamp}] Silence ({silence_count}/{SILENCE_THRESHOLD})")

            # Check if question is complete
            if silence_count >= SILENCE_THRESHOLD and question_text.strip():
                print()
                print_info(f"Question: {question_text.strip()}")
                print_info("Asking Claude...")
                print()

                current_state = State.PROCESSING

                # Ask Claude
                response = ask_claude(question_text.strip())

                if response:
                    print("─" * 80)
                    print(f"Claude: {response}")
                    print("─" * 80)
                    print()

                    # Speak response
                    print_info("Speaking response...")
                    speak_text(response)
                    print()
                else:
                    print_error("No response from Claude")
                    speak_text("I'm sorry, I couldn't process that question.")
                    print()

                # Reset to listening
                print_success("Ready for next question")
                print()
                print("=" * 80)
                print_info("🎯 Say 'Jarvis' to activate")
                print("=" * 80)
                print()

                current_state = State.LISTENING_FOR_WAKE_WORD
                question_text = ""
                silence_count = 0

except KeyboardInterrupt:
    print()
    print("=" * 80)
    print_info("JARVIS SHUTTING DOWN")
    print("=" * 80)
    print(f"Total batches processed: {batch_num}")
    print()
    print_success("Goodbye!")

    try:
        stream.stop_stream()
        stream.close()
        p.terminate()
    except:
        pass

    sys.exit(0)

except Exception as e:
    print()
    print_error(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

PYTHON_SCRIPT
