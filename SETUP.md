# JARVIS Setup

## Prerequisites Installed ✓
- Python 3.13
- Claude CLI (`/usr/bin/claude`)
- mpv (audio playback)
- jq (JSON processing)
- NeMo + PyTorch (in venv)

## Quick Start

1. **Set your OpenAI API key:**
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

2. **Run JARVIS:**
   ```bash
   ./run.sh
   ```

   Or manually:
   ```bash
   source venv/bin/activate
   ./hear.py
   ```

## Usage

1. Say "**Jarvis**" (wake word)
2. Speak your command
3. JARVIS will:
   - Transcribe with Parakeet-TDT-0.6B-v3
   - Send to Claude CLI
   - Speak response with OpenAI TTS

## Example

```
You: "Jarvis"
JARVIS: ✓ Wake word detected!
You: "What's the capital of France?"
JARVIS: [Processes with Claude] → [Speaks: "The capital of France is Paris"]
```

## Troubleshooting

### No audio input
- Check microphone permissions
- Test with: `arecord -l`

### Model loading slow
- First run downloads ~600MB model
- Subsequent runs are fast (model cached)

### GPU not detected
- Check CUDA: `nvidia-smi`
- Model will fall back to CPU (slower)

## Files

- `hear.py` - Voice input & transcription
- `think.sh` - Claude CLI integration
- `speak.sh` - Voice output
- `say.sh` - TTS implementation
- `run.sh` - Startup script
