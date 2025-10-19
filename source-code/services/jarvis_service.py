#!/usr/bin/env python3
"""
JARVIS Service - Core orchestration layer
Coordinates audio capture, transcription, and keyboard automation
"""
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

# Deferred imports for fast startup
from core import Config

logger = logging.getLogger(__name__)


class JarvisService:
    """
    Main JARVIS service orchestrator

    Responsibilities:
    - Coordinate audio capture, transcription, and typing
    - Manage component lifecycle
    - Handle main processing loop
    - Provide clean shutdown
    """

    def __init__(self, config: Config, data_bridge: Optional['DataBridge'] = None):
        """
        Initialize JARVIS service

        Args:
            config: Configuration object
            data_bridge: Optional DataBridge for UI communication
        """
        # Defer heavy imports
        from core import setup_logging, RollingBuffer
        from ui.data_bridge import UILogHandler

        self.config = config
        self.data_bridge = data_bridge
        self.logger = setup_logging(debug=config.debug_mode, name='jarvis')

        # Add UI log handler if data bridge provided
        if self.data_bridge:
            ui_handler = UILogHandler(self.data_bridge)
            self.logger.addHandler(ui_handler)

        # Core components (lazy initialized)
        self.model = None
        self.frame_asr = None
        self.audio_capture = None
        self.transcription_buffer = RollingBuffer(max_duration=config.buffer_duration)
        self.keyboard_typer = None

        # State management
        self.shutdown = False
        self.last_trigger_time = 0
        self.last_detection_time = 0
        self.is_running = False

        self.logger.info("JarvisService initialized")

    def load_model(self) -> bool:
        """
        Load NeMo ASR model

        Returns:
            True if successful, False otherwise
        """
        from core.transcription import load_nemo_model, FrameASR

        if not self.config.enable_model:
            self.logger.warning("Model loading disabled by config")
            if self.data_bridge:
                self.data_bridge.update_state(model_loaded=False)
            return True

        self.logger.info("Loading AI model (this may take 10-60 seconds)...")
        if self.data_bridge:
            self.data_bridge.send_log("INFO", "Loading NVIDIA Canary-1B Flash model (883M params)...")

        self.model = load_nemo_model(self.config)
        if self.model is None:
            if self.data_bridge:
                self.data_bridge.update_state(model_loaded=False, error="Failed to load model")
            return False

        # Initialize frame ASR
        if self.config.enable_transcription:
            self.frame_asr = FrameASR(self.model, self.config)
            self.logger.info("Frame ASR initialized")

        if self.data_bridge:
            self.data_bridge.update_state(model_loaded=True)
            self.data_bridge.send_log("INFO", "Model loaded successfully!")

        return True

    def initialize_audio(self) -> bool:
        """
        Initialize audio capture

        Returns:
            True if successful, False otherwise
        """
        from core import AudioCapture

        if not self.config.enable_microphone:
            self.logger.warning("Microphone disabled by config")
            if self.data_bridge:
                self.data_bridge.update_state(mic_active=False)
            return True

        try:
            self.audio_capture = AudioCapture(self.config)
            self.logger.info("Audio capture initialized")
            if self.data_bridge:
                self.data_bridge.update_state(mic_active=True)
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize audio: {e}")
            if self.data_bridge:
                self.data_bridge.update_state(mic_active=False, error=f"Audio init failed: {e}")
            return False

    def initialize_keyboard_typer(self) -> bool:
        """
        Initialize keyboard typer

        Returns:
            True if successful, False otherwise
        """
        from services.keyboard_typer import get_typer

        try:
            self.keyboard_typer = get_typer(typing_delay=self.config.typing_delay)

            # Pre-initialize to check permissions
            if self.keyboard_typer.initialize():
                self.logger.info("Keyboard typer initialized successfully")
                return True
            else:
                self.logger.warning("Keyboard typer initialization failed - Type Mode will not work")
                if self.data_bridge:
                    self.data_bridge.send_log("WARNING", "Keyboard typer failed - check permissions")
                return False
        except Exception as e:
            self.logger.warning(f"Could not initialize keyboard typer: {e}")
            return False

    def log_conversation(self, text: str) -> None:
        """
        Log conversation to file

        Args:
            text: Text to log
        """
        try:
            with open(self.config.log_file, 'a') as f:
                f.write(text + ' ')
        except Exception as e:
            self.logger.error(f"Failed to log conversation: {e}")

    def run_main_loop(self) -> None:
        """
        Main processing loop: continuous speech capture and transcription

        This is the core loop that:
        1. Captures audio chunks
        2. Detects speech/silence
        3. Transcribes speech
        4. Handles Type Mode (PTT)
        """
        import numpy as np
        from datetime import datetime
        from core import AudioCapture

        if not self.config.enable_microphone:
            self.logger.info("Microphone disabled, nothing to do")
            return

        if not self.config.enable_model:
            self.logger.info("Microphone test mode (model disabled)")
        else:
            self.logger.info("Starting real-time continuous transcription...")

        # Start continuous streaming (zero-gap audio capture)
        if not self.audio_capture.start_stream():
            self.logger.error("Failed to start audio stream")
            return

        self.is_running = True
        iteration = 0
        last_ptt_state = False
        ptt_transcriptions = []

        try:
            while not self.shutdown:
                try:
                    iteration += 1

                    # Check PTT state for typing control
                    ptt_active = False
                    if self.data_bridge:
                        state = self.data_bridge.get_state()
                        ptt_active = state.ptt_active

                    # Detect PTT state changes
                    ptt_pressed = not last_ptt_state and ptt_active
                    ptt_released = last_ptt_state and not ptt_active
                    last_ptt_state = ptt_active

                    # When PTT is pressed, clear the transcription buffer
                    if ptt_pressed:
                        ptt_transcriptions = []
                        if self.data_bridge:
                            self.data_bridge.send_log("INFO", "Type Mode: Hold to record, release to type")

                    # When PTT is released, type all transcriptions from this session
                    if ptt_released and ptt_transcriptions:
                        combined_text = " ".join(ptt_transcriptions)
                        if self.keyboard_typer:
                            try:
                                self.keyboard_typer.paste_text(combined_text)
                                self.logger.debug(f"Auto-typed: {combined_text}")
                                if self.data_bridge:
                                    self.data_bridge.send_log("INFO", f"Typed: {combined_text[:50]}...")
                            except Exception as e:
                                self.logger.error(f"Failed to auto-type text: {e}", exc_info=True)
                        ptt_transcriptions = []

                    # ALWAYS capture and process audio (continuous transcription)
                    # get_chunk() retrieves from the continuous stream queue
                    audio_chunk = self.audio_capture.get_chunk(timeout=1.0)
                    if audio_chunk is None:
                        # No audio available or timeout - continue loop
                        continue

                    # Calculate and send audio level for UI (every chunk)
                    if self.data_bridge:
                        max_amp, avg_amp = AudioCapture.calculate_energy(audio_chunk)
                        self.data_bridge.send_audio_level(max_amp, avg_amp)

                    # Test mode: just show stats
                    if not self.config.enable_model or not self.config.enable_transcription:
                        has_speech = self.frame_asr.has_speech(audio_chunk, debug=False)
                        if has_speech:
                            chunk_duration = len(audio_chunk) / self.config.sample_rate
                            max_amp, _ = AudioCapture.calculate_energy(audio_chunk)
                            self.logger.info(
                                f"MIC TEST: {len(audio_chunk)} samples "
                                f"({chunk_duration:.2f}s) - max: {max_amp:.0f}"
                            )
                    else:
                        # Continuous transcription mode
                        has_speech = self.frame_asr.has_speech(audio_chunk, debug=False)

                        if has_speech:
                            # Add speech to buffer
                            self.frame_asr.add_speech_chunk(audio_chunk)
                        else:
                            # Silence detected - increment silence counter
                            self.frame_asr.increment_silence()

                        # Check if we should transcribe (respects min buffer, silence counter, and max buffer)
                        if self.frame_asr.should_transcribe():
                            buffered_audio = self.frame_asr.get_buffered_audio()

                            if len(buffered_audio) > 0:
                                if self.data_bridge:
                                    self.data_bridge.update_state(processing=True)

                                # Transcribe (with retry logic built-in)
                                text = self.frame_asr.transcribe_chunk(buffered_audio)

                                if self.data_bridge:
                                    self.data_bridge.update_state(processing=False)

                                # Process transcription
                                if text:
                                    self.log_conversation(text)
                                    self.transcription_buffer.add(text)

                                    # Always send to UI
                                    if self.data_bridge:
                                        self.data_bridge.send_transcription(text)

                                    # If PTT is active, buffer for typing when released
                                    if ptt_active:
                                        ptt_transcriptions.append(text)

                                    if not self.config.enable_ui:
                                        timestamp = datetime.now().strftime('%H:%M:%S')
                                        self.logger.info(f"[{timestamp}] {text}")

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    self.logger.error(f"Main loop error: {e}", exc_info=True)
                    # Continue running despite errors - error recovery will handle retries

        except KeyboardInterrupt:
            self.logger.info("Stopped by user")
        finally:
            self.is_running = False

    def start(self) -> bool:
        """
        Start JARVIS service

        Returns:
            True if started successfully, False otherwise
        """
        self.logger.info("=" * 60)
        self.logger.info("JARVIS - Speech Logger v2.0")
        self.logger.info("=" * 60)

        # Clear log files on startup
        try:
            Path(self.config.log_file).write_text('')
            Path(self.config.improved_log_file).write_text('')
        except Exception as e:
            self.logger.warning(f"Could not clear log files: {e}")

        # Initialize keyboard typer
        self.initialize_keyboard_typer()

        # Load model (slow operation)
        if not self.load_model():
            self.logger.error("Failed to load model")
            return False

        # Initialize audio
        if not self.initialize_audio():
            self.logger.error("Failed to initialize audio")
            return False

        self.logger.info("READY - Listening...")

        # Start main loop
        try:
            self.run_main_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

        return True

    def stop(self) -> None:
        """Stop JARVIS service"""
        self.shutdown = True
        self.logger.info("Stopping JARVIS service...")

    def cleanup(self) -> None:
        """Cleanup resources"""
        self.shutdown = True
        self.is_running = False
        self.logger.info("Cleaning up JARVIS resources...")

        # Stop audio stream
        if self.audio_capture:
            try:
                self.audio_capture.stop_stream()
            except Exception as e:
                self.logger.error(f"Error stopping audio stream: {e}")

        # Clean up keyboard typer
        if self.keyboard_typer:
            try:
                self.keyboard_typer.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up keyboard typer: {e}")

        self.logger.info("JARVIS cleanup complete")
