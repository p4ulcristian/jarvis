# JARVIS Production Deployment Guide

This guide covers deploying JARVIS in a production environment.

## Prerequisites

### System Requirements
- Linux (tested on Arch Linux)
- Python 3.8+
- CUDA-capable GPU (recommended) or CPU
- 4GB+ RAM (8GB+ recommended)
- Audio input device (microphone)

### System Dependencies
```bash
# Arch Linux
sudo pacman -S portaudio python-pip mpv

# Ubuntu/Debian
sudo apt-get install portaudio19-dev python3-pip mpv

# Fedora
sudo dnf install portaudio-devel python3-pip mpv
```

## Quick Installation

Use the automated installation script:

```bash
cd /path/to/jarvis
./deploy/install.sh
```

This script will:
1. Check system dependencies
2. Create Python virtual environment
3. Install all Python packages
4. Create `.env` configuration file
5. Optionally install systemd service

## Manual Installation

### 1. Clone and Setup

```bash
git clone <repository-url> jarvis
cd jarvis
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and configure:

```bash
# Required: OpenAI API key for TTS
OPENAI_API_KEY=your-key-here

# Optional: Feature flags
ENABLE_MICROPHONE=true
ENABLE_MODEL=true
ENABLE_TRANSCRIPTION=true
DEBUG_MODE=false
```

### 4. Create Data Directories

```bash
mkdir -p logs data
```

## Running JARVIS

### Manual Execution

```bash
source venv/bin/activate
./jarvis_v2.py
```

### Systemd Service (Recommended for Production)

#### Install Service

```bash
# Edit deploy/jarvis.service and update paths
sudo cp deploy/jarvis.service /etc/systemd/system/
sudo systemctl daemon-reload
```

#### Start/Stop Service

```bash
# Start JARVIS
sudo systemctl start jarvis

# Stop JARVIS
sudo systemctl stop jarvis

# Enable auto-start on boot
sudo systemctl enable jarvis

# View logs
sudo journalctl -u jarvis -f
```

#### Service Status

```bash
sudo systemctl status jarvis
```

## Configuration

### Environment Variables

All configuration is done via `.env` file. See `.env.example` for all available options.

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_MICROPHONE` | true | Enable audio capture |
| `ENABLE_MODEL` | true | Enable NeMo ASR model |
| `SAMPLE_RATE` | 16000 | Audio sample rate (Hz) |
| `SILENCE_THRESHOLD` | 10 | VAD threshold (lower = more sensitive) |
| `DEBUG_MODE` | false | Enable debug logging |
| `LOG_FILE` | chat.txt | Transcription output file |

### Word Boosting

Add custom words/phrases to `boost_words.txt` for better recognition:

```txt
Jarvis
Claude
kubernetes
TensorFlow
```

## Monitoring

### Logs

View application logs:

```bash
# Systemd journal
sudo journalctl -u jarvis -f

# Or check log files
tail -f logs/jarvis.log
```

### Metrics (Optional)

If `ENABLE_METRICS=true`, metrics are exposed on port 9090:

```bash
curl http://localhost:9090/metrics
```

## Troubleshooting

### Audio Not Capturing

```bash
# Test microphone
arecord -d 3 test.wav && aplay test.wav

# Check permissions
sudo usermod -a -G audio $USER
# Log out and back in
```

### GPU Out of Memory

Edit `.env`:
```bash
# Force CPU mode
CUDA_VISIBLE_DEVICES=""
```

Or reduce model size in `core/transcription.py` by switching to smaller model.

### Too Much Noise/Silence

Adjust VAD settings in `.env`:

```bash
# More sensitive (captures more)
SILENCE_THRESHOLD=5
MIN_SPEECH_RATIO=0.00001

# Less sensitive (captures less)
SILENCE_THRESHOLD=50
MIN_SPEECH_RATIO=0.001
```

### Service Won't Start

Check logs:
```bash
sudo journalctl -u jarvis -n 50
```

Common issues:
- Missing `.env` file
- Invalid API keys
- Permission issues with audio device
- Missing dependencies

## Security

### API Keys

- Never commit `.env` to version control
- Use environment-specific `.env` files
- Rotate keys regularly

### File Permissions

```bash
# Secure .env file
chmod 600 .env

# Secure service file
sudo chmod 644 /etc/systemd/system/jarvis.service
```

### Network Security

- JARVIS doesn't open any network ports by default (except metrics if enabled)
- Firewall configuration not required unless using metrics endpoint

## Backup and Recovery

### Backup Transcriptions

```bash
# Backup logs
tar -czf jarvis-backup-$(date +%Y%m%d).tar.gz chat.txt chat-revised.txt logs/
```

### Restore

```bash
tar -xzf jarvis-backup-YYYYMMDD.tar.gz
```

## Updating

```bash
cd /path/to/jarvis
git pull
source venv/bin/activate
pip install -r requirements.txt --upgrade

# If using systemd
sudo systemctl restart jarvis
```

## Uninstalling

```bash
# Stop and disable service
sudo systemctl stop jarvis
sudo systemctl disable jarvis
sudo rm /etc/systemd/system/jarvis.service
sudo systemctl daemon-reload

# Remove application
rm -rf /path/to/jarvis
```

## Performance Tuning

### CPU Usage

Limit CPU usage via systemd:

```ini
# In jarvis.service
CPUQuota=150%  # Max 1.5 cores
```

### Memory Usage

Limit memory:

```ini
# In jarvis.service
MemoryLimit=4G
```

### GPU Memory

For RTX 3080 or similar:
- Model uses ~2-3GB VRAM
- Monitor with `nvidia-smi`
- Adjust batch size if needed (currently single-stream)

## Support

For issues:
1. Check logs: `sudo journalctl -u jarvis -f`
2. Enable debug mode: `DEBUG_MODE=true`
3. Check GitHub issues
4. File a bug report with logs

---

**See [README.md](README.md) for feature documentation and [VISION.md](VISION.md) for project roadmap.**
