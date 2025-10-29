# AEC (Acoustic Echo Cancellation) Investigation

## Problem
Enabling AEC causes `malloc()` corruption errors and crashes.

## Root Cause
Multiple concurrent audio streams with different sample rates + resampling causes memory corruption in C libraries.

### Technical Details
1. **Microphone**: 48kHz native → needs resampling to 16kHz
2. **System Monitor**: 48kHz native → needs resampling to 16kHz
3. **Resampling libraries** (scipy/resampy) use C extensions
4. **sounddevice** uses C bindings to PortAudio
5. **Concurrent streams** + **resampling** → malloc corruption

## Attempted Fixes
- ✅ Added buffer size alignment
- ✅ Implemented time-synchronized resampling
- ✅ Added padding/trimming to match exact buffer sizes
- ✅ Removed fixed blocksize parameter
- ❌ Still crashes with `malloc(): invalid size (unsorted)`

## What Works
- ✓ Single-stream audio capture (regular AudioCapture)
- ✓ Continuous transcription
- ✓ Wake word detection (when enabled)
- ✓ Speaker recognition (when enrolled)

## What Doesn't Work
- ✗ Dual-stream audio capture (SystemAudioCapture)
- ✗ AEC processing
- ✗ Echo removal from system audio

## Current Status
**AEC is DISABLED by default** in config.py

The system works perfectly for continuous transcription without AEC.

## Future Solutions

### Option 1: Use PipeWire/PulseAudio Native AEC
Instead of capturing two streams and doing AEC in Python:
- Enable PipeWire's built-in echo cancellation module
- Let the audio server handle AEC at system level
- Much more efficient and no malloc issues

### Option 2: Use Lower-Level Audio Library
- Replace sounddevice with pyaudio or direct ALSA
- More control over buffer management
- Avoid C library conflicts

### Option 3: External AEC Process
- Run AEC in separate process via IPC
- Isolate memory issues
- More complex architecture

## Recommendation
**Use PipeWire native AEC** - it's designed for this and runs at the kernel/system level.

Enable with:
```bash
pactl load-module module-echo-cancel
```

Then JARVIS will receive pre-cleaned audio automatically.
