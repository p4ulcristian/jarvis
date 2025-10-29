# CRITICAL TEST - Speak Into Mic!

## The Issue

Model returns empty for **all** Netflix audio chunks, even with good levels (378 amplitude).

**This suggests**: Microphone→Netflix audio quality might be too degraded for the model.

## PLEASE TRY THIS TEST

**Speak directly into your microphone** and see if THAT gets transcribed:

```bash
source-code/venv/bin/python test_real_transcription.py
```

When you see "(Netflix should be playing NOW)", **SPEAK CLEARLY into the mic**:
- Say: "Hello world"
- Say: "Testing one two three"
- Say: "The quick brown fox"

## What This Tests

- If speaking works → Model is fine, Netflix audio quality is the problem
- If speaking doesn't work → Something else is wrong with the model

## Possible Issues

### 1. Netflix Through Mic Doesn't Work Well
**Problem**: Netflix → Speakers → Room → Microphone = Degraded audio
**Solution**: Use a loopback device to capture system audio directly

### 2. Model Needs More Context
**Problem**: Streaming model needs cache to build up
**Solution**: Let it run for longer (30+ seconds)

### 3. Chunk Size Too Small
**Problem**: 1.6 second chunks might be too short
**Solution**: Increase chunk size in config

## Quick Fix to Try

Edit `.env` or set:
```bash
FRAME_LEN=3.2  # Double the chunk size
```

This gives the model more context per chunk.

## Check Audio Routing

```bash
# List audio devices
python3 -c "import sounddevice; print(sounddevice.query_devices())"
```

Make sure JARVIS is using the right microphone!

---

**NEXT STEP**: Run the test and speak into your mic. Tell me if you see any transcribed words!
