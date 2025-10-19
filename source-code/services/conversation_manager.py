#!/usr/bin/env python3
"""
Conversation Manager
Routes voice commands to appropriate backend (Ollama chat or Claude Code SDK)
"""
import logging
import re
from typing import Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from .ollama_client import OllamaClient
from .claude_code_handler import ClaudeCodeHandler

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Types of user intent"""
    CHAT = "chat"  # Simple conversation → Ollama
    CODE = "code"  # Coding task → Claude Code SDK
    UNKNOWN = "unknown"


@dataclass
class ConversationResponse:
    """Response from conversation manager"""
    intent: IntentType
    full_response: str  # Full response text
    short_response: str  # Shortened for TTS
    success: bool
    backend: str  # "ollama" or "claude_code"


class ConversationManager:
    """
    Manages conversation flow and routes to appropriate backend

    Wake word detection → Intent classification → Route to backend → TTS
    """

    def __init__(
        self,
        wake_word: str = "jarvis",
        ollama_client: Optional[OllamaClient] = None,
        claude_handler: Optional[ClaudeCodeHandler] = None,
        max_tts_sentences: int = 2
    ):
        """
        Initialize conversation manager

        Args:
            wake_word: Wake word to detect (case-insensitive)
            ollama_client: Ollama client for chat
            claude_handler: Claude Code handler for coding tasks
            max_tts_sentences: Max sentences in TTS response
        """
        self.wake_word = wake_word.lower()
        self.max_tts_sentences = max_tts_sentences

        # Backends
        self.ollama = ollama_client or OllamaClient()
        self.claude = claude_handler or ClaudeCodeHandler()

        # Coding-related keywords for intent classification
        self.code_keywords = [
            # Actions
            "refactor", "add", "create", "fix", "debug", "implement", "modify",
            "update", "change", "write", "edit", "delete", "remove",
            # Code concepts
            "function", "class", "method", "variable", "file", "code",
            "script", "test", "bug", "error", "exception",
            # File operations
            "save", "read file", "open file", "search code",
            # Development
            "commit", "push", "pull", "branch", "merge", "review",
            "deploy", "build", "run", "execute", "install"
        ]

        logger.info(f"Conversation manager initialized (wake_word='{wake_word}')")
        logger.info(f"Ollama available: {self.ollama.is_available()}")
        logger.info(f"Claude Code enabled: {self.claude.enabled}")

    def detect_wake_word(self, text: str) -> Optional[str]:
        """
        Detect wake word and extract command

        Args:
            text: Transcribed text

        Returns:
            Command after wake word, or None if not detected

        Example:
            "Jarvis, what's the weather?" → "what's the weather?"
            "Hey Jarvis refactor this" → "refactor this"
        """
        if not text:
            return None

        text_lower = text.lower().strip()

        # Check if starts with wake word
        if text_lower.startswith(self.wake_word):
            # Extract command after wake word
            command = text[len(self.wake_word):].strip()

            # Remove common punctuation at start
            command = re.sub(r'^[,.:;!?]\s*', '', command)

            if command:
                logger.info(f"Wake word detected: '{self.wake_word}' | Command: '{command}'")
                return command

        return None

    def classify_intent(self, command: str) -> IntentType:
        """
        Classify user intent (chat vs code task)

        Args:
            command: User command (after wake word)

        Returns:
            Intent type
        """
        if not command:
            return IntentType.UNKNOWN

        command_lower = command.lower()

        # Check for coding keywords
        for keyword in self.code_keywords:
            if keyword in command_lower:
                logger.debug(f"Code intent detected (keyword: '{keyword}')")
                return IntentType.CODE

        # Check for explicit Claude Code triggers
        code_triggers = ["code", "programming", "developer", "implement"]
        if any(trigger in command_lower for trigger in code_triggers):
            return IntentType.CODE

        # Default to chat for simple queries
        logger.debug("Chat intent detected (default)")
        return IntentType.CHAT

    async def process_command(
        self,
        command: str,
        force_intent: Optional[IntentType] = None
    ) -> ConversationResponse:
        """
        Process a command and route to appropriate backend

        Args:
            command: User command (without wake word)
            force_intent: Force specific intent (for testing)

        Returns:
            Conversation response
        """
        # Classify intent
        intent = force_intent or self.classify_intent(command)

        logger.info(f"Processing command: '{command}' | Intent: {intent.value}")

        # Route to appropriate backend
        if intent == IntentType.CODE and self.claude.enabled:
            return await self._handle_code_task(command)
        else:
            return self._handle_chat(command)

    def _handle_chat(self, message: str) -> ConversationResponse:
        """
        Handle simple chat query with Ollama

        Args:
            message: User message

        Returns:
            Conversation response
        """
        logger.debug(f"Routing to Ollama: '{message}'")

        # Get response from Ollama
        full_response = self.ollama.chat(message)

        if not full_response:
            return ConversationResponse(
                intent=IntentType.CHAT,
                full_response="Sorry, I couldn't process that.",
                short_response="Sorry, I couldn't process that.",
                success=False,
                backend="ollama"
            )

        # Extract short version for TTS
        short_response = self.ollama.extract_short_response(
            full_response,
            max_sentences=self.max_tts_sentences
        )

        return ConversationResponse(
            intent=IntentType.CHAT,
            full_response=full_response,
            short_response=short_response or full_response,
            success=True,
            backend="ollama"
        )

    async def _handle_code_task(self, command: str) -> ConversationResponse:
        """
        Handle code task with Claude Code SDK

        Args:
            command: Coding command

        Returns:
            Conversation response
        """
        logger.debug(f"Routing to Claude Code: '{command}'")

        # Execute via Claude Code SDK
        success = await self.claude.execute_command(command)

        if success:
            full_response = f"I've completed the task: {command}"
            short_response = "Task completed!"
        else:
            full_response = f"I couldn't complete the task: {command}"
            short_response = "Task failed."

        return ConversationResponse(
            intent=IntentType.CODE,
            full_response=full_response,
            short_response=short_response,
            success=success,
            backend="claude_code"
        )

    def process_transcription(self, text: str) -> Optional[str]:
        """
        Process transcription and check for wake word

        Args:
            text: Transcribed text

        Returns:
            Command if wake word detected, None otherwise
        """
        return self.detect_wake_word(text)

    def clear_chat_history(self) -> None:
        """Clear Ollama chat history"""
        self.ollama.clear_history()
        logger.info("Chat history cleared")


# Example usage
if __name__ == "__main__":
    import asyncio

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create manager
    manager = ConversationManager(wake_word="jarvis")

    # Test wake word detection
    print("\n=== Wake Word Detection ===")
    test_inputs = [
        "Jarvis, what's the weather?",
        "Hey there, just testing",
        "JARVIS refactor this function",
        "jarvis, tell me a joke"
    ]

    for text in test_inputs:
        command = manager.detect_wake_word(text)
        if command:
            print(f"✓ '{text}' → Command: '{command}'")
        else:
            print(f"✗ '{text}' → No wake word")

    # Test intent classification
    print("\n=== Intent Classification ===")
    test_commands = [
        "what's the weather today?",
        "refactor the audio module",
        "tell me a joke",
        "add error handling to the API",
        "how are you?"
    ]

    for cmd in test_commands:
        intent = manager.classify_intent(cmd)
        print(f"'{cmd}' → {intent.value}")

    # Test async processing
    async def test_processing():
        print("\n=== Command Processing ===")

        # Chat query
        response = await manager.process_command("Hello, how are you?")
        print(f"\nChat Query:")
        print(f"  Full: {response.full_response}")
        print(f"  TTS:  {response.short_response}")
        print(f"  Backend: {response.backend}")

        # Code task (if Claude Code available)
        if manager.claude.enabled:
            response = await manager.process_command("show me the transcription module structure")
            print(f"\nCode Task:")
            print(f"  Full: {response.full_response}")
            print(f"  TTS:  {response.short_response}")
            print(f"  Backend: {response.backend}")

    asyncio.run(test_processing())
