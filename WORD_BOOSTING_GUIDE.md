# Word Boosting Guide - NeMo GPU-PB

**Date**: 2025-10-19

## What is Word Boosting?

Word boosting (also called **context-biasing** or **phrase-boosting**) is a feature that makes your ASR model more likely to recognize specific words or phrases. This is especially useful for:

- **Domain-specific terminology** (technical terms, product names)
- **Names** (people, places, companies)
- **Commands** (wake words, action triggers)
- **Rare words** that the model might miss

## How It Works

### GPU-PB Framework (GPU-accelerated Phrase-Boosting)

Your JARVIS implementation uses **GPU-PB**, NVIDIA's latest context-biasing framework (introduced in 2025). Here's how it works:

1. **Phrase-Boosting Tree**: Creates a GPU-accelerated tree structure of your key phrases
2. **Modified Scoring**: Adjusts decoder scores to favor your boosted words
3. **Real-time Processing**: Adds only 2-5% overhead to transcription time
4. **Scalable**: Supports up to 20,000 phrases with minimal performance impact

### Technical Details

When Canary decodes audio, it:
1. Generates candidate transcriptions (hypotheses)
2. Scores each hypothesis based on acoustic features
3. **GPU-PB boosts scores** for hypotheses containing your key phrases
4. Returns the highest-scoring result

**Result**: Your boosted words are more likely to be recognized correctly!

## Performance

According to NVIDIA research (2025):
- **8-10% improvement** in key phrase recognition (F-score) with greedy decoding
- **17-23% improvement** with beam search decoding
- **2-5% RTFx overhead** (minimal impact on speed)
- **Robust** up to 20K phrases in boost list

## Your Current Configuration

### Code Implementation (transcription.py:594-619)

```python
def _configure_word_boosting(model, boost_file: Path) -> None:
    """Configure GPU-PB word boosting"""
    # Load phrases from file
    with open(boost_file, 'r') as f:
        key_phrases = [line.strip() for line in f if line.strip()]

    # Configure decoding strategy
    decoding_cfg = OmegaConf.create({
        'strategy': 'greedy_batch',      # Fast batch decoding
        'context_score': 3.0,             # Boosting strength
        'key_phrases_list': key_phrases  # Your boosted words
    })

    model.change_decoding_strategy(decoding_cfg)
```

### Current Boost File (source-code/config/boost_words.txt)

```
Jarvis
```

**Status**: ✅ Active (if file exists and has content)

### Configuration Parameters

**1. `strategy: 'greedy_batch'`**
- Uses fast batch greedy decoding
- Significantly faster than regular greedy
- Nearly identical accuracy to greedy

**2. `context_score: 3.0`**
- **Per-token weight** for context biasing
- Range: 1.0 - 10.0 (typically 3.0 - 5.0)
- **Higher = stronger boosting** (more aggressive)
- **3.0** is a balanced default
- Can test multiple values: `[3.0, 4.0, 5.0]`

**3. `key_phrases_list`**
- List of words/phrases to boost
- One phrase per line in boost_words.txt
- Case-sensitive (usually)
- Can include multi-word phrases

## How to Add More Boosted Words

### Method 1: Edit the File Directly

```bash
# Edit boost words file
nano /home/paul/Work/jarvis/source-code/config/boost_words.txt
```

Add one word/phrase per line:
```
Jarvis
Claude Code
Python
NVIDIA
NeMo
FastConformer
Canary
transcription
microphone
```

### Method 2: Programmatically

```python
# Add words to boost file
boost_words = [
    'Jarvis',
    'Claude Code',
    'Python',
    'NVIDIA',
    'NeMo',
    # Add your domain-specific terms
]

with open('source-code/config/boost_words.txt', 'w') as f:
    f.write('\n'.join(boost_words) + '\n')
```

## What Words Should You Boost?

### Good Candidates ✅

1. **Wake words**: `Jarvis`, `Hey Jarvis`, `Computer`
2. **Technical terms**: `Python`, `NVIDIA`, `Claude`, `NeMo`
3. **Your project names**: `JARVIS`, `Claude Code`
4. **Rare words**: Domain-specific terminology
5. **Commands**: `stop`, `pause`, `continue`, `cancel`
6. **Names**: People, places, products you frequently mention

### Poor Candidates ❌

1. **Common words**: `the`, `and`, `is`, `it` (already recognized well)
2. **Too many words**: Keep list focused (quality over quantity)
3. **Similar-sounding words**: Can cause confusion
4. **Filler words**: `um`, `uh`, `like` (you want to filter these)

### Multi-word Phrases

You can boost entire phrases:
```
Claude Code
push to talk
speech to text
natural language processing
```

## Tuning Context Score

The `context_score` parameter controls boosting strength:

| Score | Strength | When to Use |
|-------|----------|-------------|
| 1.0-2.0 | Subtle | Slight preference for words |
| 3.0 | **Balanced** | Default, works well |
| 4.0-5.0 | Aggressive | Important domain terms |
| 6.0-10.0 | Very aggressive | Only for critical words (may reduce accuracy) |

### Testing Different Scores

Edit `transcription.py:610`:
```python
decoding_cfg = OmegaConf.create({
    'strategy': 'greedy_batch',
    'context_score': 4.0,  # Try different values
    'key_phrases_list': key_phrases
})
```

Or test multiple values:
```python
'context_score': [3.0, 4.0, 5.0]  # NeMo will test all
```

## Verifying Word Boosting is Active

### Check Logs on Startup

When JARVIS starts, look for:
```
Word boost enabled: X phrases
GPU-PB word boosting configured
```

### Test Recognition

1. **Without boosting**: Temporarily rename boost_words.txt
2. **Speak a rare term** like "Canary-1B" or "NeMo"
3. **Check accuracy** - was it recognized?
4. **Enable boosting**: Restore boost_words.txt
5. **Test again** - recognition should improve!

### Debug Mode

```bash
DEBUG_MODE=true ./jarvis.sh
```

Look for:
- `Word boost enabled: N phrases` during model loading
- Better recognition of your boosted words

## Example Use Cases

### 1. Software Development Commands

```
git commit
git push
git pull
pull request
code review
merge conflict
Docker
Kubernetes
pytest
```

### 2. Voice Assistant Commands

```
Jarvis
Hey Jarvis
wake up
stop listening
cancel
repeat
louder
quieter
```

### 3. Technical Writing/Documentation

```
NVIDIA
NeMo
Claude Code
Anthropic
API
endpoint
authentication
webhook
```

## Limitations

1. **Not a replacement for fine-tuning**: Won't fix fundamental model issues
2. **Balancing act**: Too much boosting can reduce overall accuracy
3. **Case sensitivity**: May need to test both cases
4. **Phrase complexity**: Very long phrases may not work well

## Current Status in Your Setup

**File location**: `/home/paul/Work/jarvis/source-code/config/boost_words.txt`

**Current content**:
```
Jarvis
```

**Configuration**:
- Strategy: `greedy_batch` (fast)
- Context score: `3.0` (balanced)
- Phrases: 1 word

**Is it active?**: ✅ Yes (assuming file exists and has content)

## Recommended Next Steps

### 1. Add More Relevant Words

Think about:
- Technical terms you use frequently
- Commands you want JARVIS to recognize
- Names (people, projects, companies)
- Domain-specific vocabulary

### 2. Test Recognition

Before adding 100 words:
1. Start with 5-10 most important terms
2. Test transcription accuracy
3. Adjust context_score if needed
4. Gradually add more words

### 3. Monitor Performance

Watch for:
- Recognition improvement on boosted words
- Any degradation in overall accuracy
- Latency changes (should be minimal)

## Advanced: Custom Scoring Per Word

If you need different boost levels for different words, you'll need to use NeMo's advanced context-biasing API. Current implementation uses same score for all words (simpler, works well).

## Resources

- **NeMo Word Boosting Docs**: https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/asr/asr_customization/word_boosting.html
- **TurboBias Paper** (2025): https://arxiv.org/html/2508.07014
- **NeMo Context Biasing Tutorial**: `NeMo/tutorials/asr/ASR_Context_Biasing.ipynb`

---

**Summary**: Word boosting is active and configured! Currently boosting "Jarvis" with a context score of 3.0. Add more domain-specific terms to improve recognition of technical vocabulary and commands.
