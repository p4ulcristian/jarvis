#!/usr/bin/env python3
"""
AI Detection Module - Detects when messages are directed at AI assistant.
"""

import os
from typing import Optional
from llama_cpp import Llama
import yaml


class AIDetector:
    """Detects if a message is directed at or about an AI assistant."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the detector with configuration."""

        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.ai_name = self.config['ai_name']
        self.threshold = self.config['detection']['threshold']
        self.verbose = self.config['detection'].get('verbose', False)

        # Initialize model
        model_config = self.config['model']

        if self.verbose:
            print(f"Loading model from {model_config['model_path']}...")

        self.model = Llama(
            model_path=model_config['model_path'],
            n_gpu_layers=model_config.get('n_gpu_layers', -1),
            n_ctx=model_config.get('n_ctx', 2048),
            verbose=self.verbose
        )

        if self.verbose:
            print("Model loaded successfully!")

    def is_message_for_ai(self, message: str) -> bool:
        """
        Determine if a message is directed at or about the AI assistant.

        Args:
            message: The message to analyze

        Returns:
            True if message is directed at AI, False otherwise
        """

        # Build the prompt
        prompt = self._build_prompt(message)

        # Get model response
        response = self.model(
            prompt,
            max_tokens=self.config['model'].get('max_tokens', 10),
            temperature=self.config['model'].get('temperature', 0.3),
            stop=["\n"],
            echo=False
        )

        # Extract answer
        answer = response['choices'][0]['text'].strip().upper()

        if self.verbose:
            print(f"\nMessage: {message}")
            print(f"Answer: {answer}")

        # Parse response
        return self._parse_response(answer)

    def _build_prompt(self, message: str) -> str:
        """Build the detection prompt using Llama 3.2 chat format."""

        # Use Llama 3.2 instruction format
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are a classifier. Determine if a message is directly addressing or calling an AI named "{self.ai_name}". Answer only YES or NO.

YES examples:
- "{self.ai_name}, help me" (direct address)
- "Hey {self.ai_name}" (greeting)
- "Can you explain this?" (request to AI in conversation)

NO examples:
- "I talked to {self.ai_name}" (past reference)
- "{self.ai_name} is nice" (statement about)
- "Tell {self.ai_name} I said hi" (indirect reference)<|eot_id|><|start_header_id|>user<|end_header_id|>

Message: "{message}"
Is this directly addressing {self.ai_name}?<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""

        return prompt

    def _parse_response(self, answer: str) -> bool:
        """Parse the model's response to a boolean."""

        # Check for YES/NO in response
        if "YES" in answer:
            return True
        elif "NO" in answer:
            return False
        else:
            # If unclear, default to False (conservative approach)
            if self.verbose:
                print(f"Warning: Unclear response '{answer}', defaulting to NO")
            return False

    def close(self):
        """Clean up resources."""
        # llama-cpp-python handles cleanup automatically
        pass


def main():
    """Test the detector with sample messages."""

    detector = AIDetector()

    test_messages = [
        "Hey Alex, can you help me?",
        "I was talking to Alex yesterday",
        "Alex is a nice name",
        "What do you think about this?",
        "The weather is nice today",
        "Alex, what time is it?",
    ]

    print("\n" + "=" * 60)
    print("Testing AI Detection")
    print("=" * 60)

    for msg in test_messages:
        result = detector.is_message_for_ai(msg)
        status = "✓ TRIGGER" if result else "✗ IGNORE"
        print(f"\n{status}: {msg}")

    print("\n" + "=" * 60)

    detector.close()


if __name__ == "__main__":
    main()
