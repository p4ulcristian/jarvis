#!/usr/bin/env python3
"""
JARVIS - Voice-to-Text System with Streaming NeMo ASR
Production-ready refactored version with modular architecture
"""
import sys
import os
import signal
import threading
import logging
from typing import Optional

# Suppress noisy library logging BEFORE any imports (prevents TUI interference)
os.environ['HYDRA_FULL_ERROR'] = '0'
os.environ['NEMO_LOG_LEVEL'] = 'ERROR'

# Import ONLY UI modules at startup for fast loading
from ui import DataBridge, JarvisUI

# Global logger for main module
logger = logging.getLogger(__name__)


class ApplicationContext:
    """
    Application context - holds references to all components
    Replaces global variables with a clean container
    """

    def __init__(self):
        self.ui: Optional[JarvisUI] = None
        self.jarvis_service: Optional['JarvisService'] = None
        self.jarvis_thread: Optional[threading.Thread] = None
        self.process_manager: Optional['ProcessManager'] = None
        self.shutdown_manager: Optional['ShutdownManager'] = None
        self.data_bridge: Optional[DataBridge] = None
        self._shutdown_in_progress = False

    def initiate_shutdown(self) -> None:
        """
        Initiate coordinated shutdown of all components
        Thread-safe shutdown initiation
        """
        if self._shutdown_in_progress:
            logger.warning("Shutdown already in progress, ignoring duplicate call")
            return

        self._shutdown_in_progress = True
        logger.info("Initiating application shutdown...")

        if self.shutdown_manager:
            # Use ShutdownManager for coordinated shutdown
            success = self.shutdown_manager.shutdown()
            if success:
                logger.info("Application shutdown completed successfully")
            else:
                logger.warning("Application shutdown completed with errors")
        else:
            # Fallback: manual shutdown (shouldn't happen)
            logger.warning("No ShutdownManager available, performing manual shutdown")
            self._manual_shutdown()

    def _manual_shutdown(self) -> None:
        """Fallback manual shutdown if ShutdownManager not available"""
        if self.ui:
            try:
                self.ui.stop()
            except Exception as e:
                logger.error(f"Error stopping UI: {e}")

        if self.jarvis_service:
            try:
                self.jarvis_service.stop()
            except Exception as e:
                logger.error(f"Error stopping JARVIS: {e}")

        if self.process_manager:
            try:
                self.process_manager.force_kill()
            except Exception as e:
                logger.error(f"Error stopping keyboard listener: {e}")


# Global application context (single instance)
_app_context: Optional[ApplicationContext] = None


def signal_handler(sig, frame):
    """
    Handle SIGINT (Ctrl+C) gracefully

    This is the entry point for Ctrl+C shutdown
    """
    global _app_context

    logger.info(f"\nReceived signal {sig}, initiating shutdown...")

    if _app_context:
        _app_context.initiate_shutdown()
    else:
        logger.warning("No application context available, exiting immediately")
        sys.exit(0)


def run_jarvis_service(config, data_bridge: DataBridge, app_context: ApplicationContext):
    """
    Run JARVIS service in a separate thread

    Args:
        config: Configuration object
        data_bridge: DataBridge for UI communication
        app_context: Application context
    """
    # Defer import until thread starts
    from services.jarvis_service import JarvisService

    try:
        # Create JARVIS service
        jarvis = JarvisService(config, data_bridge=data_bridge)
        app_context.jarvis_service = jarvis

        # Start JARVIS (this blocks until shutdown)
        jarvis.start()

    except Exception as e:
        logger.error(f"JARVIS service failed: {e}", exc_info=True)
        if data_bridge:
            data_bridge.send_log("ERROR", f"JARVIS failed: {e}")


def main():
    """
    Main entry point

    Architecture:
    1. Create ApplicationContext (replaces global variables)
    2. Set up signal handlers
    3. Start keyboard listener (ProcessManager)
    4. Start UI immediately (fast startup)
    5. Load config and start JARVIS in background thread
    6. Use ShutdownManager for coordinated cleanup
    """
    global _app_context

    # Initialize application context
    _app_context = ApplicationContext()

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Import services (deferred)
        from services.process_manager import ProcessManager
        from services.shutdown_manager import ShutdownManager
        from core import Config

        # Create ProcessManager for keyboard listener
        process_manager = ProcessManager()
        _app_context.process_manager = process_manager

        # Start keyboard listener with sudo
        logger.info("Starting keyboard listener...")
        if not process_manager.start_keyboard_listener():
            logger.warning("Failed to start keyboard listener - Type Mode will not work")
            # Continue anyway - not a fatal error

        # Create DataBridge for UI communication
        data_bridge = DataBridge()
        _app_context.data_bridge = data_bridge

        # Create UI (starts immediately for fast visual feedback)
        ui = JarvisUI(
            data_bridge,
            refresh_rate=4,
            log_history=50
        )
        _app_context.ui = ui

        # Start JARVIS initialization in background thread
        def init_and_run():
            try:
                # Load config (heavy import happens in background)
                data_bridge.send_log("INFO", "Loading configuration...")
                config = Config()

                # Validate config
                errors = config.validate()
                if errors:
                    for error in errors:
                        data_bridge.send_log("ERROR", f"Config error: {error}")
                    return

                data_bridge.send_log("INFO", "Configuration loaded successfully")

                # Run JARVIS service (blocks until shutdown)
                run_jarvis_service(config, data_bridge, _app_context)

            except Exception as e:
                logger.error(f"Initialization failed: {e}", exc_info=True)
                data_bridge.send_log("ERROR", f"Initialization failed: {e}")

        # Start JARVIS thread (daemon=True so it doesn't block shutdown)
        jarvis_thread = threading.Thread(
            target=init_and_run,
            daemon=True,
            name="JARVIS-Thread"
        )
        jarvis_thread.start()
        _app_context.jarvis_thread = jarvis_thread

        # Create ShutdownManager and register components
        # Note: We defer this until after config is loaded, so we do it in a callback
        def setup_shutdown_manager_callback():
            """Setup ShutdownManager once config is loaded"""
            try:
                # Wait for config to load (up to 10 seconds)
                for i in range(100):
                    if _app_context.jarvis_service and _app_context.jarvis_service.config:
                        break
                    threading.Event().wait(0.1)

                config = _app_context.jarvis_service.config if _app_context.jarvis_service else Config()

                # Create ShutdownManager
                shutdown_manager = ShutdownManager(shutdown_timeout=config.shutdown_timeout)
                _app_context.shutdown_manager = shutdown_manager

                # Register components in shutdown order (LIFO)
                # 1. UI (stop first)
                shutdown_manager.register_component(
                    name="UI",
                    shutdown_func=lambda: ui.stop(),
                    timeout=2.0
                )

                # 2. JARVIS Service
                if _app_context.jarvis_service:
                    shutdown_manager.register_component(
                        name="JARVIS",
                        shutdown_func=lambda: _app_context.jarvis_service.stop(),
                        timeout=config.shutdown_timeout
                    )

                # 3. Keyboard Listener (shutdown last)
                shutdown_manager.register_component(
                    name="KeyboardListener",
                    shutdown_func=lambda: process_manager.stop_keyboard_listener(
                        timeout=config.graceful_shutdown_timeout
                    ),
                    timeout=config.graceful_shutdown_timeout + 1.0,
                    force_kill_func=lambda: process_manager.force_kill()
                )

                logger.info("ShutdownManager configured successfully")

            except Exception as e:
                logger.error(f"Failed to setup ShutdownManager: {e}", exc_info=True)

        # Start shutdown manager setup in background
        threading.Thread(
            target=setup_shutdown_manager_callback,
            daemon=True,
            name="ShutdownManager-Setup"
        ).start()

        # Set UI shutdown callback
        ui.set_shutdown_callback(lambda: _app_context.initiate_shutdown())

        # Start UI in main thread (blocking) - appears instantly
        ui.start()

        # When UI exits, wait briefly for JARVIS to finish
        if jarvis_thread.is_alive():
            logger.info("Waiting for JARVIS thread to finish...")
            jarvis_thread.join(timeout=1.0)

            # If still alive after timeout, log and exit anyway (daemon thread will be killed)
            if jarvis_thread.is_alive():
                logger.warning("JARVIS thread still running, forcing exit (daemon will be killed)")

        return 0

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        if _app_context:
            _app_context.initiate_shutdown()
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        if _app_context:
            _app_context.initiate_shutdown()
        return 1


if __name__ == "__main__":
    # Set up file-only logging for main module (no stdout - TUI handles display)
    from core import setup_logging

    # Configure root logger to prevent any StreamHandlers from being added
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    # Remove any existing handlers on root logger (prevents stdout output)
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            root_logger.removeHandler(handler)

    setup_logging(debug=False, name='__main__', data_bridge=None)

    sys.exit(main())
