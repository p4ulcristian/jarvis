# AI Detection System

A lightweight, fast AI detection system that monitors conversation logs and triggers when someone talks to or about your AI assistant.

## Features

- **Context-aware detection**: Uses Llama 3.2 1B to understand context, not just keywords
- **Fast inference**: 10-30ms on GPU, 30-100ms on CPU
- **Low memory**: ~1-1.5GB RAM when running
- **Real-time monitoring**: Watches log files for new messages
- **Configurable**: Easy YAML configuration

## Requirements

- Python 3.8+
- CUDA-capable GPU (optional but recommended)
- ~2GB disk space for model

## Installation

### 1. Install Dependencies

**For GPU support (recommended):**
```bash
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python --force-reinstall --no-cache-dir
pip install -r requirements.txt
```

**For CPU only:**
```bash
pip install -r requirements.txt
```

### 2. Download the Model

Run the helper script to see download instructions:
```bash
python download_model.py
```

**Recommended model:**
- Visit: https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF
- Download: `Llama-3.2-1B-Instruct-Q4_K_M.gguf` (~700MB)
- Save to: `./models/llama-3.2-1b-q4_k_m.gguf`

**Alternative (smaller):**
- Visit: https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF
- Download: `tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf` (~637MB)
- Update `config.yaml` with the correct model path

### 3. Configure

Edit `config.yaml`:

```yaml
# Set your AI's name
ai_name: "Alex"

# Set your log file path
log_file: "/home/paul/ai-detector/conversation.jsonl"

# Model path
model:
  model_path: "/home/paul/ai-detector/models/llama-3.2-1b-q4_k_m.gguf"
```

## Usage

### Start the Detector

```bash
python log_watcher.py
```

The system will:
1. Load the model
2. Start monitoring your conversation log
3. Detect and log when messages are directed at your AI
4. Print detections to console and log file

### Log Format

Your conversation log should be in JSONL format (one JSON object per line):

```json
{"timestamp": "2025-10-16T10:30:00", "user": "Paul", "message": "Hey Alex, what's the weather?"}
{"timestamp": "2025-10-16T10:30:05", "user": "Alex", "message": "It's sunny today!"}
```

**Required fields:**
- `message`: The message text (required)

**Optional fields:**
- `timestamp`: ISO format timestamp (auto-generated if missing)
- `user`: Username (defaults to "Unknown")

### Test the Detector

Test with sample messages:
```bash
python ai_detector.py
```

### Add Messages Manually

```bash
echo '{"timestamp": "2025-10-16T10:30:00", "user": "Paul", "message": "Hey Alex, can you help?"}' >> conversation.jsonl
```

## How It Works

1. **Watches log file** for new messages
2. **Analyzes each message** using Llama 3.2 1B
3. **Determines context**: Is this directed AT the AI or just mentioning it?
4. **Triggers function** when AI is addressed

**Examples:**

| Message | Detection | Reason |
|---------|-----------|--------|
| "Hey Alex, what's the weather?" | ✓ TRIGGER | Direct address |
| "Can you help me with this?" | ✓ TRIGGER | Implied request |
| "I talked to Alex yesterday" | ✗ IGNORE | Past reference |
| "Alex is a nice name" | ✗ IGNORE | Talking about name |

## Configuration Options

### Detection Settings

```yaml
detection:
  threshold: 0.7        # Confidence threshold (0.0-1.0)
  verbose: true         # Enable detailed logging
```

### Model Settings

```yaml
model:
  n_gpu_layers: -1      # GPU layers (-1 = all, 0 = CPU only)
  n_ctx: 2048          # Context window
  temperature: 0.1      # Lower = more deterministic
  max_tokens: 5         # Tokens to generate (5 is enough for YES/NO)
```

## Customization

### Add Custom Function

Edit `log_watcher.py` and modify the `trigger_function` method:

```python
def trigger_function(self, timestamp: str, user: str, message: str):
    # Your custom code here
    # Examples:

    # Send notification
    import subprocess
    subprocess.run(['notify-send', 'AI Detected', message])

    # Call API
    import requests
    requests.post('http://localhost:8000/ai-trigger', json={'message': message})

    # Execute script
    subprocess.run(['./my-script.sh', message])
```

## Performance

**GPU (NVIDIA):**
- First load: ~2-5 seconds
- Per message: 10-30ms

**CPU:**
- First load: ~3-8 seconds
- Per message: 30-100ms

**Memory:**
- Model: ~700MB
- Runtime: ~1-1.5GB total

## Troubleshooting

### "Model not found" error
- Ensure you've downloaded the model to the correct path
- Check `model_path` in `config.yaml`

### Slow inference
- Enable GPU: Set `n_gpu_layers: -1` in config
- Reinstall with CUDA support (see Installation)

### GPU not detected
- Check CUDA installation: `nvidia-smi`
- Reinstall llama-cpp-python with CUDA support

### Too many false positives
- Increase `threshold` in config (try 0.8 or 0.9)

### Too many false negatives
- Decrease `threshold` in config (try 0.5 or 0.6)

## Files

- `ai_detector.py` - Core detection module
- `log_watcher.py` - Log monitoring daemon
- `config.yaml` - Configuration file
- `download_model.py` - Model download helper
- `conversation.jsonl` - Your conversation log
- `detections.log` - Detection results log

## License

MIT License - Free to use and modify
