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


class Jarvis:
    """Main JARVIS application"""

    def __init__(self, config: Config):
        """
        Initialize JARVIS

        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = setup_logging(debug=config.debug_mode, name='jarvis')

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
            return True

        self.model = load_nemo_model(self.config)
        if self.model is None:
            return False

        # Initialize frame ASR
        if self.config.enable_transcription:
            self.frame_asr = FrameASR(self.model, self.config)
            self.logger.info("Frame ASR initialized")

        return True

    def initialize_audio(self) -> bool:
        """
        Initialize audio capture

        Returns:
            True if successful, False otherwise
        """
        if not self.config.enable_microphone:
            self.logger.warning("Microphone disabled by config")
            return True

        try:
            self.audio_capture = AudioCapture(self.config)
            self.logger.info("Audio capture initialized")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize audio: {e}")
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

                    # Process when we have enough audio (frame length)
                    total_samples = sum(len(chunk) for chunk in audio_accumulator)
                    frame_samples = int(self.config.frame_len * self.config.sample_rate)

                    if total_samples >= frame_samples:
                        # Combine accumulated audio
                        combined_audio = np.concatenate(audio_accumulator)

                        # Test mode: just show stats
                        if not self.config.enable_model or not self.config.enable_transcription:
                            max_amp, avg_amp = AudioCapture.calculate_energy(combined_audio)
                            self.logger.info(
                                f"MIC TEST: {total_samples} samples "
                                f"({total_samples/self.config.sample_rate:.2f}s) "
                                f"- max: {max_amp:.0f}"
                            )
                        else:
                            # Transcribe
                            text = self.frame_asr.transcribe_chunk(combined_audio)

                            if text:
                                # Log to file
                                self.log_conversation(text)

                                # Add to buffer
                                self.transcription_buffer.add(text)

                                # Display
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


def signal_handler(sig, frame):
    """Handle SIGINT gracefully"""
    sys.exit(0)


def main():
    """Main entry point"""
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

        # Create and start JARVIS
        jarvis = Jarvis(config)
        success = jarvis.start()

        return 0 if success else 1

    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
