# Iris

A voice assistant for Wayland. Hold CapsLock to speak, release to transcribe text at your cursor.

## What It Does

- **Push-to-Talk** - Hold CapsLock, speak, release. Text appears where your cursor is.
- **Speech-to-Text** - Uses NVIDIA Canary 1B for fast, accurate transcription
- **Text-to-Speech** - Natural voice responses via Kokoro TTS
- **Visual Indicator** - Floating bubble overlay glows when listening
- **HTTP API** - Control STT/TTS from scripts or other apps

## Requirements

- Linux with Wayland (Hyprland, Sway, etc.)
- NVIDIA GPU with CUDA
- Python 3.10+
- [Kokoro TTS](https://github.com/remsky/Kokoro-FastAPI) server (for speech output)

System packages (Arch):
```bash
sudo pacman -S wtype wl-clipboard mpv jq alsa-utils
```

## Install

```bash
git clone https://github.com/yourusername/iris.git
cd iris
uv venv && uv pip install -e .
```

## Usage

Start the server:
```bash
./iris.sh
```

Then hold CapsLock and speak. Your words appear at the cursor when you release.

### Scripts

```bash
# Speak text aloud
./speak.sh "Hello there"
./speak.sh "Faster speech" 1.3

# Transcribe audio file
./listen.sh recording.wav

# Record and transcribe (press Enter to stop)
./listen.sh
```

### HTTP API

```bash
# Check server status
curl http://127.0.0.1:8765/health

# Text-to-speech
curl -X POST http://127.0.0.1:8765/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello", "speed": 1.0}'

# Speech-to-text
curl -X POST http://127.0.0.1:8765/listen \
  -F "audio=@recording.wav"
```

## How It Works

```
iris.sh
   └── server.py (loads models, runs HTTP server on :8765)
          ├── STT: NVIDIA Canary 1B (local)
          ├── TTS: Kokoro server (localhost:7123)
          ├── PTT: evdev listens for CapsLock
          └── bubble.py (GTK4 overlay)
```

**Note:** We use evdev directly for hotkey detection, not keyd. Disable CapsLock toggle in your compositor (e.g., `kb_options = caps:none` in Hyprland).

Models stay loaded in memory for instant response. First startup takes a minute to load.

## License

MIT
