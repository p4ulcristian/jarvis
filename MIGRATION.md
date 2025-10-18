# Migration Guide: v1 to v2

This guide helps you migrate from the original JARVIS (jarvis.py) to the production-ready v2 (jarvis_v2.py).

## What Changed?

### Architecture

**v1 (jarvis.py):**
- Monolithic 1170-line file
- Hardcoded configurations
- Print statements for logging
- Stderr suppression
- No proper error handling

**v2 (jarvis_v2.py):**
- Modular architecture with separate core modules
- Environment-based configuration (.env)
- Structured logging with levels
- Proper exception handling
- Production-ready service deployment

### Module Structure

```
jarvis/
├── core/
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── logger.py          # Logging setup
│   ├── audio.py           # Audio capture
│   ├── transcription.py   # ASR logic
│   └── buffer.py          # Buffer management
├── utils/
│   └── __init__.py
├── deploy/
│   ├── jarvis.service     # Systemd service
│   └── install.sh         # Installation script
├── jarvis_v2.py           # New main application
├── jarvis.py.backup       # Backup of original
└── .env                   # Configuration
```

## Migration Steps

### 1. Backup Your Data

```bash
# Backup existing installation
cp -r /path/to/jarvis /path/to/jarvis_backup

# Backup transcription logs
cp chat.txt chat.txt.backup
cp chat-revised.txt chat-revised.txt.backup
```

### 2. Update Repository

```bash
cd /path/to/jarvis
git pull  # or manually copy new files
```

### 3. Install Dependencies

```bash
# Reinstall with updated requirements.txt
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

### 4. Create Configuration

```bash
# Copy example config
cp .env.example .env

# Edit configuration
nano .env
```

**Key settings to transfer:**

From hardcoded constants in old `jarvis.py`:
```python
# Old hardcoded values
DEBUG_MODE = False
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 10
```

To `.env`:
```bash
DEBUG_MODE=false
SAMPLE_RATE=16000
SILENCE_THRESHOLD=10
```

### 5. Test New Version

```bash
# Test run
./jarvis_v2.py

# Check it works correctly
# Press Ctrl+C to stop
```

### 6. Update Service (if using systemd)

```bash
# Update service file
sudo cp deploy/jarvis.service /etc/systemd/system/

# Update paths in service file to match your installation
sudo nano /etc/systemd/system/jarvis.service

# Reload systemd
sudo systemctl daemon-reload

# Restart service
sudo systemctl restart jarvis
```

## Configuration Mapping

### Environment Variables

| Old Constant | New .env Variable | Default |
|--------------|-------------------|---------|
| `DEBUG_MODE` | `DEBUG_MODE` | false |
| `SAMPLE_RATE` | `SAMPLE_RATE` | 16000 |
| `CHUNK_SIZE` | `CHUNK_SIZE` | 1600 |
| `SILENCE_THRESHOLD` | `SILENCE_THRESHOLD` | 10 |
| `MIN_SPEECH_RATIO` | `MIN_SPEECH_RATIO` | 0.0001 |
| `FRAME_LEN` | `FRAME_LEN` | 1.6 |
| `LOG_FILE` | `LOG_FILE` | chat.txt |
| `ENABLE_MICROPHONE` | `ENABLE_MICROPHONE` | true |
| `ENABLE_MODEL` | `ENABLE_MODEL` | true |
| `ENABLE_VAD` | `ENABLE_VAD` | true |
| `ENABLE_AI_DETECTION` | `ENABLE_AI_DETECTION` | false |
| `ENABLE_TRANSCRIPTION` | `ENABLE_TRANSCRIPTION` | true |

### Feature Flags

All feature flags from old `jarvis.py` are now configurable via `.env`:

```bash
# Old: Hardcoded in jarvis.py
ENABLE_MICROPHONE = True
ENABLE_MODEL = True

# New: .env file
ENABLE_MICROPHONE=true
ENABLE_MODEL=true
```

## Removed Features (Temporarily)

The following features were disabled in v1 and are not yet re-implemented in v2:

1. **Keyboard Listener** - Push-to-talk mode
   - Status: Disabled in v1, not in v2
   - Reason: Caused memory conflicts
   - Migration: Not needed

2. **Conversation Improver** - LLM post-processing
   - Status: Separate process, still works
   - Location: `conversation_improver.py`
   - Migration: Run separately if needed

3. **AI Detection** - Detect if speaking to AI
   - Status: Disabled by default
   - Migration: Set `ENABLE_AI_DETECTION=true` in .env

## Breaking Changes

### Logging

**Old:**
```python
print(f"[INFO] Message")
print(f"[ERROR] Error", file=sys.stderr)
```

**New:**
```python
logger.info("Message")
logger.error("Error")
```

### Configuration Access

**Old:**
```python
# Direct constant access
if DEBUG_MODE:
    print("Debug")
```

**New:**
```python
# Via config object
if self.config.debug_mode:
    logger.debug("Debug")
```

## Rollback Plan

If v2 doesn't work:

### Option 1: Quick Rollback

```bash
# Use backup
cp jarvis.py.backup jarvis.py

# Or checkout old version
git checkout <old-commit> jarvis.py
```

### Option 2: Run Old Version Directly

```bash
# The backup is still there
./jarvis.py.backup
```

## Validation Checklist

After migration, verify:

- [ ] Audio capture working
- [ ] Transcriptions appearing in chat.txt
- [ ] Model loading correctly
- [ ] VAD filtering working
- [ ] Word corrections applied
- [ ] Logs being generated properly
- [ ] Service starts/stops cleanly (if using systemd)

## Testing

### Minimal Test

```bash
# Start v2
./jarvis_v2.py

# Speak into microphone
# Check output appears
# Press Ctrl+C
# Check chat.txt has content
```

### Full Test

```bash
# Enable debug mode
echo "DEBUG_MODE=true" >> .env

# Run and check detailed logs
./jarvis_v2.py

# Verify:
# - Audio chunks being captured
# - VAD detecting speech
# - Transcriptions being generated
# - Text being written to files
```

## Getting Help

If you encounter issues:

1. Enable debug mode: `DEBUG_MODE=true`
2. Check logs: `tail -f logs/jarvis.log` or `journalctl -u jarvis -f`
3. Compare with backup: `diff jarvis.py.backup jarvis_v2.py`
4. File an issue with logs

## Performance Comparison

| Metric | v1 | v2 |
|--------|----|----|
| Lines of Code | 1170 (monolithic) | ~600 (modular) |
| Startup Time | ~5s | ~5s |
| Memory Usage | ~3GB | ~3GB |
| CPU Usage | Similar | Similar |
| Logging | Print statements | Structured logging |
| Configuration | Hardcoded | .env file |

## Next Steps

After successful migration:

1. Monitor for a few days
2. Tune VAD settings if needed
3. Add custom words to `boost_words.txt`
4. Set up systemd service for auto-start
5. Configure log rotation
6. Set up monitoring/alerting

---

**For deployment help, see [DEPLOYMENT.md](DEPLOYMENT.md)**
