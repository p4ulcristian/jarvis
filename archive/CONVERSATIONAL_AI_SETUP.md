# Conversational AI Setup Guide

Complete guide to setting up natural, human-like conversations with JARVIS.

This system allows JARVIS to have natural conversations with you, even while:
- Movies are playing
- Music is playing
- Other people are talking
- Background noise is present

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  CONVERSATIONAL AI PIPELINE                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Microphone Input ──┬──> [Acoustic Echo                     │
│                     │     Cancellation] ────┐               │
│  System Audio ──────┘     (removes movies,  │               │
│  (movies, music, TTS)      music, TTS)      │               │
│                                              ↓               │
│                                         [Clean Audio]        │
│                                              ↓               │
│                                    [Wake Word Gatekeeper]    │
│                                     (only after "Jarvis")    │
│                                              ↓               │
│                                    [Speaker Recognition]     │
│                                     (only YOUR voice)        │
│                                              ↓               │
│                                       [Transcription]        │
│                                              ↓               │
│                                        [Qwen Agent]          │
│                                              ↓               │
│                                      [TTS Response]          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Features

### 1. Acoustic Echo Cancellation (AEC)
- Removes ALL system audio from microphone input
- Works with movies, music, games, notifications
- Uses system audio monitor as reference signal
- Based on Speex DSP or WebRTC AEC

### 2. Speaker Recognition
- Learns YOUR voice specifically
- Rejects other voices (movies, TV, other people)
- Based on deep learning voice embeddings (resemblyzer)
- ~99% accuracy after proper enrollment

### 3. Wake Word Gating
- Never transcribes without wake word ("Jarvis") first
- Prevents false activations from background audio
- Conversation mode stays active for follow-up questions
- Automatic timeout after inactivity

### 4. Natural Conversation Flow
```
You: "Jarvis"
Assistant: *ding* "Yes?"

You: "What's the weather?"
[auto-detected pause → sends to AI]