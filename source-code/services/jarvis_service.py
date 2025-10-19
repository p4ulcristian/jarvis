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

        self.config = config
        self.data_bridge = data_bridge
        self.logger = setup_logging(
            debug=config.debug_mode,
            name='jarvis',
            data_bridge=self.data_bridge
        )

        # Core components (lazy initialized)
        self.model = None
        self.frame_asr = None
        self.audio_capture = None
        self.transcription_buffer = RollingBuffer(max_duration=config.buffer_duration)
        self.keyboard_typer = None
        self.transcription_worker = None
        self.claude_code_handler = None

        # Chat mode components
        self.conversation_manager = None
        self.response_processor = None
        self.accumulated_chat_text = []  # Buffer for accumulating chat transcriptions

        # State management
        self.shutdown = False
        self.last_trigger_time = 0
        self.last_detection_time = 0
        self.is_running = False

        # Performance monitoring
        self.last_metrics_log = 0
        self.metrics_log_interval = 60.0  # Log metrics every 60 seconds

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

            # Initialize transcription worker for async processing
            from core.transcription_worker import TranscriptionWorker
            self.transcription_worker = TranscriptionWorker(
                frame_asr=self.frame_asr,
                timeout=10.0,  # 10 second timeout for transcription
                max_queue_size=50,
                callback=None  # We'll poll for results
            )
            self.transcription_worker.start()
            self.logger.info("Transcription worker started with 10s timeout protection")

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

    def initialize_claude_code_handler(self) -> bool:
        """
        Initialize Claude Code handler for voice-driven coding

        Returns:
            True if successful, False otherwise
        """
        if not self.config.enable_claude_code:
            self.logger.info("Claude Code integration disabled by config")
            return True

        try:
            from services.claude_code_handler import ClaudeCodeHandler

            self.claude_code_handler = ClaudeCodeHandler(
                trigger_words=[w.strip() for w in self.config.claude_code_trigger_words],
                project_path=self.config.claude_code_project_path,
                allowed_tools=[t.strip() for t in self.config.claude_code_allowed_tools],
                enabled=self.config.enable_claude_code
            )

            if self.claude_code_handler.enabled:
                self.logger.info(f"Claude Code handler initialized with triggers: {self.config.claude_code_trigger_words}")
                if self.data_bridge:
                    self.data_bridge.send_log("INFO", f"Claude Code integration enabled - say '{self.config.claude_code_trigger_words[0]}' to code")
                return True
            else:
                self.logger.warning("Claude Code handler disabled - SDK not available")
                if self.data_bridge:
                    self.data_bridge.send_log("WARNING", "Claude Code SDK not installed - voice coding disabled")
                return False

        except Exception as e:
            self.logger.warning(f"Could not initialize Claude Code handler: {e}")
            if self.data_bridge:
                self.data_bridge.send_log("WARNING", f"Claude Code initialization failed: {e}")
            return False

    def ensure_ollama_running(self) -> bool:
        """
        Ensure Ollama service is running, start it if needed

        Returns:
            True if Ollama is running or successfully started, False otherwise
        """
        import subprocess
        import time

        try:
            # Check if Ollama is already running
            result = subprocess.run(
                ['pgrep', '-f', 'ollama serve'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                self.logger.info("Ollama is already running")
                return True

            # Ollama not running - start it
            self.logger.info("Starting Ollama service...")
            if self.data_bridge:
                self.data_bridge.send_log("INFO", "Starting Ollama service...")

            # Start Ollama in background
            subprocess.Popen(
                ['ollama', 'serve'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            # Wait for Ollama to be ready (max 5 seconds)
            for i in range(10):
                time.sleep(0.5)
                # Check if it's running
                check_result = subprocess.run(
                    ['pgrep', '-f', 'ollama serve'],
                    capture_output=True,
                    text=True
                )
                if check_result.returncode == 0:
                    self.logger.info("Ollama service started successfully")
                    if self.data_bridge:
                        self.data_bridge.send_log("INFO", "Ollama service started")
                    return True

            self.logger.warning("Ollama service did not start in time")
            if self.data_bridge:
                self.data_bridge.send_log("WARNING", "Ollama startup timeout")
            return False

        except FileNotFoundError:
            self.logger.warning("Ollama not installed - install with: curl -fsSL https://ollama.com/install.sh | sh")
            if self.data_bridge:
                self.data_bridge.send_log("WARNING", "Ollama not installed")
            return False
        except Exception as e:
            self.logger.warning(f"Could not start Ollama: {e}")
            if self.data_bridge:
                self.data_bridge.send_log("WARNING", f"Ollama startup failed: {e}")
            return False

    def initialize_chat_mode(self) -> bool:
        """
        Initialize chat mode components (Qwen Agent + TTS)

        Returns:
            True if successful, False otherwise
        """
        if not self.config.enable_chat_mode:
            self.logger.info("Chat mode disabled by config")
            return True

        try:
            from services.simple_conversation_manager import SimpleConversationManager
            from services.qwen_agent import QwenAgent
            from services.response_processor import ResponseProcessor

            # Initialize response processor (TTS)
            self.response_processor = ResponseProcessor(
                default_personality=self.config.tts_personality,
                enabled=True
            )

            if not self.response_processor.is_available():
                self.logger.warning("TTS (say.sh) not available - chat responses will be silent")
                if self.data_bridge:
                    self.data_bridge.send_log("WARNING", "TTS unavailable - responses will be silent")

            # Initialize Qwen Agent with Claude Code as a tool
            qwen_agent = QwenAgent(
                model=self.config.chat_model,
                system_prompt=self.config.chat_system_prompt,
                claude_handler=self.claude_code_handler,
                max_history=10,
                max_tts_sentences=self.config.max_tts_sentences
            )

            # Initialize conversation manager
            self.conversation_manager = SimpleConversationManager(
                wake_word=self.config.wake_word,
                qwen_agent=qwen_agent
            )

            self.logger.info(f"Chat mode initialized: wake_word='{self.config.wake_word}', model={self.config.chat_model}")
            if self.data_bridge:
                self.data_bridge.send_log("INFO", f"Chat mode ready - say '{self.config.wake_word}' to chat")
            return True

        except Exception as e:
            self.logger.warning(f"Could not initialize chat mode: {e}", exc_info=True)
            if self.data_bridge:
                self.data_bridge.send_log("WARNING", f"Chat mode initialization failed: {e}")
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
        ptt_recording_mode = False  # Track if we're in isolated PTT recording
        chunks_skipped = 0  # Track skipped chunks for graceful degradation

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

                    # When PTT is pressed, start isolated recording session
                    if ptt_pressed:
                        ptt_recording_mode = True
                        # Clear the frame ASR buffer for isolated recording
                        if self.frame_asr:
                            self.frame_asr.reset()
                        if self.data_bridge:
                            self.data_bridge.send_log("INFO", "Recording... (release Ctrl to transcribe and type)")

                    # When PTT is released, transcribe the isolated recording and paste
                    if ptt_released and ptt_recording_mode:
                        ptt_recording_mode = False

                        # Get the buffered audio from isolated recording
                        if self.frame_asr:
                            buffered_audio = self.frame_asr.get_buffered_audio()

                            if len(buffered_audio) > 0:
                                if self.data_bridge:
                                    self.data_bridge.send_log("INFO", "Processing recording...")
                                    self.data_bridge.update_state(processing=True)

                                # Submit to async worker (non-blocking)
                                if self.transcription_worker:
                                    submitted = self.transcription_worker.submit(buffered_audio)

                                    if submitted:
                                        # Wait for transcription result with polling (up to 15 seconds)
                                        # Poll multiple times to handle longer transcriptions
                                        result = None
                                        max_wait_time = 15.0
                                        poll_interval = 0.5
                                        elapsed = 0.0

                                        while elapsed < max_wait_time and not result:
                                            result = self.transcription_worker.get_result(timeout=poll_interval)
                                            if not result:
                                                elapsed += poll_interval
                                                # Continue polling

                                        if result and result.success and result.text:
                                            # Check for Claude Code trigger words first
                                            claude_command_detected = False
                                            if self.claude_code_handler and self.claude_code_handler.enabled:
                                                command = self.claude_code_handler.detect_trigger(result.text)
                                                if command:
                                                    claude_command_detected = True
                                                    self.logger.info(f"Claude Code command detected: '{command}'")
                                                    if self.data_bridge:
                                                        self.data_bridge.send_log("INFO", f"Executing: {command[:50]}...")
                                                        self.data_bridge.send_transcription(f"[CLAUDE CODE] {result.text}")

                                                    # Execute Claude Code command (async, non-blocking)
                                                    try:
                                                        success = self.claude_code_handler.execute_command_sync(command)
                                                        if success:
                                                            self.logger.info("Claude Code command executed successfully")
                                                            if self.data_bridge:
                                                                self.data_bridge.send_log("INFO", "Claude Code command completed")
                                                        else:
                                                            self.logger.warning("Claude Code command failed")
                                                            if self.data_bridge:
                                                                self.data_bridge.send_log("WARNING", "Claude Code command failed")
                                                    except Exception as e:
                                                        self.logger.error(f"Claude Code execution error: {e}", exc_info=True)
                                                        if self.data_bridge:
                                                            self.data_bridge.send_log("ERROR", f"Claude Code error: {e}")

                                                    if self.data_bridge:
                                                        self.data_bridge.update_state(processing=False)

                                            # Only paste text if it wasn't a Claude Code command
                                            if not claude_command_detected and self.keyboard_typer:
                                                try:
                                                    self.keyboard_typer.paste_text(result.text)
                                                    self.logger.debug(f"PTT typed: {result.text} (latency: {elapsed:.1f}s)")
                                                    if self.data_bridge:
                                                        self.data_bridge.send_log("INFO", f"Typed: {result.text[:50]}...")
                                                        self.data_bridge.send_transcription(result.text)
                                                        self.data_bridge.update_state(processing=False)

                                                    # Log to conversation file
                                                    self.log_conversation(result.text)
                                                    self.transcription_buffer.add(result.text)
                                                except Exception as e:
                                                    self.logger.error(f"Failed to auto-type PTT text: {e}", exc_info=True)
                                                    if self.data_bridge:
                                                        self.data_bridge.update_state(processing=False)
                                        elif result and not result.success:
                                            self.logger.warning(f"PTT transcription failed: {result.error}")
                                            if self.data_bridge:
                                                self.data_bridge.send_log("WARNING", f"Transcription failed: {result.error}")
                                                self.data_bridge.update_state(processing=False)
                                        else:
                                            self.logger.warning(f"PTT transcription timeout after {max_wait_time}s")
                                            if self.data_bridge:
                                                self.data_bridge.send_log("WARNING", f"Transcription timeout (waited {elapsed:.1f}s)")
                                                self.data_bridge.update_state(processing=False)
                                    else:
                                        self.logger.warning("Failed to submit PTT audio for transcription")
                                        if self.data_bridge:
                                            self.data_bridge.send_log("WARNING", "Transcription queue full")
                                            self.data_bridge.update_state(processing=False)
                            else:
                                if self.data_bridge:
                                    self.data_bridge.send_log("INFO", "No audio recorded")

                    # ALWAYS capture and process audio
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
                        # Isolated PTT recording mode: buffer audio but don't transcribe
                        if ptt_recording_mode:
                            has_speech = self.frame_asr.has_speech(audio_chunk, debug=False)
                            if has_speech:
                                # Buffer speech for later transcription
                                self.frame_asr.add_speech_chunk(audio_chunk)

                        # Continuous transcription mode (when PTT not active)
                        elif not ptt_recording_mode:
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
                                    # Submit to async worker (non-blocking)
                                    if self.transcription_worker:
                                        submitted = self.transcription_worker.submit(buffered_audio)

                                        if submitted:
                                            if self.data_bridge:
                                                self.data_bridge.update_state(processing=True)
                                            chunks_skipped = 0  # Reset skip counter
                                        else:
                                            # Worker queue is full - graceful degradation
                                            chunks_skipped += 1
                                            self.logger.warning(
                                                f"Transcription queue full - skipping chunk "
                                                f"({chunks_skipped} chunks skipped so far)"
                                            )
                                            if self.data_bridge and chunks_skipped == 1:
                                                self.data_bridge.send_log(
                                                    "WARNING",
                                                    "System degraded - transcription falling behind"
                                                )

                                            # Check worker health after multiple failures
                                            if chunks_skipped > 10:
                                                if not self.transcription_worker.is_healthy():
                                                    self.logger.critical(
                                                        "Transcription worker unhealthy - may need restart"
                                                    )
                                                    if self.data_bridge:
                                                        self.data_bridge.update_state(
                                                            error="Transcription system degraded"
                                                        )

                            # Poll for transcription results (non-blocking)
                            if self.transcription_worker:
                                result = self.transcription_worker.get_result(timeout=0.001)
                                if result:
                                    if self.data_bridge:
                                        self.data_bridge.update_state(processing=False)

                                    if result.success and result.text:
                                        # Process successful transcription
                                        self.log_conversation(result.text)
                                        self.transcription_buffer.add(result.text)

                                        # Always send to transcription UI
                                        if self.data_bridge:
                                            self.data_bridge.send_transcription(result.text)

                                        # If chat mode is enabled and accumulating, accumulate transcriptions
                                        if self.conversation_manager and self.response_processor and self.data_bridge:
                                            state = self.data_bridge.get_state()
                                            if state.chat_accumulating:
                                                # Accumulate this transcription
                                                self.accumulated_chat_text.append(result.text)
                                                # Send to chat window as user message
                                                self.data_bridge.send_chat_message("user", result.text)
                                                self.logger.info(f"Accumulated chat text: '{result.text}'")

                                        if not self.config.enable_ui:
                                            timestamp = datetime.now().strftime('%H:%M:%S')
                                            self.logger.info(f"[{timestamp}] {result.text}")

                                    elif not result.success:
                                        # Log transcription errors
                                        if result.error:
                                            self.logger.error(
                                                f"Transcription failed: {result.error} "
                                                f"(latency: {result.latency:.1f}s)"
                                            )

                            # Check for chat button triggers - starts accumulating mode
                            if self.conversation_manager and self.response_processor and self.data_bridge:
                                chat_trigger = self.data_bridge.get_chat_trigger(timeout=0.001)
                                if chat_trigger:
                                    # Clear accumulated text buffer and start chat session
                                    self.accumulated_chat_text.clear()
                                    self.logger.info("Chat button pressed - starting chat session (SEND button now active)")

                            # Check for send button triggers - sends accumulated text to agent
                            if self.conversation_manager and self.response_processor and self.data_bridge:
                                send_trigger = self.data_bridge.get_send_trigger(timeout=0.001)
                                if send_trigger:
                                    # Get accumulated text
                                    if self.accumulated_chat_text:
                                        command = " ".join(self.accumulated_chat_text).strip()
                                        # Clear buffer immediately for next question
                                        self.accumulated_chat_text.clear()
                                    else:
                                        command = "Hello"  # Default greeting if no accumulated text

                                    self.logger.info(f"Send button pressed - sending: '{command}'")

                                    # Update chat state - keep accumulating mode active for next question
                                    if self.data_bridge:
                                        self.data_bridge.update_state(chat_active=True)
                                        # Don't disable chat_accumulating - it stays True for the session

                                    # Acknowledge via TTS (non-blocking) - optional "I hear you"
                                    # Comment out if you don't want the TTS acknowledgment:
                                    # self.response_processor.acknowledge(blocking=False)

                                    # Process command via Qwen Agent (async with streaming)
                                    try:
                                        import asyncio
                                        import uuid

                                        # Generate unique message ID for streaming
                                        message_id = str(uuid.uuid4())
                                        full_response = ""

                                        # Run async chat in sync context
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        try:
                                            # Get streaming response
                                            stream_generator = self.conversation_manager.process_command_stream(command)

                                            # Process streaming chunks - accumulate full response
                                            async def process_stream():
                                                nonlocal full_response
                                                async for chunk in stream_generator:
                                                    full_response += chunk
                                                    # Just accumulate, don't send individual chunks to UI

                                            loop.run_until_complete(process_stream())

                                            # Send complete response to chat window once
                                            if self.data_bridge and full_response:
                                                self.data_bridge.send_chat_message(
                                                    role="jarvis",
                                                    text=full_response,
                                                    backend="ollama"
                                                )

                                            # Log response
                                            self.logger.info(f"Agent response (streamed): {full_response[:100]}...")

                                            # Speak response via TTS (short version)
                                            # Extract short version from full response
                                            import re
                                            sentences = re.split(r'[.!?]+', full_response)
                                            sentences = [s.strip() for s in sentences if s.strip()]
                                            short_response = '. '.join(sentences[:self.config.max_tts_sentences])
                                            if short_response and not short_response.endswith(('.', '!', '?')):
                                                short_response += '.'

                                            if short_response:
                                                self.response_processor.speak_response(
                                                    full_response=full_response,
                                                    short_response=short_response,
                                                    blocking=False
                                                )

                                            # Update state - ready for next question
                                            if self.data_bridge:
                                                self.data_bridge.update_state(chat_active=False)
                                        finally:
                                            loop.close()

                                    except Exception as e:
                                        self.logger.error(f"Error processing chat command: {e}", exc_info=True)
                                        if self.data_bridge:
                                            self.data_bridge.send_log("ERROR", f"Chat error: {e}")
                                            self.data_bridge.update_state(chat_active=False)

                        # Periodic metrics logging
                        current_time = time.time()
                        if current_time - self.last_metrics_log > self.metrics_log_interval:
                            self._log_performance_metrics()
                            self.last_metrics_log = current_time

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

        # Ensure Ollama is running (needed for chat mode and other features)
        self.ensure_ollama_running()

        # Initialize keyboard typer
        self.initialize_keyboard_typer()

        # Initialize Claude Code handler
        self.initialize_claude_code_handler()

        # Initialize chat mode (Qwen Agent + TTS)
        self.initialize_chat_mode()

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

    def _log_performance_metrics(self) -> None:
        """Log performance metrics for monitoring"""
        try:
            # Audio queue stats
            if self.audio_capture:
                audio_stats = self.audio_capture.get_queue_stats()
                self.logger.info(
                    f"[METRICS] Audio queue: {audio_stats['size']}/{audio_stats['capacity']} "
                    f"({audio_stats['utilization_pct']:.0f}%)"
                )

            # Transcription worker stats
            if self.transcription_worker:
                metrics = self.transcription_worker.get_metrics()
                success_rate = (metrics.successful / metrics.total_requests * 100) if metrics.total_requests > 0 else 0
                self.logger.info(
                    f"[METRICS] Transcription: {metrics.successful}/{metrics.total_requests} success "
                    f"({success_rate:.1f}%), avg latency: {metrics.avg_latency:.2f}s, "
                    f"max: {metrics.max_latency:.2f}s, timeouts: {metrics.timeouts}, "
                    f"queue: {metrics.queue_depth}/{metrics.queue_capacity}"
                )

                # Send to UI if available
                if self.data_bridge and metrics.total_requests > 0:
                    self.data_bridge.send_log(
                        "INFO",
                        f"Performance: {success_rate:.0f}% success, "
                        f"{metrics.avg_latency:.1f}s avg latency"
                    )

        except Exception as e:
            self.logger.error(f"Error logging metrics: {e}")

    def cleanup(self) -> None:
        """Cleanup resources"""
        self.shutdown = True
        self.is_running = False
        self.logger.info("Cleaning up JARVIS resources...")

        # Stop transcription worker
        if self.transcription_worker:
            try:
                self.transcription_worker.stop()
            except Exception as e:
                self.logger.error(f"Error stopping transcription worker: {e}")

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
