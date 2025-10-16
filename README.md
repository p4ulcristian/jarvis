# Jarvis - Voice-to-Text with Ctrl Key Trigger

A Clojure daemon that listens for Ctrl key presses and uses OpenAI Whisper to transcribe spoken audio directly into your keyboard input.

## Features

- **Global Ctrl key listener** - Press Ctrl to start/stop recording from anywhere
- **Real-time audio capture** - Records microphone input at 16kHz
- **Whisper transcription** - Uses OpenAI's Whisper model for accurate speech-to-text
- **Automatic typing** - Transcribed text is automatically typed like you pressed the keys
- **Persistent subprocess** - Whisper model loaded once for fast subsequent transcriptions

## Prerequisites

### System Requirements
- Java 11+
- Python 3.7+
- Microphone/audio input device
- Linux (tested on Arch Linux)

### Python Dependencies
```bash
pip install openai-whisper
# or for faster transcription:
pip install faster-whisper
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

2. **Ensure Python dependencies are installed:**
```bash
pip install openai-whisper
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
- **whisper.clj** - Communication with Python Whisper subprocess
- **typer.clj** - Keyboard simulation using java.awt.Robot
- **core.clj** - Main daemon coordinating all components
- **whisper_server.py** - Persistent Python process for Whisper model

## Configuration

### Audio Settings
Adjust in `src/jarvis/audio.clj`:
- `SAMPLE_RATE` - Default: 16000 Hz
- `BITS_PER_SAMPLE` - Default: 16 bits
- `CHANNELS` - Default: 1 (mono)

### Whisper Model
The default model is "base". To use a different model, edit `whisper_server.py`:
```python
model = whisper.load_model("small")  # Options: tiny, base, small, medium, large
```

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

### Whisper model download fails
First run will download the model (~1.4 GB for "base"):
```bash
python3 -c "import whisper; whisper.load_model('base')"
```

### Typing doesn't work
- Some applications may not respond to Robot input
- Try focusing a text editor first
- Some restricted applications (terminals, games) may block simulated input
- Alternative: Use xdotool instead (see notes below)

## Performance Notes

- **First transcription**: ~10 seconds (model loading + inference)
- **Subsequent transcriptions**: ~1-2 seconds (model already loaded)
- **Typing speed**: ~50ms per character (adjustable)

To speed up transcription, install and use `faster-whisper`:
```bash
pip install faster-whisper
```

Then update `whisper_server.py` to use faster-whisper instead.

## Advanced Options

### Using whisper.cpp instead of Python
For even faster performance without Python dependency:
1. Install whisper.cpp: https://github.com/ggerganov/whisper.cpp
2. Modify `whisper.clj` to call the C++ binary directly

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
