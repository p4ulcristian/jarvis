#!/home/paul/Work/jarvis/venv/bin/python
"""
JARVIS - Voice-to-Text System with Streaming NeMo ASR
Production-ready refactored version with modular architecture
"""
import os
import sys
import signal
import threading
from pathlib import Path
from typing import Optional

# Import ONLY UI modules at startup for fast loading
# Heavy imports (numpy, NeMo, core modules) are deferred until needed
from ui import DataBridge, JarvisUI


class Jarvis:
    """Main JARVIS application"""

    def __init__(self, config, data_bridge: Optional[DataBridge] = None):
        """
        Initialize JARVIS

        Args:
            config: Configuration object
            data_bridge: Optional DataBridge for UI communication
        """
        # Defer heavy imports until __init__
        from core import setup_logging, RollingBuffer
        from ui.data_bridge import UILogHandler

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
        self.keyboard_typer = None

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
        # Import only when needed
        from core.transcription import load_nemo_model, FrameASR

        if not self.config.enable_model:
            self.logger.warning("Model loading disabled by config")
            if self.data_bridge:
                self.data_bridge.update_state(model_loaded=False)
            return True

        self.logger.info("Loading AI model (this may take 10-60 seconds)...")
        if self.data_bridge:
            self.data_bridge.send_log("INFO", "Loading NeMo Parakeet-TDT model (0.6B params)...")

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
        # Import only when needed
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
        # Import only when needed
        try:
            import numpy as np
        except ImportError as e:
            self.logger.error(f"Failed to import numpy: {e}")
            if self.data_bridge:
                self.data_bridge.send_log("ERROR", f"Failed to import numpy: {e}")
            return

        from datetime import datetime
        from core import AudioCapture

        if not self.config.enable_microphone:
            self.logger.info("Microphone disabled, nothing to do")
            return

        if not self.config.enable_model:
            self.logger.info("Microphone test mode (model disabled)")
        else:
            self.logger.info("Starting real-time continuous transcription...")

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

                    # Calculate and send audio level for UI (every chunk)
                    if self.data_bridge:
                        max_amp, avg_amp = AudioCapture.calculate_energy(audio_chunk)
                        self.data_bridge.send_audio_level(max_amp, avg_amp)

                    # Test mode: just show stats
                    if not self.config.enable_model or not self.config.enable_transcription:
                        # Check if this chunk contains speech (for display only)
                        has_speech = self.frame_asr.has_speech(audio_chunk, debug=False)
                        if has_speech:
                            chunk_duration = len(audio_chunk) / self.config.sample_rate
                            self.logger.info(
                                f"MIC TEST: {len(audio_chunk)} samples "
                                f"({chunk_duration:.2f}s) "
                                f"- max: {max_amp:.0f}"
                            )
                    else:
                        # Check if chunk has speech
                        has_speech = self.frame_asr.has_speech(audio_chunk, debug=False)

                        if has_speech:
                            # Add speech to buffer
                            self.frame_asr.add_speech_chunk(audio_chunk)
                        else:
                            # Increment silence counter
                            self.frame_asr.silence_count += 1

                        # Check if we should transcribe accumulated audio
                        if self.frame_asr.should_transcribe():
                            # Get buffered audio
                            buffered_audio = self.frame_asr.get_buffered_audio()

                            if len(buffered_audio) > 0:
                                if self.data_bridge:
                                    self.data_bridge.update_state(processing=True)

                                text = self.frame_asr.transcribe_chunk(buffered_audio)

                                if self.data_bridge:
                                    self.data_bridge.update_state(processing=False)

                                self.logger.debug(f"Transcription result: '{text}' (empty={not text})")
                            else:
                                text = ""

                        else:
                            # Not ready to transcribe yet
                            continue

                        # Only log/display non-empty transcriptions
                        if text:
                            # Log to file
                            self.log_conversation(text)

                            # Add to buffer
                            self.transcription_buffer.add(text)

                            # Send to UI
                            if self.data_bridge:
                                self.data_bridge.send_transcription(text)

                            # Check if Type Mode is active and type the text
                            if self.data_bridge and self.keyboard_typer:
                                state = self.data_bridge.get_state()
                                if state.type_mode:
                                    try:
                                        self.keyboard_typer.type_text(text)
                                        self.logger.debug(f"Typed: {text}")
                                    except Exception as e:
                                        self.logger.error(f"Failed to type text: {e}")

                            # Display (only if no UI)
                            if not self.config.enable_ui:
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                self.logger.info(f"[{timestamp}] {text}")

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    self.logger.error(f"Main loop error: {e}", exc_info=True)

        except KeyboardInterrupt:
            self.logger.info("Stopped by user")

    def start(self) -> bool:
        """
        Start JARVIS (assumes UI is already running if enabled)

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

        # Clear keyboard events file to start fresh (may fail if owned by root)
        try:
            Path('/tmp/jarvis-keyboard-events').write_text('')
        except (PermissionError, Exception) as e:
            self.logger.debug(f"Could not clear keyboard events file (may need sudo): {e}")

        # Initialize keyboard typer
        try:
            from services.keyboard_typer import get_typer
            self.keyboard_typer = get_typer(typing_delay=0.01)
            # Pre-initialize to check permissions
            if self.keyboard_typer.initialize():
                self.logger.info("Keyboard typer initialized successfully")
            else:
                self.logger.warning("Keyboard typer initialization failed - Type Mode will not work")
                if self.data_bridge:
                    self.data_bridge.send_log("WARNING", "Keyboard typer failed - check permissions")
        except Exception as e:
            self.logger.warning(f"Could not initialize keyboard typer: {e}")

        # Load model (this is slow - UI should already be running)
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

        # Clean up keyboard typer
        if self.keyboard_typer:
            self.keyboard_typer.cleanup()


# Global references for cleanup
_ui_instance = None
_jarvis_instance = None


def shutdown_all():
    """Shutdown both JARVIS and UI"""
    global _ui_instance, _jarvis_instance

    # Stop JARVIS
    if _jarvis_instance:
        _jarvis_instance.shutdown = True
        _jarvis_instance.cleanup()
        _jarvis_instance = None

    # Stop UI
    if _ui_instance:
        _ui_instance.stop()
        _ui_instance = None

    sys.exit(0)


def signal_handler(sig, frame):
    """Handle SIGINT gracefully"""
    shutdown_all()


def run_jarvis_main(config, data_bridge):
    """Run JARVIS in a separate thread"""
    global _jarvis_instance

    try:
        # Import Config here
        from core import Config as ConfigClass

        # Create JARVIS instance
        jarvis = Jarvis(config, data_bridge=data_bridge)
        _jarvis_instance = jarvis

        # Start JARVIS (this will load model, initialize audio, and run)
        jarvis.start()

    except Exception as e:
        if data_bridge:
            data_bridge.send_log("ERROR", f"JARVIS failed: {e}")
    finally:
        _jarvis_instance = None


def main():
    """Main entry point"""
    global _ui_instance, _jarvis_instance

    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # START UI IMMEDIATELY - before ANY heavy imports
        # Just create the UI first, check config later
        data_bridge = DataBridge()
        ui = JarvisUI(
            data_bridge,
            refresh_rate=4,
            log_history=50
        )
        _ui_instance = ui

        # Set shutdown callback
        ui.set_shutdown_callback(shutdown_all)

        # Start JARVIS initialization in background thread
        def init_and_run():
            try:
                # Now import Config (heavy import happens in background)
                from core import Config

                # Load config (user sees this in UI)
                data_bridge.send_log("INFO", "Loading configuration...")
                config = Config()

                # Check if UI should actually be enabled
                if not config.enable_ui:
                    data_bridge.send_log("WARNING", "UI disabled in config but already running")

                # Validate config
                errors = config.validate()
                if errors:
                    for error in errors:
                        data_bridge.send_log("ERROR", f"Config error: {error}")
                    return

                # Update UI with actual config values
                data_bridge.send_log("INFO", "Configuration loaded successfully")

                # Now run JARVIS main with loaded config
                run_jarvis_main(config, data_bridge)

            except Exception as e:
                data_bridge.send_log("ERROR", f"Initialization failed: {e}")

        # Start background initialization
        jarvis_thread = threading.Thread(
            target=init_and_run,
            daemon=False,
            name="JARVIS-Thread"
        )
        jarvis_thread.start()

        # Start UI in main thread (blocking) - appears instantly
        ui.start()

        # When UI exits, wait for JARVIS to finish
        jarvis_thread.join(timeout=2.0)

        return 0

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
