# Jarvis

Voice assistant with push-to-talk STT and TTS for Wayland.

## Architecture

```
jarvis.sh → server.py (loads STT + TTS models once)
                ↓
    ┌───────────┴───────────┐
    │                       │
listen.sh              speak.sh
(STT via /listen)      (TTS via /speak)
    │                       │
    └───────────┬───────────┘
                ↓
         keyd PTT signals
      (CapsLock hold/release)
```

## Requirements

- Hyprland (or any Wayland compositor)
- NVIDIA GPU with CUDA
- Python 3.10+
- keyd, wtype, wl-clipboard, mpv, jq

## Install

```bash
# System deps (Arch)
sudo pacman -S keyd wtype wl-clipboard mpv jq

# Clone and install
git clone https://github.com/p4ulcristian/jarvis.git
cd jarvis
uv venv && uv pip install -e .

# Run install script
./install.sh
```

## Usage

Start the server:
```bash
./jarvis.sh
# or
systemctl --user start jarvis
```

### Push-to-talk
Hold CapsLock and speak. Text appears at cursor on release.

### CLI

```bash
# Text-to-speech
./speak.sh "Hello world"

# Speech-to-text (record until Enter)
./listen.sh

# STT from file
./listen.sh audio.wav
```

### HTTP API

```bash
# Health check
curl http://127.0.0.1:8765/health

# TTS
curl -X POST http://127.0.0.1:8765/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello"}' -o output.wav

# STT
curl -X POST http://127.0.0.1:8765/listen \
  -F "audio=@recording.wav"

# PTT control
curl -X POST http://127.0.0.1:8765/ptt/start
curl -X POST http://127.0.0.1:8765/ptt/stop
```

## Config

Environment variables:
- `JARVIS_OUTPUT_MODE` - `clipboard` (default) or `type`
