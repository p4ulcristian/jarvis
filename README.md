# JARVIS - Simple Voice Assistant

A minimal voice assistant that listens, thinks, and speaks.

## Architecture

Three simple scripts:

1. **hear.py** - Listens for "jarvis" wake word, transcribes command (Parakeet-TDT-0.6B-v3)
2. **think.sh** - Sends command to Claude CLI for processing
3. **speak.sh** - Speaks response using OpenAI TTS

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="your-key-here"

# Run
./hear.py
```

## Usage

1. Say "Jarvis" (wake word)
2. Speak your command
3. JARVIS will:
   - Transcribe your command
   - Send it to Claude
   - Speak Claude's response back to you

## Requirements

- Python 3.10+
- CUDA-capable GPU (recommended)
- OpenAI API key
- Claude CLI installed (`claude` command available)
- Audio: `mpv`, `jq` installed

## Example

```
You: "Jarvis"
JARVIS: ✓ Wake word detected!
You: "What's the weather like?"
JARVIS: [Sends to Claude] → [Speaks response]
```
