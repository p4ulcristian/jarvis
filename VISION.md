# JARVIS: The Vision

## What if your AI assistant actually knew what you were talking about?

Current voice assistants are functionally deaf. They wake up when you say their name, process your command, then go back to sleep. They have no memory of the conversation you just had, the meeting that just happened, or the brainstorming session with your friend. Every interaction starts from zero context.

JARVIS is different.

## Always Listening, Selectively Engaging

JARVIS continuously transcribes everything said in its presence. Not to be creepy, but to be **useful**. Because real intelligence requires context.

### The Core Behavior

**When you're alone:**
- You can have natural back-and-forth conversations
- JARVIS responds when addressed
- Full conversational context is maintained

**When friends are over:**
- JARVIS logs the conversation silently
- Stays quiet unless you say "Jarvis"
- Can answer questions about what was said: *"Jarvis, what was that restaurant Mike mentioned?"*

**In meetings:**
- Full automatic transcription
- Queryable afterwards: *"Jarvis, summarize the action items"*
- No need to take notes manually

## Why This Matters

Traditional assistants force you to change how you communicate. You have to remember wake words, speak in commands, and repeat context every time.

JARVIS adapts to you. It listens like a human assistant would - present, aware, but respectful. It knows when you're talking to it versus just having a conversation.

## The Technical Approach

This isn't just duct-taped APIs. It's a carefully designed system:

1. **Continuous ASR** (NeMo Parakeet-TDT) - Gap-free transcription with streaming architecture
2. **AI Detection** - Distinguishes direct address from ambient conversation
3. **Context Management** - Maintains conversation history with rolling buffer
4. **LLM Integration** - Generates intelligent responses with full contextual awareness
5. **Natural Speech** - Responds via high-quality TTS (OpenAI)

## Current State vs. Vision

**What works now:**
- Continuous speech logging with no gaps
- Push-to-talk transcription and auto-typing
- AI detection for direct address
- Conversation improvement/cleanup
- Word boosting for better recognition

**Where we're going:**
- Wake word detection ("Hey Jarvis")
- Full conversational AI integration
- Proactive assistance and suggestions
- Multi-room audio tracking
- Privacy-preserving local LLM option
- Voice cloning for truly personalized responses

## Why "JARVIS"?

Because Tony Stark had it right. An assistant shouldn't be a command interface - it should be a conversational partner that understands context, anticipates needs, and seamlessly integrates into your environment.

This is the assistant that should exist in 2025. One that actually listens.
