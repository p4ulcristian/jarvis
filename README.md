# Jarvis - Voice-to-Text with Ctrl Key Trigger

A Clojure daemon that listens for Ctrl key presses and uses Faster-Whisper (Large V3 Turbo) for blazing-fast speech-to-text transcription directly into your keyboard input.

## Features

- **Global Ctrl key listener** - Press Ctrl to start/stop recording from anywhere
- **Real-time audio capture** - Records microphone input at 16kHz
- **Faster-Whisper Turbo** - 5.4x faster than standard Whisper with comparable accuracy
- **Automatic typing** - Transcribed text is automatically typed like you pressed the keys
- **Persistent subprocess** - Model loaded once for instant subsequent transcriptions

## Prerequisites

### System Requirements
- Java 11+
- Python 3.7+
- Microphone/audio input device
- Linux (tested on Arch Linux)

### Python Dependencies
This project uses a virtual environment for Python dependencies:

```bash
# Virtual environment is already set up in the project
# Dependencies are installed in venv/
python3 -m venv venv
venv/bin/pip install faster-whisper
```

### Clojure Dependencies
Handled by `deps.edn` but requires:
- Clojure 1.12.0
- JNativeHook for global keyboard hooks
- core.async for event handling
- Cheshire for JSON parsing

## Installation

1. **Clone/navigate to the project directory:**
```bash
cd /home/paul/Work/jarvis
```

2. **Set up Python virtual environment and install dependencies:**
```bash
python3 -m venv venv
venv/bin/pip install faster-whisper
```

3. **Make the Python script executable:**
```bash
chmod +x whisper_server.py
```

## Running the Daemon

### Basic usage:
```bash
clj -M:run
```

### Or build an executable JAR:
```bash
clj -A:uberjar
java -jar jarvis-standalone.jar
```

## Usage

1. **Start the daemon:**
   ```bash
   clj -M:run
   ```

2. **Press Ctrl to start recording**
   - The daemon will begin capturing audio from your microphone

3. **Speak clearly**
   - Say what you want to type

4. **Release Ctrl to transcribe and type**
   - The daemon will:
     - Stop recording
     - Send audio to Whisper
     - Type the transcription automatically

## How It Works

### Architecture

```
┌─────────────────────────────────────┐
│  Global Keyboard Listener           │
│  (JNativeHook - Ctrl key)           │
└──────────────┬──────────────────────┘
               │
       ┌───────▼────────┐
       │ Audio Capture  │
       │ (Java Sound)   │
       └───────┬────────┘
               │
         ┌─────▼──────┐
         │ Whisper    │
         │ (Python)   │
         └─────┬──────┘
               │
       ┌───────▼──────────┐
       │ Keyboard Typing  │
       │ (java.awt.Robot) │
       └──────────────────┘
```

### Components

- **keyboard.clj** - Global keyboard hook using JNativeHook
- **audio.clj** - Microphone recording using Java Sound API
- **whisper.clj** - Communication with Python Faster-Whisper subprocess
- **typer.clj** - Keyboard simulation using java.awt.Robot
- **core.clj** - Main daemon coordinating all components
- **whisper_server.py** - Persistent Python process for Faster-Whisper Turbo model

## Configuration

### Audio Settings
Adjust in `src/jarvis/audio.clj`:
- `SAMPLE_RATE` - Default: 16000 Hz
- `BITS_PER_SAMPLE` - Default: 16 bits
- `CHANNELS` - Default: 1 (mono)

### Faster-Whisper Model
The default model is "turbo" (Whisper Large V3 Turbo). Other options in `whisper_server.py`:
```python
# Options: tiny, base, small, medium, large-v2, large-v3, turbo
model = WhisperModel("large-v3", device="cuda", compute_type="int8")
```

**Note:** Uses int8 quantization for lower GPU memory usage. For better quality with more VRAM, use `compute_type="float16"`.

### Typing Delay
Adjust character-by-character delay in `core.clj` or add a parameter to `type-text-with-delay`

## Troubleshooting

### "Failed to register global keyboard hook"
On Linux, global keyboard hooks may require elevated privileges:
```bash
sudo clj -M:run
```

Or use without sudo if your user is in the `input` group:
```bash
sudo usermod -a -G input $USER
```

### Audio not being captured
- Check microphone is working: `pactl list sources` (PulseAudio)
- Verify permissions: microphone should be available to your user
- Test with: `arecord -d 3 test.wav`

### Faster-Whisper model download
First run will download the model automatically. The turbo model is ~1.5 GB and will be cached in `~/.cache/huggingface/`.

### Typing doesn't work
- Some applications may not respond to Robot input
- Try focusing a text editor first
- Some restricted applications (terminals, games) may block simulated input
- Alternative: Use xdotool instead (see notes below)

## Performance Notes

- **Model loading**: ~5 seconds (first startup only)
- **Transcription speed**: ~0.2-0.5 seconds for 2-second audio (5.4x faster than standard Whisper!)
- **Typing speed**: ~50ms per character (adjustable)
- **GPU Memory**: ~1.5-2GB VRAM with int8 quantization

**Faster-Whisper Turbo Benefits:**
- 5.4x faster than Whisper Large V2
- Comparable accuracy to standard Whisper
- Lower memory footprint with int8 quantization
- Real-time factor (RTFx): 216x on GPU

## Advanced Options

### GPU Out of Memory
If you get CUDA out of memory errors:
1. The code already uses int8 quantization (lowest memory)
2. Check GPU usage: `nvidia-smi`
3. Consider using a smaller model: "base", "small", or "medium"
4. Or use CPU mode (slower): `device="cpu", compute_type="int8"`

### Using xdotool for typing
For better compatibility on some Linux applications:
```bash
# Install xdotool
sudo pacman -S xdotool  # Arch Linux
sudo apt-get install xdotool  # Ubuntu/Debian

# Modify typer.clj to use xdotool instead of Robot
```

## Limitations

- Currently Linux only (JNativeHook has Windows/Mac versions, but not tested)
- Some characters may not type correctly depending on keyboard layout
- Robot input may not work with privileged applications (terminals, password fields)
- Audio input limited to single microphone (can be improved)

## Future Improvements

- [ ] Add configuration file support
- [ ] Per-application text editing strategies
- [ ] Custom hotkey support (not just Ctrl)
- [ ] Audio file input instead of just microphone
- [ ] GUI configuration tool
- [ ] Wake word support
- [ ] Multiple language support
- [ ] Clipboard mode (copy instead of type)

## License

MIT

## Support

Issues and questions: Check JNativeHook and Whisper documentation if you encounter problems.
