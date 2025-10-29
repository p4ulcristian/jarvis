# JARVIS

A context-aware voice assistant that continuously listens, logs conversations, and responds when addressed. See [VISION.md](VISION.md) for the full story.

## Quick Start

```bash
# Install system dependencies (Arch Linux)
sudo pacman -S portaudio python-pyaudio mpv

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set OpenAI API key for TTS responses
export OPENAI_API_KEY="your-key-here"

# Run JARVIS
./jarvis.py
```

First run will download the NVIDIA Canary-1B Flash model (~1.7GB) - state-of-the-art ASR with 1000+ RTFx performance.

## What It Does Right Now

- **Continuous speech logging** - Transcribes everything to `chat.txt` with gap-free streaming
- **Push-to-talk typing** - Hold Ctrl, speak, release → auto-types transcription
- **Trigger-based typing** - `touch /tmp/jarvis-type-trigger` → records and types after countdown
- **AI detection** - Identifies when you're addressing an AI assistant
- **Conversation improvement** - Cleans up raw transcriptions (saves to `chat-revised.txt`)
- **Word boosting** - Better recognition for custom words (edit `boost_words.txt`)
- **Voice responses** - Uses OpenAI TTS to speak back (via `say.sh`)

## How It Works

```
┌─────────────────┐
│  Microphone     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  NVIDIA Canary-1B Flash         │
│  (1000+ RTFx real-time ASR)     │
│  - 4 languages supported        │
│  - Translation ready            │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  AI Detection                   │
│  (DistilBERT classifier)        │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Conversation Logger            │
│  (chat.txt + rolling buffer)    │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  LLM Response (future)          │
│         +                       │
│  OpenAI TTS (say.sh)            │
└─────────────────────────────────┘
```

## Configuration

### Word Boosting

Add custom words/names that need better recognition to `boost_words.txt`:
```
Jarvis
Claude
kubernetes
```

### Voice Activity Detection

Edit constants in `jarvis.py`:
```python
SILENCE_THRESHOLD = 10        # Audio amplitude threshold (lower = more sensitive)
MIN_SPEECH_RATIO = 0.0001     # % of frame that must be speech (0.01%)
```

### Word Corrections

Add common misrecognitions to the `WORD_CORRECTIONS` dict in `jarvis.py`:
```python
WORD_CORRECTIONS = {
    'jarve': 'Jarvis',
    'clod': 'Claude',
}
```

### TTS Voice

Edit `say.sh` to change the OpenAI voice:
```bash
# Options: alloy, echo, fable, onyx, nova, shimmer
voice: "nova"
```

## File Structure

```
jarvis/
├── jarvis.py                    # Main application
├── keyboard_listener.py         # Ctrl key monitoring for push-to-talk
├── conversation_improver.py     # Cleans up raw transcriptions
├── say.sh                       # TTS output via OpenAI
├── boost_words.txt              # Custom vocabulary for ASR
├── chat.txt                     # Raw transcription log
├── chat-revised.txt             # Improved transcription log
├── ai-detector/                 # AI detection module (optional)
└── venv/                        # Python virtual environment
```

## Usage Modes

### Continuous Logging (Default)
Just run `./jarvis.py` - it logs everything to `chat.txt` automatically.

### Push-to-Talk Typing
1. Hold Ctrl key
2. Speak
3. Release Ctrl
4. Text is automatically typed where your cursor is

### Trigger-Based Typing
```bash
touch /tmp/jarvis-type-trigger
```
Records for 2 seconds, shows transcription, counts down 3-2-1, then types.

### Voice Responses (Coming Soon)
Say "Jarvis" to get a spoken response via `say.sh`.

## Troubleshooting

### Audio not capturing
```bash
# Test microphone
arecord -d 3 test.wav && aplay test.wav

# Check permissions
sudo usermod -a -G audio $USER
```

### Too much silence transcribed
Increase thresholds in `jarvis.py`:
```python
SILENCE_THRESHOLD = 500      # Higher = less sensitive
MIN_SPEECH_RATIO = 0.02      # 2% of frame must be speech
```

### Keyboard listener fails
```bash
sudo usermod -a -G input $USER
# Log out and back in
```

### GPU out of memory
Canary-1B Flash uses ~2GB VRAM. Close other GPU applications if needed.

For CPU mode (slower), edit `config.py` and add to transcription.py:
```python
# In load_nemo_model(), remove .cuda()
model = model.cpu()
```

**Note**: CPU mode will be significantly slower (~10-50x)

## Roadmap

- [ ] Wake word detection ("Hey Jarvis")
- [ ] Full LLM conversational integration
- [ ] Context-aware responses based on conversation history
- [ ] Voice activity detection using Silero-VAD
- [ ] Local LLM option for privacy
- [ ] Multi-language support
- [ ] Proactive suggestions and assistance

## Requirements

- Python 3.8+
- CUDA-capable GPU (recommended) or CPU
- Linux (tested on Arch)
- OpenAI API key for TTS responses

## License

MIT

---

**See [VISION.md](VISION.md) for the philosophy and future direction of this project.**
