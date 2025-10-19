#!/usr/bin/env python3
"""
Simple Conversation Manager
Handles wake word detection and routes to Qwen Agent
"""
import logging
import re
from typing import Optional
from dataclasses import dataclass

from .qwen_agent import QwenAgent, AgentResponse

logger = logging.getLogger(__name__)


class SimpleConversationManager:
    """
    Simplified conversation manager

    Flow:
    1. Detect wake word ("Jarvis")
    2. Extract command
    3. Send to Qwen Agent (which handles everything else)
    """

    def __init__(
        self,
        wake_word: str = "jarvis",
        qwen_agent: Optional[QwenAgent] = None
    ):
        """
        Initialize conversation manager

        Args:
            wake_word: Wake word to detect (case-insensitive)
            qwen_agent: Qwen Agent instance
        """
        self.wake_word = wake_word.lower()
        self.agent = qwen_agent or QwenAgent()

        logger.info(f"Simple Conversation Manager initialized (wake_word='{wake_word}')")
        logger.info(f"Qwen Agent available: {self.agent.is_available()}")

    def detect_wake_word(self, text: str) -> Optional[str]:
        """
        Detect wake word and extract command

        Args:
            text: Transcribed text

        Returns:
            Command after wake word, or None if not detected

        Example:
            "Jarvis" → "Hello" (greeting)
            "Jarvis, what's the weather?" → "what's the weather?"
            "Hey Jarvis refactor this" → "refactor this"
            "what's the weather jarvis" → "what's the weather"
        """
        if not text:
            return None

        text_lower = text.lower().strip()

        # Check if wake word appears anywhere in the text
        if self.wake_word in text_lower:
            # Remove the wake word from the text
            command = re.sub(
                rf'\b{re.escape(self.wake_word)}\b',
                '',
                text_lower,
                flags=re.IGNORECASE
            ).strip()

            # Remove common filler words at the start
            command = re.sub(r'^(hey|ok|okay|hi|hello)[,\s]+', '', command, flags=re.IGNORECASE).strip()

            # Remove common punctuation at start and end
            command = re.sub(r'^[,.:;!?\s]+', '', command)
            command = re.sub(r'[,.:;!?\s]+$', '', command)

            # If nothing left after removing wake word, use a greeting
            if not command:
                logger.info(f"Wake word detected: '{self.wake_word}' (greeting)")
                return "Hello"
            else:
                logger.info(f"Wake word detected: '{self.wake_word}' | Command: '{command}'")
                return command

        return None

    async def process_command(self, command: str) -> AgentResponse:
        """
        Process a command via Qwen Agent (non-streaming)

        Args:
            command: User command (without wake word)

        Returns:
            Agent response
        """
        logger.info(f"Processing command: '{command}'")
        return await self.agent.chat(command)

    async def process_command_stream(self, command: str):
        """
        Process a command via Qwen Agent (streaming)

        Args:
            command: User command (without wake word)

        Yields:
            Response chunks as they arrive
        """
        logger.info(f"Processing command (streaming): '{command}'")
        async for chunk in self.agent.chat_stream(command):
            yield chunk

    def process_transcription(self, text: str) -> Optional[str]:
        """
        Process transcription and check for wake word

        Args:
            text: Transcribed text

        Returns:
            Command if wake word detected, None otherwise
        """
        return self.detect_wake_word(text)

    def clear_history(self) -> None:
        """Clear conversation history"""
        self.agent.clear_history()
        logger.info("Conversation history cleared")


# Example usage
if __name__ == "__main__":
    import asyncio

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def test_manager():
        """Test the conversation manager"""
        manager = SimpleConversationManager(wake_word="jarvis")

        print("=== Testing Conversation Manager ===\n")

        # Test wake word detection
        print("1. Wake word detection:")
        test_inputs = [
            "Jarvis, what's the weather?",
            "Hey there, just testing",
            "JARVIS refactor this function",
            "jarvis, tell me a joke"
        ]

        for text in test_inputs:
            command = manager.detect_wake_word(text)
            if command:
                print(f"   ✓ '{text}' → Command: '{command}'")
            else:
                print(f"   ✗ '{text}' → No wake word")

        print("\n2. Processing commands:")

        # Simple question
        command = manager.detect_wake_word("Jarvis, what's 5 plus 3?")
        if command:
            response = await manager.process_command(command)
            print(f"   Q: {command}")
            print(f"   A: {response.short_text}")
            print(f"   Tool: {response.tool_used or 'None'}\n")

        # Coding task
        command = manager.detect_wake_word("Jarvis, add error handling to the API")
        if command:
            response = await manager.process_command(command)
            print(f"   Q: {command}")
            print(f"   A: {response.short_text}")
            print(f"   Tool: {response.tool_used or 'None'}\n")

    asyncio.run(test_manager())
