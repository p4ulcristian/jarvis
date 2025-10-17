#!/home/paul/Work/jarvis/ai-detector/venv/bin/python
"""
CLI wrapper for AI Detector - accepts text and returns YES/NO.
"""

import sys
import os
from ai_detector import AIDetector


def main():
    if len(sys.argv) < 2:
        print("Usage: ai_detector_cli.py <text>", file=sys.stderr)
        sys.exit(1)

    # Get text from command line
    text = sys.argv[1]

    # Initialize detector
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    detector = AIDetector(config_path=config_path)

    # Check if message is for AI
    result = detector.is_message_for_ai(text, use_sentences=True, n_sentences=5)

    # Output YES or NO
    print("YES" if result else "NO")

    # Exit with appropriate code
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
