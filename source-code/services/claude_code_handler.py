#!/usr/bin/env python3
"""
Claude Code Command Handler
Detects trigger words in transcribed text and sends commands to Claude Code
"""
import asyncio
import logging
import re
from typing import Optional, List, Tuple
from pathlib import Path

try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False

logger = logging.getLogger(__name__)


class ClaudeCodeHandler:
    """
    Handles voice commands for Claude Code integration

    Detects trigger words like "jarvis code" or "hey jarvis" in transcribed text
    and executes the command using Claude Code SDK
    """

    def __init__(
        self,
        trigger_words: List[str] = None,
        project_path: str = None,
        allowed_tools: List[str] = None,
        enabled: bool = True
    ):
        """
        Initialize Claude Code handler

        Args:
            trigger_words: List of trigger phrases (e.g., ["jarvis", "hey jarvis", "jarvis code"])
            project_path: Path to the project directory for Claude Code
            allowed_tools: List of tools Claude Code can use
            enabled: Whether Claude Code integration is enabled
        """
        self.enabled = enabled and CLAUDE_SDK_AVAILABLE

        if not CLAUDE_SDK_AVAILABLE:
            logger.warning("Claude Agent SDK not available - Claude Code integration disabled")
            logger.warning("Install with: pip install claude-agent-sdk")
            self.enabled = False

        # Default trigger words (case-insensitive)
        self.trigger_words = trigger_words or [
            "jarvis",
            "hey jarvis",
            "jarvis code",
            "code assistant"
        ]

        # Sort by length (longest first) to match "hey jarvis" before "jarvis"
        self.trigger_words = sorted(self.trigger_words, key=len, reverse=True)

        # Project configuration
        self.project_path = project_path or str(Path.cwd())

        # Default allowed tools (can be customized)
        self.allowed_tools = allowed_tools or [
            "Read",
            "Edit",
            "Write",
            "Bash",
            "Grep",
            "Glob"
        ]

        # Command history
        self.command_history: List[Tuple[str, str]] = []  # [(command, response), ...]
        self.max_history = 50

        logger.info(f"Claude Code handler initialized (enabled={self.enabled})")
        if self.enabled:
            logger.info(f"Trigger words: {self.trigger_words}")
            logger.info(f"Project path: {self.project_path}")

    def detect_trigger(self, text: str) -> Optional[str]:
        """
        Detect trigger word in text and extract the command

        Args:
            text: Transcribed text

        Returns:
            Command string if trigger detected, None otherwise

        Example:
            "jarvis add error handling to the API" -> "add error handling to the API"
            "hey jarvis fix the bug in main.py" -> "fix the bug in main.py"
        """
        if not text:
            return None

        text_lower = text.lower().strip()

        # Check each trigger word (longest first)
        for trigger in self.trigger_words:
            trigger_lower = trigger.lower()

            # Check if text starts with trigger word
            if text_lower.startswith(trigger_lower):
                # Extract command after trigger
                command = text[len(trigger):].strip()

                # Remove common punctuation at the start
                command = re.sub(r'^[,.:;!?]\s*', '', command)

                if command:
                    logger.info(f"Trigger detected: '{trigger}' | Command: '{command}'")
                    return command

        return None

    async def execute_command(self, command: str) -> bool:
        """
        Execute a Claude Code command asynchronously

        Args:
            command: The coding command to execute

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.warning("Claude Code handler is disabled")
            return False

        if not command:
            logger.warning("Empty command provided")
            return False

        try:
            logger.info(f"Executing Claude Code command: '{command}'")

            # Configure Claude Code options
            options = ClaudeAgentOptions(
                cwd=self.project_path,
                allowed_tools=self.allowed_tools
            )

            # Execute command via Claude Code SDK
            async with ClaudeSDKClient(options=options) as client:
                # Send the command
                await client.query(command)

                # Stream responses
                responses = []
                async for msg in client.receive_response():
                    logger.debug(f"Claude Code response: {msg}")
                    responses.append(str(msg))

                # Store in history
                response_text = "\n".join(responses) if responses else "No response"
                self._add_to_history(command, response_text)

                logger.info(f"Claude Code command completed: '{command}'")
                return True

        except Exception as e:
            logger.error(f"Failed to execute Claude Code command: {e}", exc_info=True)
            return False

    def execute_command_sync(self, command: str) -> bool:
        """
        Execute a Claude Code command synchronously (blocking)

        Args:
            command: The coding command to execute

        Returns:
            True if successful, False otherwise
        """
        try:
            # Run async function in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self.execute_command(command))
                return result
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Failed to execute command synchronously: {e}", exc_info=True)
            return False

    def process_transcription(self, text: str) -> bool:
        """
        Process transcribed text and execute Claude Code command if trigger detected

        Args:
            text: Transcribed text from voice input

        Returns:
            True if command was detected and executed, False otherwise
        """
        if not self.enabled:
            return False

        # Detect trigger and extract command
        command = self.detect_trigger(text)

        if command:
            # Execute command in background (non-blocking)
            logger.info(f"Processing Claude Code command: '{command}'")

            # For now, execute synchronously
            # TODO: Could be made async with threading or asyncio
            return self.execute_command_sync(command)

        return False

    def _add_to_history(self, command: str, response: str) -> None:
        """Add command/response to history"""
        self.command_history.append((command, response))

        # Trim history if too long
        if len(self.command_history) > self.max_history:
            self.command_history = self.command_history[-self.max_history:]

    def get_history(self, limit: int = 10) -> List[Tuple[str, str]]:
        """
        Get recent command history

        Args:
            limit: Maximum number of recent commands to return

        Returns:
            List of (command, response) tuples
        """
        return self.command_history[-limit:]

    def clear_history(self) -> None:
        """Clear command history"""
        self.command_history = []
        logger.info("Claude Code command history cleared")


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create handler
    handler = ClaudeCodeHandler(
        trigger_words=["jarvis", "hey jarvis"],
        project_path="/home/paul/Work/jarvis"
    )

    # Test trigger detection
    test_inputs = [
        "jarvis add error handling to the API",
        "hey jarvis fix the bug in main.py",
        "just some regular text",
        "jarvis, create a new function for database queries",
        "JARVIS refactor the transcription module"  # Case insensitive
    ]

    print("\n=== Testing Trigger Detection ===")
    for text in test_inputs:
        command = handler.detect_trigger(text)
        if command:
            print(f"✓ '{text}' -> Command: '{command}'")
        else:
            print(f"✗ '{text}' -> No trigger detected")

    # Test command execution (if SDK available)
    if CLAUDE_SDK_AVAILABLE:
        print("\n=== Testing Command Execution ===")
        test_command = "Show me the structure of the core directory"
        print(f"Executing: '{test_command}'")
        success = handler.execute_command_sync(test_command)
        print(f"Result: {'Success' if success else 'Failed'}")
