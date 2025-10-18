#!/home/paul/Work/jarvis/venv/bin/python
"""
JARVIS - Voice-to-Text System with Streaming NeMo ASR
Production-ready refactored version with modular architecture
"""
import os
import sys
import signal
from pathlib import Path
from datetime import datetime
import numpy as np
from typing import Optional

# Import core modules
from core import (
    Config,
    setup_logging,
    AudioCapture,
    FrameASR,
    RollingBuffer,
    TranscriptionBuffer
)
from core.transcription import load_nemo_model

# Import UI modules
from ui import DataBridge, JarvisUI
from ui.data_bridge import UILogHandler


class Jarvis:
    """Main JARVIS application"""

    def __init__(self, config: Config, data_bridge: Optional[DataBridge] = None):
        """
        Initialize JARVIS

        Args:
            config: Configuration object
            data_bridge: Optional DataBridge for UI communication
        """
        self.config = config
        self.data_bridge = data_bridge
        self.logger = setup_logging(debug=config.debug_mode, name='jarvis')

        # Add UI log handler if data bridge is provided
        if self.data_bridge:
            ui_handler = UILogHandler(self.data_bridge)
            self.logger.addHandler(ui_handler)

        # Initialize components
        self.model = None
        self.frame_asr = None
        self.audio_capture = None
        self.transcription_buffer = RollingBuffer(max_duration=config.buffer_duration)

        # State
        self.shutdown = False
        self.last_trigger_time = 0
        self.last_detection_time = 0

    def load_model(self) -> bool:
        """
        Load NeMo ASR model

        Returns:
            True if successful, False otherwise
        """
        if not self.config.enable_model:
            self.logger.warning("Model loading disabled by config")
            if self.data_bridge:
                self.data_bridge.update_state(model_loaded=False)
            return True

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

        return True

    def initialize_audio(self) -> bool:
        """
        Initialize audio capture

        Returns:
            True if successful, False otherwise
        """
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

    def continuous_logging(self) -> None:
        """Main loop: continuous speech capture and transcription"""
        if not self.config.enable_microphone:
            self.logger.info("Microphone disabled, nothing to do")
            return

        if not self.config.enable_model:
            self.logger.info("Microphone test mode (model disabled)")
        else:
            self.logger.info("Starting continuous speech capture...")

        # Accumulator for audio chunks
        audio_accumulator = []
        chunks_captured = 0

        try:
            iteration = 0
            while not self.shutdown:
                try:
                    iteration += 1

                    # Capture audio chunk
                    audio_chunk = self.audio_capture.capture_chunk()
                    if audio_chunk is None:
                        continue

                    chunks_captured += 1

                    # Accumulate chunks
                    audio_accumulator.append(audio_chunk)

                    # Calculate and send audio level for UI (every chunk)
                    if self.data_bridge:
                        max_amp, avg_amp = AudioCapture.calculate_energy(audio_chunk)
                        self.data_bridge.send_audio_level(max_amp, avg_amp)

                    # Process when we have enough audio (frame length)
                    total_samples = sum(len(chunk) for chunk in audio_accumulator)
                    frame_samples = int(self.config.frame_len * self.config.sample_rate)

                    if total_samples >= frame_samples:
                        # Combine accumulated audio
                        combined_audio = np.concatenate(audio_accumulator)

                        # Test mode: just show stats
                        if not self.config.enable_model or not self.config.enable_transcription:
                            self.logger.info(
                                f"MIC TEST: {total_samples} samples "
                                f"({total_samples/self.config.sample_rate:.2f}s) "
                                f"- max: {max_amp:.0f}"
                            )
                        else:
                            # Transcribe
                            if self.data_bridge:
                                self.data_bridge.update_state(processing=True)

                            text = self.frame_asr.transcribe_chunk(combined_audio)

                            if self.data_bridge:
                                self.data_bridge.update_state(processing=False)

                            if text:
                                # Log to file
                                self.log_conversation(text)

                                # Add to buffer
                                self.transcription_buffer.add(text)

                                # Send to UI
                                if self.data_bridge:
                                    self.data_bridge.send_transcription(text)

                                # Display (only if no UI)
                                if not self.config.enable_ui:
                                    timestamp = datetime.now().strftime('%H:%M:%S')
                                    self.logger.info(f"[{timestamp}] {text}")

                        # Reset accumulator with overlap
                        overlap_samples = int(0.4 * self.config.sample_rate)
                        if len(combined_audio) > overlap_samples:
                            audio_accumulator = [combined_audio[-overlap_samples:]]
                        else:
                            audio_accumulator = []

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    self.logger.error(f"Main loop error: {e}", exc_info=True)

        except KeyboardInterrupt:
            self.logger.info("Stopped by user")

    def start(self) -> bool:
        """
        Start JARVIS

        Returns:
            True if successful, False otherwise
        """
        self.logger.info("="*60)
        self.logger.info("JARVIS - Speech Logger v2.0")
        self.logger.info("="*60)

        # Clear log files on startup
        try:
            Path(self.config.log_file).write_text('')
            Path(self.config.improved_log_file).write_text('')
        except Exception as e:
            self.logger.warning(f"Could not clear log files: {e}")

        # Load model
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
            self.continuous_logging()
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

        return True

    def cleanup(self) -> None:
        """Cleanup resources"""
        self.shutdown = True
        self.logger.info("Shutting down...")


# Global references for cleanup
_ui_instance = None
_jarvis_instance = None


def signal_handler(sig, frame):
    """Handle SIGINT gracefully"""
    global _ui_instance, _jarvis_instance

    print("\n\nShutting down JARVIS...")

    # Stop JARVIS
    if _jarvis_instance:
        _jarvis_instance.shutdown = True
        _jarvis_instance.cleanup()

    # Stop UI
    if _ui_instance:
        _ui_instance.stop()

    sys.exit(0)


def main():
    """Main entry point"""
    global _ui_instance, _jarvis_instance

    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Load configuration
        config = Config()

        # Validate config
        errors = config.validate()
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return 1

        # Create data bridge and UI if enabled
        data_bridge = None
        ui = None

        if config.enable_ui:
            try:
                data_bridge = DataBridge()
                ui = JarvisUI(
                    data_bridge,
                    refresh_rate=config.ui_refresh_rate,
                    log_history=config.ui_log_history
                )
                ui.start()
                _ui_instance = ui  # Store for signal handler
            except Exception as e:
                print(f"Warning: UI failed to start, falling back to standard logging: {e}")
                data_bridge = None
                ui = None

        # Create and start JARVIS
        jarvis = Jarvis(config, data_bridge=data_bridge)
        _jarvis_instance = jarvis  # Store for signal handler

        success = jarvis.start()

        # Stop UI if running
        if ui:
            ui.stop()
            _ui_instance = None

        _jarvis_instance = None
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 0
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1
    finally:
        # Ensure cleanup even on errors
        if _ui_instance:
            _ui_instance.stop()
        if _jarvis_instance:
            _jarvis_instance.shutdown = True


if __name__ == "__main__":
    sys.exit(main())
