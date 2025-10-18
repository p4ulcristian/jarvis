# NeMo Setup Guide

## Migration Complete! 🎉

Your Jarvis app now uses **NVIDIA NeMo (Parakeet-TDT-1.1B)** instead of Whisper.

## Architecture

```
Jarvis (Clojure)          →  HTTP  →     Docker Container
- Keyboard listener                      - NeMo Parakeet-TDT-1.1B
- Audio capture                          - FastAPI server
- HTTP client                            - GPU inference
- Text typer
```

## Prerequisites

1. **Docker with NVIDIA GPU support**
   ```bash
   # Test GPU in Docker
   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
   ```

2. **Docker Compose**
   ```bash
   sudo pacman -S docker-compose  # Arch
   sudo apt install docker-compose  # Ubuntu
   ```

## Setup Steps

### 1. Build and start NeMo container

```bash
cd /home/paul/Work/jarvis

# Build the container (first time only - takes ~10-15 min)
docker-compose build

# Start the container
docker-compose up -d

# Check logs to see model loading
docker-compose logs -f
```

**Wait for this message:**
```
INFO:     Application startup complete.
NeMo model ready for inference!
```

### 2. Test NeMo server

```bash
# Check health
curl http://localhost:8000/health

# Should return:
# {"status":"healthy","model_loaded":true,"cuda_available":true}
```

### 3. Run Jarvis

```bash
# In another terminal
clj -M:run
```

## Quick Commands

```bash
# Start NeMo server
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop NeMo server
docker-compose down

# Restart NeMo server
docker-compose restart
```

## Troubleshooting

### Container won't start
```bash
# Check NVIDIA Docker runtime
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# If fails, install nvidia-container-toolkit
sudo pacman -S nvidia-container-toolkit
sudo systemctl restart docker
```

### Model download is slow
The first run downloads ~2GB model from Hugging Face. Be patient!

### Connection refused
```bash
# Check if container is running
docker-compose ps

# Check if port 8000 is listening
netstat -tuln | grep 8000

# Restart container
docker-compose restart
```

### Out of memory
```bash
# Check GPU memory
nvidia-smi

# If needed, use smaller model in nemo_server.py:
# nvidia/parakeet-ctc-0.6b (600MB instead of 1.1GB)
```

## Performance

- **Model loading**: ~10-15 seconds (first startup)
- **Transcription**: ~0.1-0.3 seconds for 2-second audio
- **VRAM usage**: ~2-3GB
- **Faster than Whisper?** Should be comparable or slightly faster

## What Changed

✅ Removed Python subprocess management
✅ Removed `whisper_server.py` dependency
✅ Added HTTP-based communication
✅ NeMo runs in isolated Docker container
✅ Better for production (easier to scale/restart)

## Next Steps

1. Test transcription quality
2. Compare speed vs Whisper
3. Try streaming models if you want real-time transcription
4. Optimize Docker image size (optional)

Enjoy your upgraded Jarvis! 🚀
