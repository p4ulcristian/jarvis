#!/usr/bin/env python3
"""
Response Processor
Handles TTS (text-to-speech) output via say.sh and response formatting
"""
import logging
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TTSResult:
    """Result of TTS operation"""
    success: bool
    text: str
    error: Optional[str] = None


class ResponseProcessor:
    """
    Processes AI responses and converts to speech via say.sh

    Handles:
    - TTS via say.sh (OpenAI TTS)
    - Response formatting
    - Emotional/personality parameters
    """

    def __init__(
        self,
        say_script_path: str = None,
        default_personality: str = "helpful and friendly",
        enabled: bool = True
    ):
        """
        Initialize response processor

        Args:
            say_script_path: Path to say.sh script
            default_personality: Default TTS personality/emotion
            enabled: Whether TTS is enabled
        """
        self.enabled = enabled
        self.default_personality = default_personality

        # Find say.sh script
        if say_script_path:
            self.say_script = Path(say_script_path)
        else:
            # Auto-detect in common locations
            possible_paths = [
                Path(__file__).parent / "say.sh",
                Path(__file__).parent.parent / "services" / "say.sh",
                Path.cwd() / "say.sh"
            ]

            self.say_script = None
            for path in possible_paths:
                if path.exists():
                    self.say_script = path
                    break

        if not self.say_script or not self.say_script.exists():
            logger.warning(f"say.sh script not found! TTS disabled.")
            logger.warning(f"Searched: {possible_paths}")
            self.enabled = False
        else:
            logger.info(f"Response processor initialized: say.sh={self.say_script}")

    def speak(
        self,
        text: str,
        personality: Optional[str] = None,
        blocking: bool = True
    ) -> TTSResult:
        """
        Speak text via say.sh (OpenAI TTS)

        Args:
            text: Text to speak
            personality: Emotional tone (e.g., "excited", "calm", "helpful")
            blocking: If True, wait for TTS to complete. If False, return immediately.

        Returns:
            TTS result
        """
        if not self.enabled:
            logger.debug("TTS disabled, skipping speech")
            return TTSResult(success=False, text=text, error="TTS disabled")

        if not text:
            logger.warning("Empty text provided to speak()")
            return TTSResult(success=False, text="", error="Empty text")

        personality = personality or self.default_personality

        try:
            logger.info(f"Speaking: '{text[:50]}...' (personality: {personality})")

            # Build command
            cmd = [str(self.say_script), text, personality]

            # Execute say.sh
            if blocking:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30  # Max 30 seconds for TTS
                )

                if result.returncode != 0:
                    error_msg = result.stderr or "Unknown error"
                    logger.error(f"say.sh failed: {error_msg}")
                    return TTSResult(success=False, text=text, error=error_msg)

                logger.debug("TTS completed successfully")
                return TTSResult(success=True, text=text)

            else:
                # Non-blocking: fire and forget
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.debug("TTS started (non-blocking)")
                return TTSResult(success=True, text=text)

        except subprocess.TimeoutExpired:
            logger.error("TTS timeout (>30s)")
            return TTSResult(success=False, text=text, error="Timeout")
        except FileNotFoundError:
            logger.error(f"say.sh script not found at: {self.say_script}")
            return TTSResult(success=False, text=text, error="Script not found")
        except Exception as e:
            logger.error(f"TTS error: {e}", exc_info=True)
            return TTSResult(success=False, text=text, error=str(e))

    def acknowledge(self, blocking: bool = False) -> TTSResult:
        """
        Speak acknowledgment ("Yes I hear you, how can I help you?")

        Args:
            blocking: If True, wait for TTS to complete

        Returns:
            TTS result
        """
        text = "Yes I hear you, how can I help you?"
        return self.speak(text, personality="friendly", blocking=blocking)

    def speak_response(
        self,
        full_response: str,
        short_response: str,
        personality: Optional[str] = None,
        blocking: bool = True
    ) -> TTSResult:
        """
        Speak AI response (uses short version for TTS)

        Args:
            full_response: Full AI response (for display)
            short_response: Shortened version for TTS
            personality: Emotional tone
            blocking: If True, wait for TTS to complete

        Returns:
            TTS result
        """
        # Log full response
        logger.debug(f"Full response: {full_response}")

        # Speak short version
        return self.speak(short_response, personality=personality, blocking=blocking)

    def speak_error(self, error_message: str, blocking: bool = True) -> TTSResult:
        """
        Speak error message

        Args:
            error_message: Error to announce
            blocking: If True, wait for TTS to complete

        Returns:
            TTS result
        """
        # Make error message user-friendly
        friendly_message = f"Sorry, {error_message}"
        return self.speak(friendly_message, personality="apologetic", blocking=blocking)

    def is_available(self) -> bool:
        """
        Check if TTS is available

        Returns:
            True if say.sh exists and TTS is enabled
        """
        return self.enabled and self.say_script and self.say_script.exists()


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create processor
    processor = ResponseProcessor()

    if not processor.is_available():
        print("⚠️  TTS not available (say.sh not found)")
        exit(1)

    print("=== Testing Response Processor ===\n")

    # Test acknowledgment
    print("1. Acknowledgment...")
    result = processor.acknowledge(blocking=True)
    print(f"   Result: {result.success}\n")

    # Test simple response
    print("2. Simple response...")
    result = processor.speak_response(
        full_response="The weather today is sunny with a high of 75 degrees. Perfect for outdoor activities!",
        short_response="It's sunny and 75 degrees today!",
        personality="cheerful"
    )
    print(f"   Result: {result.success}\n")

    # Test error message
    print("3. Error message...")
    result = processor.speak_error("I couldn't find that file")
    print(f"   Result: {result.success}\n")

    # Test non-blocking
    print("4. Non-blocking speech...")
    result = processor.speak(
        "This is a non-blocking test. I'll return immediately!",
        blocking=False
    )
    print(f"   Result: {result.success} (returned immediately)\n")

    import time
    print("   Waiting for TTS to finish...")
    time.sleep(3)
    print("   Done!")
