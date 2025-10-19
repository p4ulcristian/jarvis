# FastConformer Streaming Implementation

## Overview

JARVIS now uses **NVIDIA NeMo FastConformer** with **cache-aware streaming** for ultra-low latency speech recognition (~80-160ms per chunk).

## What is Cache-Aware Streaming?

Traditional ASR models process entire audio files at once. Streaming models process audio in real-time chunks, but this is challenging because:
1. Models need context from previous chunks
2. Reprocessing overlapping audio is wasteful
3. Maintaining state across chunks is complex

FastConformer solves this with **cache-aware streaming**:
- Stores intermediate encoder activations in a cache
- Reuses cached activations from previous chunks
- Only processes new audio, avoiding redundant computation
- Maintains decoder state (`previous_hypotheses`) for autoregressive decoding

## Architecture

```
Audio Input (1.6s chunk)
    ↓
Preprocessor (convert to features)
    ↓
FastConformer Encoder (with cache)
    ├─ cache_last_channel (MHA cache)
    ├─ cache_last_time (convolution cache)
    └─ cache_last_channel_len (lengths)
    ↓
RNNT/CTC Decoder (with previous_hypotheses)
    ↓
Transcribed Text
```

## Key Features

### 1. Streaming API (`conformer_stream_step`)

The implementation uses NeMo's `conformer_stream_step` API:

```python
(
    previous_pred_out,          # Decoder predictions (for next step)
    transcribed_texts,          # Actual transcriptions!
    cache_last_channel,         # Updated encoder cache (MHA)
    cache_last_time,            # Updated encoder cache (convolutions)
    cache_last_channel_len,     # Updated cache lengths
    previous_hypotheses,        # Updated decoder hypotheses
) = model.conformer_stream_step(
    processed_signal=processed_signal,
    processed_signal_length=processed_signal_length,
    cache_last_channel=cache_last_channel,
    cache_last_time=cache_last_time,
    cache_last_channel_len=cache_last_channel_len,
    keep_all_outputs=False,
    previous_hypotheses=previous_hypotheses,
    previous_pred_out=previous_pred_out,
    drop_extra_pre_encoded=None,
    return_transcription=True,
)
```

### 2. State Management

The `FrameASR` class maintains:
- **Encoder cache**: Stores activations from previous chunks
- **Decoder state**: Maintains hypotheses for autoregressive decoding
- **VAD state**: Tracks audio energy for speech detection

### 3. Fallback Mode

If the model doesn't support streaming (e.g., using a non-streaming model), it automatically falls back to regular transcription.

## Configuration

### Model Selection

In `.env` or environment:
```bash
# Default: Multi-latency streaming model (supports 0ms, 80ms, 480ms, 1040ms)
MODEL_NAME=nvidia/stt_en_fastconformer_hybrid_large_streaming_multi

# This is the recommended model as it supports multiple latencies
```

### Streaming Parameters

```bash
# Audio chunk size (in seconds)
FRAME_LEN=1.6

# Sample rate (must match model)
SAMPLE_RATE=16000

# Decoder type (rnnt or ctc)
DECODER_TYPE=rnnt
```

## Performance

### Latency Comparison

| Model Variant | Look-ahead | Expected Latency | Accuracy |
|--------------|------------|------------------|----------|
| 80ms         | 80ms       | ~80-160ms       | Good     |
| 480ms        | 480ms      | ~480-560ms      | Better   |
| 1040ms       | 1040ms     | ~1040-1120ms    | Best     |

### Processing Time

- **Chunk size**: 1.6 seconds of audio
- **Processing time**: 80-160ms per chunk
- **Real-time factor**: ~0.05-0.10 (10-20x faster than real-time)
- **VRAM usage**: ~2-3GB for large model (114M params)

## How It Works

### 1. Audio Capture
```python
# Capture 1.6s chunk at 16kHz
chunk = audio_capture.capture_chunk()  # 25,600 samples
```

### 2. VAD (Voice Activity Detection)
```python
# Check if chunk contains speech
if frame_asr.has_speech(chunk):
    # Process this chunk
```

### 3. Streaming Transcription
```python
# Transcribe with cache-aware streaming
text = frame_asr.transcribe_chunk(chunk)
# Cache is automatically maintained between calls
```

### 4. Cache Management
The cache persists across chunks, maintaining encoder state:
- **First chunk**: Cache is None, processes from scratch
- **Subsequent chunks**: Uses cache from previous chunk
- **On silence**: Can optionally reset cache with `frame_asr.reset()`

## Advantages Over Previous Implementation

### Old (Buffered) Approach
- Used sliding buffer with overlapping audio
- Wrote audio to temporary WAV files
- Reprocessed overlapping portions
- Manual deduplication needed
- Higher latency (~200-400ms)

### New (Streaming) Approach
- ✓ No temporary files
- ✓ No redundant computation
- ✓ Cache reuses previous activations
- ✓ Lower latency (~80-160ms)
- ✓ Better integration with model
- ✓ Direct tensor processing
- ✓ Automatic state management

## Debugging

### Enable Debug Logging
```bash
DEBUG_MODE=true
```

### Log Messages to Watch For
```
✓ Streaming mode enabled - cache-aware processing active
✓ conformer_stream_step API available
Using cache-aware streaming mode with conformer_stream_step
Streaming transcription in 142.3ms | Raw: 'hello world'
```

### Common Issues

**1. Model doesn't support streaming**
```
⚠ conformer_stream_step not available - will use fallback transcription
```
Solution: Use a streaming model (contains `_streaming_` in name)

**2. Slow transcription**
- Check GPU is being used: `nvidia-smi`
- Try smaller model variant
- Reduce chunk size

**3. Poor accuracy**
- Use longer look-ahead model (480ms or 1040ms)
- Enable word boosting (see config/boost_words.txt)
- Adjust VAD thresholds

## References

- [NeMo FastConformer Documentation](https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/asr/models.html)
- [Cache-Aware Streaming Paper](https://arxiv.org/abs/2312.17279)
- [NeMo Streaming Tutorial](https://github.com/NVIDIA-NeMo/NeMo/blob/main/tutorials/asr/Online_ASR_Microphone_Demo_Cache_Aware_Streaming.ipynb)

## Future Improvements

- [ ] Multi-stream processing (process multiple audio streams simultaneously)
- [ ] Adaptive chunk sizing based on speech rate
- [ ] Confidence scores for transcriptions
- [ ] Speaker diarization
- [ ] Custom language model integration
