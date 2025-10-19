#!/usr/bin/env python3
"""
Process Manager for JARVIS
Manages external subprocess lifecycle (keyboard listener)
"""
import subprocess
import time
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ProcessManager:
    """
    Manages external processes with proper lifecycle management

    Features:
    - Automatic sudo privilege handling
    - Process health monitoring
    - Graceful + forced termination
    - Startup validation
    - Resource cleanup
    """

    def __init__(self, event_file: str = "/tmp/jarvis-keyboard-events"):
        """
        Initialize process manager

        Args:
            event_file: Path to keyboard event file
        """
        self.event_file = event_file
        self.process: Optional[subprocess.Popen] = None
        self._is_running = False

        logger.info(f"ProcessManager initialized (event_file={event_file})")

    def start_keyboard_listener(self, script_path: Optional[Path] = None) -> bool:
        """
        Start keyboard listener process with sudo

        Args:
            script_path: Path to keyboard_listener.py (auto-detect if None)

        Returns:
            True if started successfully, False otherwise
        """
        if self._is_running:
            logger.warning("Keyboard listener already running")
            return True

        # Auto-detect script path if not provided
        if script_path is None:
            script_dir = Path(__file__).parent
            script_path = script_dir / "keyboard_listener.py"

        if not script_path.exists():
            logger.error(f"Keyboard listener not found at {script_path}")
            return False

        try:
            # Verify sudo access (should already be cached from main.py)
            result = subprocess.run(['sudo', '-v'], check=False, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error("Failed to verify sudo access")
                logger.error(f"Error: {result.stderr}")
                return False

            # Clean up old event file (may be owned by root from previous run)
            try:
                subprocess.run(['sudo', 'rm', '-f', self.event_file], check=False, capture_output=True)
            except Exception:
                pass  # Ignore cleanup errors

            # Start keyboard listener with sudo
            python_exe = sys.executable
            logger.info("Starting keyboard listener...")

            self.process = subprocess.Popen(
                ['sudo', '-E', python_exe, str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait for listener to initialize
            time.sleep(1.0)

            # Validate process started successfully
            if self.process.poll() is not None:
                # Process already exited - something went wrong
                stdout, stderr = self.process.communicate()
                logger.error("Keyboard listener failed to start")
                if stderr:
                    logger.error(f"Error: {stderr}")
                if stdout:
                    logger.debug(f"Output: {stdout}")
                self.process = None
                return False

            self._is_running = True
            logger.info("✓ Keyboard listener running!")
            logger.info("  Hotkey: Hold LEFT CTRL to enable Type Mode")
            return True

        except FileNotFoundError:
            logger.error("'sudo' command not found. Install sudo or run as root.")
            return False
        except Exception as e:
            logger.error(f"Failed to start keyboard listener: {e}", exc_info=True)
            return False

    def stop_keyboard_listener(self, timeout: float = 2.0) -> bool:
        """
        Stop keyboard listener process

        Args:
            timeout: Timeout for graceful shutdown (seconds)

        Returns:
            True if stopped successfully (graceful or forced)
        """
        if not self._is_running or self.process is None:
            logger.debug("Keyboard listener not running, nothing to stop")
            return True

        logger.info(f"Stopping keyboard listener (timeout={timeout}s)...")

        try:
            # Try graceful termination first (SIGTERM)
            self.process.terminate()

            # Wait for graceful shutdown
            try:
                self.process.wait(timeout=timeout)
                logger.info("Keyboard listener stopped gracefully")
                self._cleanup()
                return True
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't stop
                logger.warning(f"Keyboard listener did not stop after {timeout}s, force killing...")
                self.process.kill()
                self.process.wait()
                logger.info("Keyboard listener force killed")
                self._cleanup()
                return True

        except Exception as e:
            logger.error(f"Error stopping keyboard listener: {e}", exc_info=True)
            self._cleanup()
            return False

    def force_kill(self) -> None:
        """Force kill the keyboard listener immediately"""
        if self.process:
            try:
                self.process.kill()
                self.process.wait()
                logger.info("Keyboard listener force killed")
            except Exception as e:
                logger.error(f"Error force killing keyboard listener: {e}")
            finally:
                self._cleanup()

    def is_running(self) -> bool:
        """Check if keyboard listener is running"""
        if not self._is_running or self.process is None:
            return False

        # Check if process is still alive
        if self.process.poll() is not None:
            logger.warning("Keyboard listener process terminated unexpectedly")
            self._cleanup()
            return False

        return True

    def get_status(self) -> dict:
        """
        Get process status information

        Returns:
            Dictionary with process status details
        """
        return {
            "running": self.is_running(),
            "pid": self.process.pid if self.process else None,
            "event_file": self.event_file,
            "event_file_exists": Path(self.event_file).exists()
        }

    def _cleanup(self) -> None:
        """Internal cleanup of process state"""
        self.process = None
        self._is_running = False

    def __del__(self):
        """Cleanup on deletion"""
        if self._is_running:
            self.force_kill()
