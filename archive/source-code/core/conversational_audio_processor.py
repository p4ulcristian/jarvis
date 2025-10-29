#!/usr/bin/env python3
"""
Conversational Audio Processor
Complete audio processing pipeline for natural conversations
Integrates: AEC, Speaker Recognition, Wake Word Gating, VAD
"""
import logging
import numpy as np
from typing import Optional, Callable
from dataclasses import dataclass

from .system_audio import SystemAudioCapture
from .aec import AdaptiveAEC, AECConfig
from .speaker_recognition import SpeakerRecognition
from .wake_word_gatekeeper import WakeWordGatekeeper, GatekeeperConfig, ConversationState

logger = logging.getLogger(__name__)


@dataclass
class ProcessedAudio:
    """Result of audio processing"""
    audio: Optional[np.ndarray]  # Cleaned audio (None if rejected)
    should_transcribe: bool  # Whether to transcribe this audio
    is_user_voice: bool  # Whether this is the user's voice
    voice_similarity: float  # Speaker similarity score (0-1)
    gatekeeper_reason: str  # Reason for accept/reject
    conversation_state: ConversationState  # Current state


class ConversationalAudioProcessor:
    """
    Complete audio processing pipeline

    Pipeline stages:
    1. System Audio Capture (mic + system audio)
    2. Acoustic Echo Cancellation (remove speaker output from mic)
    3. Wake Word Gating (only process if wake word detected or in conversation)
    4. Speaker Recognition (verify it's the user's voice)
    5. Output clean audio for transcription

    This enables natural conversation even with:
    - Movies playing
    - Music playing
    - Multiple people talking
    - Background noise
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 1600,
        enable_aec: bool = True,
        enable_speaker_recognition: bool = True,
        speaker_profile_path: str = "data/user_voice_profile.pkl",
        speaker_similarity_threshold: float = 0.65,
        wake_word_timeout: float = 10.0,
        conversation_timeout: float = 15.0
    ):
        """
        Initialize conversational audio processor

        Args:
            sample_rate: Audio sample rate (16kHz recommended)
            chunk_size: Samples per chunk
            enable_aec: Enable echo cancellation
            enable_speaker_recognition: Enable voice identification
            speaker_profile_path: Path to speaker profile
            speaker_similarity_threshold: Min similarity for user voice (0-1)
            wake_word_timeout: Timeout after wake word (seconds)
            conversation_timeout: Conversation inactivity timeout (seconds)
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

        logger.info("Initializing Conversational Audio Processor")

        # Try to use SystemAudioCapture for dual-stream (mic + system audio)
        self.using_dual_stream = False
        try:
            if enable_aec:
                self.audio_capture = SystemAudioCapture(
                    sample_rate=sample_rate,
                    chunk_size=chunk_size,
                    channels=1
                )
                self.using_dual_stream = True
                logger.info("Using SystemAudioCapture for dual-stream AEC")
            else:
                # Fallback to single stream
                from core.audio import AudioCapture
                from core.config import Config
                config = Config()
                config.sample_rate = sample_rate
                config.chunk_size = chunk_size
                self.audio_capture = AudioCapture(config)
                logger.info("Using single-stream AudioCapture (AEC disabled)")
        except Exception as e:
            logger.error(f"Failed to initialize SystemAudioCapture: {e}")
            logger.warning("Falling back to single-stream mode")
            from core.audio import AudioCapture
            from core.config import Config
            config = Config()
            config.sample_rate = sample_rate
            config.chunk_size = chunk_size
            self.audio_capture = AudioCapture(config)
            enable_aec = False
            self.using_dual_stream = False

        # Acoustic Echo Cancellation
        if enable_aec:
            aec_config = AECConfig(
                sample_rate=sample_rate,
                frame_size=160,  # 10ms
                filter_length=1600,  # 100ms
                enabled=True
            )
            self.aec = AdaptiveAEC(aec_config)
            logger.info("AEC enabled")
        else:
            self.aec = None
            logger.warning("AEC disabled")

        # Speaker Recognition
        if enable_speaker_recognition:
            self.speaker_recognition = SpeakerRecognition(
                profile_path=speaker_profile_path,
                similarity_threshold=speaker_similarity_threshold,
                enabled=True
            )
            if self.speaker_recognition.is_enrolled():
                logger.info("Speaker recognition enabled (user enrolled)")
            else:
                logger.warning("Speaker recognition enabled but no user profile found")
                logger.warning("Run enrollment script to create voice profile")
        else:
            self.speaker_recognition = None
            logger.warning("Speaker recognition disabled")

        # Wake Word Gatekeeper (disabled - allow continuous transcription)
        gatekeeper_config = GatekeeperConfig(
            wake_word_timeout=wake_word_timeout,
            conversation_timeout=conversation_timeout
        )
        self.gatekeeper = WakeWordGatekeeper(gatekeeper_config)
        # Start in conversation mode so transcription works immediately
        self.gatekeeper.on_wake_word_detected()
        logger.info("Wake word gatekeeper initialized (continuous mode)")

        # State
        self.is_running = False
        self.frames_processed = 0
        self.frames_rejected = 0

    def start(self) -> bool:
        """
        Start audio processing

        Returns:
            True if started successfully
        """
        logger.info("Starting conversational audio processor")

        # Start audio capture (method depends on capture type)
        try:
            if self.using_dual_stream:
                if not self.audio_capture.start_capture():
                    logger.error("Failed to start dual-stream capture")
                    return False
            else:
                if not self.audio_capture.start_stream():
                    logger.error("Failed to start audio stream")
                    return False

            self.is_running = True
            logger.info(f"Audio processor started (dual_stream={self.using_dual_stream})")
            return True
        except Exception as e:
            logger.error(f"Failed to start audio processor: {e}", exc_info=True)
            return False

    def stop(self) -> None:
        """Stop audio processing"""
        logger.info("Stopping audio processor")
        try:
            if self.using_dual_stream:
                self.audio_capture.stop_capture()
            else:
                self.audio_capture.stop_stream()
        except Exception as e:
            logger.error(f"Error stopping audio capture: {e}")
        self.is_running = False

    def process_frame(self) -> ProcessedAudio:
        """
        Process one audio frame through the complete pipeline

        Returns:
            ProcessedAudio with results
        """
        self.frames_processed += 1

        # Stage 1: Capture audio (single or dual stream)
        mic_audio = None
        system_audio = None

        try:
            if self.using_dual_stream:
                # Dual stream mode - get both mic and system audio
                mic_audio, system_audio = self.audio_capture.get_frames(timeout=1.0)
            else:
                # Single stream mode
                mic_audio = self.audio_capture.get_chunk(timeout=1.0)

            if mic_audio is None:
                return ProcessedAudio(
                    audio=None,
                    should_transcribe=False,
                    is_user_voice=False,
                    voice_similarity=0.0,
                    gatekeeper_reason="no_audio",
                    conversation_state=self.gatekeeper.get_state()
                )

        except Exception as e:
            logger.error(f"Error capturing audio: {e}")
            return ProcessedAudio(
                audio=None,
                should_transcribe=False,
                is_user_voice=False,
                voice_similarity=0.0,
                gatekeeper_reason="capture_error",
                conversation_state=self.gatekeeper.get_state()
            )

        # Stage 2: Acoustic Echo Cancellation
        clean_audio = mic_audio
        if self.aec and self.aec.enabled and system_audio is not None:
            try:
                # Ensure buffer sizes match before AEC
                if len(mic_audio) == len(system_audio):
                    clean_audio = self.aec.process(mic_audio, system_audio)
                    logger.debug(f"AEC processed: {len(clean_audio)} samples")
                else:
                    logger.warning(f"Buffer size mismatch: mic={len(mic_audio)}, sys={len(system_audio)}")
                    clean_audio = mic_audio  # Skip AEC if sizes don't match
            except Exception as e:
                logger.error(f"AEC processing error: {e}")
                clean_audio = mic_audio  # Fallback to unprocessed audio

        # Stage 3: Wake Word Gating (disabled for continuous transcription)
        # Always allow transcription
        should_transcribe = True
        gatekeeper_reason = "continuous_mode"

        # Stage 4: Speaker Recognition (disabled for continuous transcription)
        # Only check if explicitly enabled AND enrolled
        is_user_voice = True
        voice_similarity = 1.0

        # Skip speaker recognition for now - allows all voices
        # TODO: Re-enable when user wants to filter by voice

        # All checks passed - return clean audio
        return ProcessedAudio(
            audio=clean_audio,
            should_transcribe=True,
            is_user_voice=is_user_voice,
            voice_similarity=voice_similarity,
            gatekeeper_reason=gatekeeper_reason,
            conversation_state=self.gatekeeper.get_state()
        )

    def on_wake_word_detected(self) -> None:
        """
        Called when wake word is detected in transcription

        Activates conversation mode
        """
        logger.info("Wake word detected - activating conversation")
        self.gatekeeper.on_wake_word_detected()

    def on_transcription_start(self) -> None:
        """Called when starting to transcribe user speech"""
        self.gatekeeper.start_listening()

    def on_transcription_complete(self) -> None:
        """Called when transcription is complete"""
        self.gatekeeper.start_processing()

    def on_response_start(self) -> None:
        """Called when TTS starts playing"""
        self.gatekeeper.start_responding()

    def on_response_complete(self) -> None:
        """Called when TTS finishes"""
        self.gatekeeper.finish_response()

    def end_conversation(self, reason: str = "user_request") -> None:
        """
        End conversation and return to IDLE

        Args:
            reason: Reason for ending
        """
        self.gatekeeper.end_conversation(reason)

    def set_aec_enabled(self, enabled: bool) -> bool:
        """
        Enable or disable AEC at runtime

        Args:
            enabled: True to enable, False to disable

        Returns:
            True if successful, False if AEC is not available
        """
        if self.aec is None:
            logger.warning("Cannot toggle AEC - not initialized")
            return False

        self.aec.enabled = enabled
        logger.info(f"AEC {'enabled' if enabled else 'disabled'}")
        return True

    def get_conversation_state(self) -> ConversationState:
        """Get current conversation state"""
        return self.gatekeeper.get_state()

    def is_in_conversation(self) -> bool:
        """Check if in active conversation"""
        return self.gatekeeper.is_in_conversation()

    def get_stats(self) -> dict:
        """Get processing statistics"""
        gatekeeper_stats = self.gatekeeper.get_stats()

        return {
            'frames_processed': self.frames_processed,
            'frames_rejected': self.frames_rejected,
            'rejection_rate': (
                self.frames_rejected / self.frames_processed
                if self.frames_processed > 0 else 0.0
            ),
            'aec_enabled': self.aec is not None and self.aec.enabled,
            'speaker_recognition_enabled': (
                self.speaker_recognition is not None and
                self.speaker_recognition.is_enrolled()
            ),
            **gatekeeper_stats
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=== Conversational Audio Processor Test ===\n")

    # Create processor
    processor = ConversationalAudioProcessor(
        sample_rate=16000,
        chunk_size=1600,
        enable_aec=True,
        enable_speaker_recognition=False,  # Disable for test (no profile)
        wake_word_timeout=10.0,
        conversation_timeout=15.0
    )

    # List audio devices
    print("Available audio devices:")
    processor.audio_capture.list_devices()
    print()

    # Start processing
    print("Starting audio processor...")
    if not processor.start():
        print("✗ Failed to start")
        exit(1)

    print("✓ Audio processor started\n")

    # Simulate conversation flow
    print("Simulating conversation flow:")
    print()

    # Test 1: Try to process without wake word
    print("1. Processing without wake word...")
    result = processor.process_frame()
    print(f"   Should transcribe: {result.should_transcribe}")
    print(f"   Reason: {result.gatekeeper_reason}")
    print(f"   State: {result.conversation_state}")
    print()

    # Test 2: Wake word detected
    print("2. Wake word detected...")
    processor.on_wake_word_detected()
    print(f"   State: {processor.get_conversation_state()}")
    print()

    # Test 3: Process after wake word
    print("3. Processing after wake word...")
    result = processor.process_frame()
    print(f"   Should transcribe: {result.should_transcribe}")
    print(f"   Reason: {result.gatekeeper_reason}")
    print()

    # Test 4: Full conversation flow
    print("4. Full conversation flow...")
    processor.on_transcription_start()
    print(f"   State: {processor.get_conversation_state()}")

    processor.on_transcription_complete()
    print(f"   State: {processor.get_conversation_state()}")

    processor.on_response_start()
    print(f"   State: {processor.get_conversation_state()}")

    processor.on_response_complete()
    print(f"   State: {processor.get_conversation_state()}")
    print()

    # Test 5: Follow-up (no wake word needed)
    print("5. Follow-up question...")
    result = processor.process_frame()
    print(f"   Should transcribe: {result.should_transcribe}")
    print(f"   Reason: {result.gatekeeper_reason}")
    print()

    # Stats
    print("Processing statistics:")
    stats = processor.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()

    # Stop
    processor.stop()
    print("✓ Test complete")
