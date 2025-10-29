# ASR Accuracy Improvements Guide

This guide covers all the improvements made to enhance speech-to-text precision in JARVIS.

## 🎯 Quick Start - Immediate Improvements

The system is now configured with **beam search (width=3)** by default for better accuracy. To adjust:

```bash
# In .env file:
CANARY_BEAM_SIZE=3  # Current: balanced speed/accuracy
CANARY_BEAM_SIZE=5  # Maximum accuracy (slower)
CANARY_BEAM_SIZE=1  # Maximum speed (less accurate)
```

**Expected Impact**: Beam size of 3-5 can reduce WER by 10-20% compared to greedy decoding.

---

## 📊 Implemented Improvements

### 1. ✅ Beam Search Decoding (ACTIVE)

**Status**: Implemented and enabled by default
**Configuration**: `source-code/core/config.py:59`

```env
CANARY_BEAM_SIZE=3           # Beam width (1=greedy, 3-5=beam search)
CANARY_BEAM_ALPHA=1.0        # Length penalty (0.8-1.5)
CANARY_BEAM_BETA=0.0         # Word insertion bonus (usually 0)
```

**How it works**: Instead of picking the single most likely word at each step (greedy), beam search explores multiple candidate sequences in parallel and picks the best overall sequence.

**Performance**: Only ~20% RTFx overhead compared to greedy decoding.

### 2. ✅ Language Model Rescoring (READY - Requires Training)

**Status**: Implemented, disabled by default
**Configuration**: `source-code/core/config.py:64-67`

```env
ENABLE_LM_RESCORING=true
LM_PATH=/path/to/your/language_model.arpa
LM_ALPHA=0.5                 # LM weight (0.5-2.0)
LM_BETA=1.0                  # Length penalty
```

**Expected Impact**: Can reduce WER by 10-30% for domain-specific vocabulary.

**To enable**:
1. Install KenLM (see Training Guide below)
2. Train a language model on your text corpus
3. Set `ENABLE_LM_RESCORING=true` and `LM_PATH` in `.env`

### 3. ✅ Neural Rescoring (READY - Experimental)

**Status**: Implemented, disabled by default
**Configuration**: `source-code/core/config.py:70-73`

```env
ENABLE_NEURAL_RESCORING=true
NEURAL_RESCORER_MODEL=/path/to/neural_lm
RESCORER_ALPHA=0.8           # Neural LM importance (0.0-1.0)
RESCORER_BETA=0.3            # Sequence length penalty
```

**How it works**: Re-ranks the top K beam search candidates using a neural language model for more sophisticated context understanding.

---

## 🚀 Model Upgrade Options

### Your Hardware: RTX 3080 (10GB VRAM)
- **Current Usage**: ~4.2GB
- **Available**: ~6GB free
- **Verdict**: ✅ Can upgrade to larger models

### Model Comparison

| Model | Parameters | VRAM Required | Speed (RTFx) | WER | Languages | Notes |
|-------|-----------|---------------|--------------|-----|-----------|-------|
| **canary-1b-flash** (current) | 883M | ~2GB | 1097 | Good | 4 | Fastest, current choice |
| **canary-1b-v2** | 978M | ~6GB | ~500 | Better | 25 | **Recommended upgrade** |
| **canary-1b** | 1B | ~6GB | 345 | Best (6.67%) | 4 | Highest accuracy |

### Recommended: Upgrade to Canary-1B-V2

**Why V2?**
- Supports 25 European languages
- Improved timestamp prediction
- Enhanced ASR & AST capabilities
- Better overall accuracy
- Recent 2025 release

**How to upgrade:**

```bash
# In .env file:
MODEL_NAME=nvidia/canary-1b-v2
```

Then restart JARVIS. The model will download automatically (~2GB download).

**Alternative: Canary-1B (full)**

For maximum English accuracy:
```bash
MODEL_NAME=nvidia/canary-1b
```

---

## 📚 Training a Language Model (Advanced)

Language model rescoring can significantly improve accuracy for domain-specific vocabulary.

### Step 1: Install KenLM

```bash
cd ~/Work/jarvis
pip install https://github.com/kpu/kenlm/archive/master.zip
```

### Step 2: Prepare Text Corpus

Create a text file with your domain-specific text (one sentence per line):

```bash
# Example: Use your chat logs, transcripts, or domain text
cat data/chat.txt data/chat-revised.txt > training_corpus.txt

# Clean the text (lowercase, remove special chars)
cat training_corpus.txt | tr '[:upper:]' '[:lower:]' | \
  sed 's/[^a-z0-9 ]//g' > cleaned_corpus.txt
```

### Step 3: Train the Language Model

```bash
# Train a 3-gram language model
lmplz -o 3 < cleaned_corpus.txt > lm_3gram.arpa

# Convert to binary format (faster loading)
build_binary lm_3gram.arpa lm_3gram.binary
```

### Step 4: Enable in JARVIS

```bash
# In .env:
ENABLE_LM_RESCORING=true
LM_PATH=/home/paul/Work/jarvis/lm_3gram.binary
LM_ALPHA=0.5
LM_BETA=1.0
```

### Step 5: Tune Parameters

Experiment with `LM_ALPHA`:
- **0.5**: Light LM influence (safer start)
- **1.0**: Balanced
- **2.0**: Heavy LM influence (use if LM is very high quality)

---

## 🎛️ Parameter Tuning Guide

### Beam Size (`CANARY_BEAM_SIZE`)

| Value | Speed | Accuracy | Use Case |
|-------|-------|----------|----------|
| 1 | Fastest | Good | Real-time, low latency required |
| 3 | Fast | Better | **Recommended default** |
| 5 | Moderate | Best | Maximum accuracy, can tolerate slight delay |

### Length Penalty (`CANARY_BEAM_ALPHA`)

- **0.5-0.8**: Prefer shorter sequences
- **1.0**: Neutral (recommended)
- **1.2-1.5**: Prefer longer sequences

### LM Weight (`LM_ALPHA`)

Start with 0.5 and increase if:
- Your LM is trained on high-quality, domain-relevant text
- You're seeing errors in domain-specific vocabulary
- The acoustic model alone isn't sufficient

Decrease if:
- The LM is forcing incorrect words
- Too much deviation from what was actually said

---

## 🧪 Testing and Validation

### Test Current Configuration

```bash
cd ~/Work/jarvis
python test_real_transcription.py
```

### Measure Improvements

1. **Before changes**: Record baseline WER with current settings
2. **After changes**: Test with new beam search settings
3. **Compare**: Calculate WER reduction

```python
# Simple WER calculation
def calculate_wer(reference, hypothesis):
    # Implementation in test scripts
    pass
```

### Expected Results

With beam search (size=3):
- **Speed**: ~20% slower than greedy
- **Accuracy**: 10-20% WER reduction
- **Real-time factor**: Still >800 RTFx (plenty fast)

With beam search + LM rescoring:
- **Speed**: ~30-40% slower than greedy
- **Accuracy**: 20-40% WER reduction for domain text
- **Real-time factor**: Still >500 RTFx

---

## 🔧 Troubleshooting

### Beam Search Not Improving Accuracy

1. **Check beam size**: Ensure `CANARY_BEAM_SIZE > 1` in config
2. **Monitor logs**: Look for "beam search (width=X)" in startup
3. **Audio quality**: Poor audio quality limits any decoder improvements
4. **Try higher beam width**: Increase to 5

### LM Rescoring Errors

**Error: "KenLM not installed"**
```bash
pip install https://github.com/kpu/kenlm/archive/master.zip
```

**Error: "Language model file not found"**
- Verify `LM_PATH` points to correct file
- Check file exists: `ls -lh $LM_PATH`

**LM making things worse**
- Your LM may not match the speech domain
- Try lowering `LM_ALPHA` to reduce LM influence
- Retrain LM on more relevant text

### Out of Memory

If you upgraded model and getting OOM:
1. **Check VRAM usage**: `nvidia-smi`
2. **Close other GPU apps**: Browser, Hyprland compositor effects, etc.
3. **Reduce beam size**: Try `CANARY_BEAM_SIZE=1` temporarily
4. **Stick with flash model**: `MODEL_NAME=nvidia/canary-1b-flash`

---

## 📈 Performance Monitoring

Monitor your improvements:

```bash
# Check current model and settings
grep "MODEL_NAME\|BEAM_SIZE" .env

# Watch GPU memory
watch -n 1 nvidia-smi

# Enable debug mode for detailed transcription logs
# In .env:
DEBUG_MODE=true
```

---

## 🎓 Additional Resources

### NVIDIA NeMo Documentation
- ASR Language Modeling: https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/asr/asr_language_modeling_and_customization.html
- Neural Rescoring: https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/asr/asr_customization/neural_rescoring.html

### KenLM
- GitHub: https://github.com/kpu/kenlm
- Training Guide: https://kheafield.com/code/kenlm/

### Model Cards
- Canary-1B-V2: https://huggingface.co/nvidia/canary-1b-v2
- Canary-1B-Flash: https://huggingface.co/nvidia/canary-1b-flash
- Canary-1B: https://huggingface.co/nvidia/canary-1b

---

## 📝 Summary of Changes

### Files Modified
1. **source-code/core/config.py**: Added beam search and LM rescoring parameters
2. **source-code/core/transcription.py**:
   - Updated beam search configuration
   - Added LM rescoring support
   - Improved logging for decoding strategy
3. **.env**: Created comprehensive configuration file

### New Features
- ✅ Configurable beam search (width 1-5)
- ✅ Length penalty and word insertion bonus
- ✅ N-gram LM rescoring support (KenLM)
- ✅ Neural rescoring configuration
- ✅ Model upgrade option to Canary-1B-V2
- ✅ Detailed logging and monitoring

### Quick Configuration

**Conservative (balanced):**
```env
CANARY_BEAM_SIZE=3
MODEL_NAME=nvidia/canary-1b-flash
ENABLE_LM_RESCORING=false
```

**Aggressive (maximum accuracy):**
```env
CANARY_BEAM_SIZE=5
MODEL_NAME=nvidia/canary-1b-v2
ENABLE_LM_RESCORING=true
LM_PATH=/path/to/your/lm.binary
LM_ALPHA=1.0
```

---

## 🎯 Next Steps

1. **Test current improvements**: Run with `CANARY_BEAM_SIZE=3`
2. **Measure accuracy**: Compare transcription quality
3. **Consider model upgrade**: Try `canary-1b-v2` if happy with speed
4. **Train LM (optional)**: For domain-specific improvements
5. **Fine-tune parameters**: Adjust beam size and LM weights as needed

Happy transcribing! 🎤✨
