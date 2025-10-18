#!/usr/bin/env python3
"""
AI Detection Module - Detects when messages are directed at AI assistant.
Uses DistilBERT-MNLI for fast zero-shot classification with rule-based pre-filtering.
"""

import os
import re
from typing import Optional, List
import yaml
from transformers import pipeline

# NLTK for sentence tokenization
try:
    import nltk
    from nltk.tokenize import sent_tokenize
    # Try to use punkt tokenizer, download if needed
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        print("[INFO] Downloading NLTK punkt tokenizer...")
        nltk.download('punkt', quiet=True)
except ImportError:
    print("[WARNING] NLTK not installed. Install with: pip install nltk")
    sent_tokenize = None


class AIDetector:
    """Detects if a message is directed at or about an AI assistant."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the detector with configuration."""

        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.ai_name = self.config['ai_name']
        self.ai_aliases = self.config.get('ai_aliases', [])
        self.threshold = self.config['detection']['threshold']
        self.verbose = self.config['detection'].get('verbose', False)
        self.use_model = self.config['model'].get('use_model', False)

        # All names to check (main name + aliases)
        self.all_names = [self.ai_name.lower()] + [alias.lower() for alias in self.ai_aliases]

        # Compile regex patterns for command detection for all names
        self.command_patterns = []
        self.mention_patterns = []

        for name in self.all_names:
            name_pattern = re.escape(name)

            # Patterns that indicate commanding/addressing
            self.command_patterns.extend([
                rf'\b{name_pattern}\s*,',  # "Jarvis, ..."
                rf'^{name_pattern}\s+\w+',  # "Jarvis do..."
                rf'\bhey\s+{name_pattern}\b',  # "hey Jarvis"
                rf'\bok(?:ay)?\s+{name_pattern}\b',  # "okay Jarvis"
                rf'{name_pattern}\s+(?:can|could|will|please)\b',  # "Jarvis can/could/will/please..."
                rf'{name_pattern}\s+(?:would|could)\s+you\b',  # "Jarvis would you..." / "Jarvis could you..."
            ])

            # Patterns that indicate just mentioning
            self.mention_patterns.extend([
                rf'\b{name_pattern}\s+is\b',  # "Jarvis is..."
                rf'\b{name_pattern}\s+would\s+(?!you)\w+',  # "Jarvis would like..." (but not "Jarvis would you")
                rf'\bwas\s+\w+\s+{name_pattern}\b',  # "was talking to Jarvis"
                rf'\btell\s+{name_pattern}\b',  # "tell Jarvis"
                rf'\btalking\s+to\s+{name_pattern}\b',  # "talking to Jarvis"
            ])

        # Only load model if explicitly enabled
        self.classifier = None
        if self.use_model:
            model_config = self.config['model']
            model_name = model_config.get('model_name', 'typeform/distilbert-base-uncased-mnli')

            if self.verbose:
                print(f"Loading model {model_name}...")

            self.classifier = pipeline(
                "zero-shot-classification",
                model=model_name,
                device=model_config.get('device', -1)  # -1 for CPU, 0 for GPU
            )

            self.labels = [
                f"addressing {self.ai_name} directly",
                f"talking about {self.ai_name}"
            ]

            if self.verbose:
                print("Model loaded successfully!")
        elif self.verbose:
            print("Using rule-based detection (model disabled)")

    def extract_last_sentences(self, text: str, n: int = 5) -> str:
        """
        Extract the last N sentences from the text buffer.

        Args:
            text: The full text buffer
            n: Number of sentences to extract (default: 5)

        Returns:
            The last N sentences joined together
        """
        if not sent_tokenize:
            # Fallback: return last 500 characters if NLTK not available
            return text[-500:] if len(text) > 500 else text

        sentences = sent_tokenize(text)
        last_n = sentences[-n:] if len(sentences) > n else sentences
        return " ".join(last_n)

    def is_message_for_ai(self, message: str, use_sentences: bool = True, n_sentences: int = 5) -> bool:
        """
        Determine if a message is directed at or about the AI assistant.

        Args:
            message: The message/buffer to analyze
            use_sentences: If True, extract last N sentences from message (default: True)
            n_sentences: Number of sentences to extract if use_sentences is True (default: 5)

        Returns:
            True if message is directed at AI, False otherwise
        """

        # Extract last N sentences if requested
        if use_sentences and sent_tokenize:
            analysis_text = self.extract_last_sentences(message, n_sentences)
        else:
            analysis_text = message

        text_lower = analysis_text.lower()

        # First check if AI name or any alias is mentioned at all
        name_found = any(name in text_lower for name in self.all_names)
        if not name_found:
            if self.verbose:
                print(f"\nBuffer: {message[:100]}..." if len(message) > 100 else f"\nBuffer: {message}")
                if use_sentences:
                    print(f"Analyzed text (last {n_sentences} sentences): {analysis_text}")
                print(f"AI name '{self.ai_name}' or aliases not found in text")
            return False

        # Rule-based detection
        # Check for mention patterns first (these override commanding)
        for pattern in self.mention_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                if self.verbose:
                    print(f"\nBuffer: {message[:100]}..." if len(message) > 100 else f"\nBuffer: {message}")
                    if use_sentences:
                        print(f"Analyzed text (last {n_sentences} sentences): {analysis_text}")
                    print(f"Matched mention pattern: {pattern}")
                return False

        # Check for command patterns
        for pattern in self.command_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                if self.verbose:
                    print(f"\nBuffer: {message[:100]}..." if len(message) > 100 else f"\nBuffer: {message}")
                    if use_sentences:
                        print(f"Analyzed text (last {n_sentences} sentences): {analysis_text}")
                    print(f"Matched command pattern: {pattern}")
                return True

        # If we have the model and no clear pattern match, use it
        if self.classifier is not None:
            result = self.classifier(analysis_text, self.labels)
            top_label = result['labels'][0]
            top_score = result['scores'][0]

            if self.verbose:
                print(f"\nBuffer: {message[:100]}..." if len(message) > 100 else f"\nBuffer: {message}")
                if use_sentences:
                    print(f"Analyzed text (last {n_sentences} sentences): {analysis_text}")
                print(f"No pattern match, using model")
                print(f"Top label: {top_label} (score: {top_score:.3f})")
                print(f"All results: {list(zip(result['labels'], result['scores']))}")

            is_commanding = top_label == f"addressing {self.ai_name} directly"
            is_confident = top_score >= self.threshold
            return is_commanding and is_confident

        # Default: if name is mentioned but no pattern matches and no model, be conservative
        if self.verbose:
            print(f"\nBuffer: {message[:100]}..." if len(message) > 100 else f"\nBuffer: {message}")
            if use_sentences:
                print(f"Analyzed text (last {n_sentences} sentences): {analysis_text}")
            print(f"No pattern match, defaulting to False")
        return False

    def close(self):
        """Clean up resources."""
        # Transformers pipeline handles cleanup automatically
        pass


def main():
    """Test the detector with sample messages."""

    detector = AIDetector()

    test_messages = [
        # Should trigger (commanding)
        "Jarvis, turn on the lights",
        "Hey Jarvis, what time is it?",
        "Jarvis can you help me with this?",
        "Okay Jarvis, start the music",

        # Should NOT trigger (mentioning)
        "Jarvis is a wonderful name",
        "I was talking to Jarvis yesterday",
        "I think Jarvis would like this",
        "Tell Jarvis I said hello",

        # Edge cases
        "The weather is nice today",
        "What do you think about this?",
    ]

    print("\n" + "=" * 60)
    print("Testing AI Detection (DistilBERT-MNLI)")
    print("=" * 60)

    for msg in test_messages:
        result = detector.is_message_for_ai(msg, use_sentences=False)
        status = "✓ TRIGGER" if result else "✗ IGNORE"
        print(f"\n{status}: {msg}")

    print("\n" + "=" * 60)

    detector.close()


if __name__ == "__main__":
    main()
