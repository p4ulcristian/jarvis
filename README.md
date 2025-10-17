# JARVIS - Voice-to-Text System

Continuous speech logging with NeMo ASR, push-to-talk, and automatic typing modes.

## Features

- **Real-time streaming transcription** - True continuous speech capture with NO GAPS
- **Voice Activity Detection (VAD)** - Energy-based silence filtering prevents hallucinations
- **Overlapping audio buffers** - Uses sliding window approach to prevent word cutoff
- **Background audio capture** - Separate thread ensures no audio is lost during transcription
- **Smart deduplication** - Filters repeated text and common hallucination phrases
- **Push-to-talk mode** - Hold Ctrl to record, release to transcribe and type
- **Typing mode** - Trigger-based recording with countdown before typing
- **AI detection** - Detects when you're addressing an AI assistant
- **NeMo Parakeet-TDT-1.1B** - Fast, accurate speech recognition with GPU acceleration
- **Auto-typing** - Transcribed text is automatically typed into any application

## Prerequisites

### System Requirements
- Python 3.8+
- CUDA-capable GPU (recommended) or CPU
- Microphone/audio input device
- Linux (tested on Arch Linux)

### System Dependencies

**Arch Linux:**
```bash
sudo pacman -S portaudio python-pyaudio
```

**Ubuntu/Debian:**
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
```

## Installation

1. **Clone/navigate to the project directory:**
```bash
cd /home/paul/Work/jarvis
```

2. **Set up Python virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Set up AI detector (optional):**
```bash
cd ai-detector
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
```

## Running JARVIS

### Quick Start

```bash
./jarvis.py
```

Or with the startup script:
```bash
./jarvis.sh
```

### First Run

The first time you run JARVIS, it will:
- Download the NeMo Parakeet-TDT-1.1B model (~2GB)
- Load the model onto GPU (takes ~10-15 seconds)
- Start the keyboard listener
- Begin continuous speech logging

## Usage Modes

### 1. Continuous Logging (Default) - **TRUE REAL-TIME**

JARVIS uses streaming architecture for gap-free transcription:
- Background thread continuously captures audio (no recording stops)
- Overlapping 1.6-second frames processed every ~1.6 seconds
- All speech is logged to `conversation.json` (5-minute rolling buffer)
- Transcriptions are printed with timestamps as they are detected
- AI detection runs periodically to detect if you're addressing an assistant
- **No audio is lost during transcription** - truly continuous

### 2. Push-to-Talk

Press and hold Ctrl while speaking:
1. Hold Ctrl
2. Speak clearly
3. Release Ctrl
4. JARVIS transcribes and automatically types the text

### 3. Typing Mode (Trigger-based)

Trigger a recording that will be typed after a countdown:
```bash
touch /tmp/jarvis-type-trigger
```

JARVIS will:
- Record for 2 seconds
- Show transcription
- Count down 3...2...1...
- Type the transcribed text

## Architecture

```
┌───────────────────────────────────────────────┐
│         jarvis.py (Main Process)              │
│                                               │
│  ┌──────────────┐    ┌──────────────────┐   │
│  │ Audio Thread │───▶│ Streaming Buffer │   │
│  │ (Background) │    │   (Queue-based)  │   │
│  └──────────────┘    └─────────┬────────┘   │
│                                 │            │
│  ┌──────────────────────────────▼─────────┐  │
│  │      FrameASR (Sliding Window)         │  │
│  │  - 1.6s overlapping frames             │  │
│  │  - Continuous transcription            │  │
│  │  - No gaps in audio capture            │  │
│  └────────────────┬───────────────────────┘  │
│                   │                           │
│  ┌────────────────▼──────────────┐           │
│  │  NeMo Parakeet-TDT-1.1B Model │           │
│  │       (GPU Accelerated)        │           │
│  └────────────────────────────────┘           │
└───────────────┬───────────────────────────────┘
                │
         ┌──────┴──────┐
         │             │
   ┌─────▼────┐  ┌────▼─────────┐
   │Keyboard  │  │ AI Detector  │
   │Listener  │  │ (DistilBERT) │
   └──────────┘  └──────────────┘
```

## Configuration

### Audio Settings

Edit `jarvis.py` constants:
```python
SAMPLE_RATE = 16000         # Audio sample rate (Hz)
CHUNK_SIZE = 1600           # 100ms chunks (streaming capture)
FRAME_LEN = 1.6             # Frame length in seconds (for transcription)
CHUNK_DURATION_SEC = 0.1    # Chunk duration (100ms)
BUFFER_DURATION = 300       # 5 minutes for AI detection
```

**Voice Activity Detection:**
```python
SILENCE_THRESHOLD = 500      # Minimum audio amplitude for speech
MIN_SPEECH_RATIO = 0.02      # Min 2% of frame must exceed threshold
```

**Tuning Tips:**
- **Too much silence transcribed?** Increase `SILENCE_THRESHOLD` (try 800-1000)
- **Missing quiet speech?** Decrease `SILENCE_THRESHOLD` (try 300-400)
- **Frame length:** Increase `FRAME_LEN` (2.0) for accuracy, decrease (1.0) for speed
- Default values work well for most environments

### AI Detection

Edit detection parameters:
```python
DETECTION_COOLDOWN = 30  # Seconds between checks
AI_DETECTOR_SCRIPT = "ai-detector/ai_detector_cli.py"
```

### Typing Speed

Adjust character delay in `type_text()` method:
```python
time.sleep(0.01)  # 10ms between characters
```

## File Structure

```
jarvis/
├── jarvis.py                 # Main application
├── keyboard_listener.py      # Ctrl key monitoring
├── requirements.txt          # Python dependencies
├── conversation.json         # Speech log (5-min rolling)
├── ai-detector/              # AI detection module
│   ├── ai_detector_cli.py
│   └── venv/
└── venv/                     # Python virtual environment
```

## Troubleshooting

### Model Loading Issues

```bash
# Clear Hugging Face cache and retry
rm -rf ~/.cache/huggingface/hub/models--nvidia--parakeet-tdt-1.1b
./jarvis.py
```

### Audio Not Capturing

```bash
# Check microphone
pactl list sources short

# Test recording
arecord -d 3 test.wav && aplay test.wav

# Check permissions
groups | grep audio
```

### GPU Out of Memory

Edit `jarvis.py` to use CPU mode:
```python
# In load_model() method, force CPU:
self.model = self.model.cpu()
```

Or use a smaller model:
```python
# Replace model name with smaller variant
self.model = nemo_asr.models.ASRModel.from_pretrained(
    "nvidia/parakeet-ctc-0.6b"  # 600MB instead of 1.1GB
)
```

### Keyboard Listener Fails

The keyboard listener may require permissions:
```bash
# Add user to input group
sudo usermod -a -G input $USER

# Log out and back in, then test
./keyboard_listener.py
```

### Transcribing Nonsense/Hallucinations

If you're getting transcriptions when silent:

**1. Adjust silence threshold:**
```python
# In jarvis.py, increase these values:
SILENCE_THRESHOLD = 800  # Higher = less sensitive
MIN_SPEECH_RATIO = 0.05  # 5% instead of 2%
```

**2. Check microphone gain:**
```bash
# Lower microphone input level
pactl set-source-volume @DEFAULT_SOURCE@ 80%
```

**3. Add more hallucination phrases:**
```python
# In jarvis.py, add to HALLUCINATION_PHRASES:
HALLUCINATION_PHRASES = {
    'thank you', 'thanks for watching',
    'your_common_hallucination_here'  # Add phrases you see
}
```

### Typing Doesn't Work

- Some applications block simulated keyboard input (terminals, password fields)
- Try focusing a text editor first
- For better compatibility, consider using `xdotool`:

```bash
sudo pacman -S xdotool  # Arch
sudo apt-get install xdotool  # Ubuntu
```

## Performance

- **Model loading**: ~10-15 seconds (first startup only)
- **Streaming latency**: ~0.1-0.3 seconds per frame (1.6s audio)
- **Audio capture**: Continuous, no gaps or dropped audio
- **VRAM usage**: ~2-3GB with NeMo Parakeet-TDT-1.1B
- **CPU usage**: Minimal during inference
- **Background thread**: Adds <1% CPU overhead

**Real-time Factor:**
- Processes 1.6 seconds of audio in ~0.2 seconds (8x real-time)
- Background capture ensures zero audio loss

## Advanced Options

### Docker Deployment (Alternative)

```bash
docker-compose up -d
```

See `NEMO_SETUP.md` for Docker-based deployment with HTTP API.

### Custom Hotkeys

Edit `keyboard_listener.py` to change the trigger key:
```python
# Replace ctrl with another key
if key == keyboard.Key.space:  # Use spacebar instead
```

## Limitations

- Currently Linux only
- Some applications may not accept simulated typing (terminals, password fields)
- Continuous mode consumes battery on laptops
- AI detection requires separate model
- Transcription still uses file I/O (future: use NeMo's direct buffer inference)

## Future Improvements

- [x] ~~Streaming transcription (real-time)~~ **IMPLEMENTED!**
- [x] ~~VAD (Voice Activity Detection)~~ **IMPLEMENTED!**
- [ ] Direct buffer inference (eliminate file I/O for even lower latency)
- [ ] Advanced VAD using pretrained models (silero-vad)
- [ ] Wake word support ("Hey Jarvis")
- [ ] Multiple language support
- [ ] Clipboard mode (copy instead of type)
- [ ] Custom hotkey configuration
- [ ] GUI configuration tool
- [ ] Per-application typing strategies

## License

MIT

## Acknowledgments

- **NVIDIA NeMo** - ASR framework
- **Parakeet-TDT-1.1B** - Speech recognition model
- **pynput** - Keyboard control
- **PyAudio** - Audio capture
