#!/usr/bin/env python3
"""
Ollama Chat Client
Handles simple conversational queries using local Ollama models
"""
import logging
import requests
import json
from typing import Optional, Dict, List, Iterator
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Represents a chat message"""
    role: str  # "user", "assistant", or "system"
    content: str


class OllamaClient:
    """
    Client for interacting with local Ollama server for chat
    Handles simple conversational queries using lightweight local models
    """

    def __init__(
        self,
        model: str = "qwen3:8b",
        base_url: str = "http://localhost:11434",
        system_prompt: str = None,
        temperature: float = 0.7
    ):
        """
        Initialize Ollama chat client

        Args:
            model: Ollama model to use (e.g., "qwen3:8b")
            base_url: Base URL for Ollama API
            system_prompt: System prompt to set personality/behavior
            temperature: Response randomness (0.0-1.0)
        """
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.temperature = temperature

        # Default system prompt for voice assistant
        self.system_prompt = system_prompt or (
            "You are Jarvis, a helpful voice assistant. "
            "Respond in 1-2 sentences maximum for voice output. "
            "Be casual, friendly, and concise."
        )

        # Conversation history
        self.conversation_history: List[ChatMessage] = []
        self.max_history = 10  # Keep last N exchanges

        logger.info(f"Ollama client initialized: model={model}, url={base_url}")

    def clear_history(self) -> None:
        """Clear conversation history"""
        self.conversation_history = []
        logger.debug("Conversation history cleared")

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to conversation history

        Args:
            role: Message role ("user" or "assistant")
            content: Message content
        """
        self.conversation_history.append(ChatMessage(role=role, content=content))

        # Trim history if too long
        if len(self.conversation_history) > self.max_history * 2:  # *2 because user+assistant
            # Keep system message and recent exchanges
            self.conversation_history = self.conversation_history[-(self.max_history * 2):]

    def _build_messages(self, user_message: str) -> List[Dict[str, str]]:
        """
        Build message list for Ollama API

        Args:
            user_message: The current user message

        Returns:
            List of message dicts for API
        """
        messages = []

        # Add system prompt
        messages.append({
            "role": "system",
            "content": self.system_prompt
        })

        # Add conversation history
        for msg in self.conversation_history:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        return messages

    def chat(
        self,
        message: str,
        stream: bool = False,
        save_to_history: bool = True
    ) -> Optional[str]:
        """
        Send a chat message and get response

        Args:
            message: User message
            stream: Whether to stream response (for real-time display)
            save_to_history: Whether to save to conversation history

        Returns:
            Full response text, or None if error
        """
        if not message:
            logger.warning("Empty message provided")
            return None

        try:
            # Build message list with history
            messages = self._build_messages(message)

            logger.debug(f"Sending chat request: {message}")

            # Make API request
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": stream,
                "options": {
                    "temperature": self.temperature
                }
            }

            response = requests.post(url, json=payload, stream=stream)
            response.raise_for_status()

            if stream:
                # Streaming response
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        if "message" in data:
                            chunk = data["message"].get("content", "")
                            full_response += chunk
                            yield chunk  # Yield for streaming

                response_text = full_response
            else:
                # Non-streaming response
                data = response.json()
                response_text = data.get("message", {}).get("content", "")

            logger.debug(f"Received response: {response_text[:100]}...")

            # Save to history
            if save_to_history:
                self.add_message("user", message)
                self.add_message("assistant", response_text)

            return response_text

        except requests.exceptions.ConnectionError:
            logger.error("Failed to connect to Ollama server. Is it running?")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in chat: {e}", exc_info=True)
            return None

    def chat_stream(self, message: str, save_to_history: bool = True) -> Iterator[str]:
        """
        Stream chat response token by token

        Args:
            message: User message
            save_to_history: Whether to save to conversation history

        Yields:
            Response tokens as they arrive
        """
        return self.chat(message, stream=True, save_to_history=save_to_history)

    def extract_short_response(self, full_response: str, max_sentences: int = 2) -> str:
        """
        Extract a short version of response for TTS

        Args:
            full_response: Full model response
            max_sentences: Maximum number of sentences to keep

        Returns:
            Shortened response suitable for voice
        """
        if not full_response:
            return ""

        # Split into sentences (basic)
        import re
        sentences = re.split(r'[.!?]+', full_response)

        # Filter empty and take first N
        sentences = [s.strip() for s in sentences if s.strip()]
        short = '. '.join(sentences[:max_sentences])

        # Add period if needed
        if short and not short.endswith(('.', '!', '?')):
            short += '.'

        return short

    def is_available(self) -> bool:
        """
        Check if Ollama server is available

        Returns:
            True if server is reachable, False otherwise
        """
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=2)
            return response.status_code == 200
        except:
            return False


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create client
    client = OllamaClient(model="qwen3:8b")

    # Check if available
    if not client.is_available():
        print("⚠️  Ollama server not available. Start it with: ollama serve")
        exit(1)

    print("Jarvis Chat (Qwen3:8b) - Type 'quit' to exit\n")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("Goodbye!")
            break

        if not user_input:
            continue

        # Get response
        response = client.chat(user_input)

        if response:
            print(f"Jarvis: {response}")

            # Show short version for TTS
            short = client.extract_short_response(response)
            if short != response:
                print(f"(TTS): {short}")
        else:
            print("⚠️  Failed to get response")

        print()
