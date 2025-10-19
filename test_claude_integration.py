#!/usr/bin/env python3
"""
Test Claude Code Integration
Quick test to verify trigger detection and setup
"""
import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Test imports
print("Testing Claude Code integration...\n")

print("1. Testing imports...")
sys.path.insert(0, 'source-code')

try:
    from services.claude_code_handler import ClaudeCodeHandler
    print("✓ claude_code_handler imported successfully")
except ImportError as e:
    print(f"✗ Failed to import claude_code_handler: {e}")
    sys.exit(1)

try:
    from core.config import Config
    print("✓ Config imported successfully")
except ImportError as e:
    print(f"✗ Failed to import Config: {e}")
    sys.exit(1)

print("\n2. Testing configuration...")
config = Config()
print(f"✓ Config loaded")
print(f"  - Claude Code enabled: {config.enable_claude_code}")
print(f"  - Trigger words: {config.claude_code_trigger_words}")
print(f"  - Project path: {config.claude_code_project_path}")
print(f"  - Allowed tools: {config.claude_code_allowed_tools}")

print("\n3. Testing ClaudeCodeHandler initialization...")
try:
    handler = ClaudeCodeHandler(
        trigger_words=config.claude_code_trigger_words,
        project_path=config.claude_code_project_path,
        allowed_tools=config.claude_code_allowed_tools,
        enabled=config.enable_claude_code
    )
    print(f"✓ Handler initialized")
    print(f"  - Enabled: {handler.enabled}")
    print(f"  - Trigger words: {handler.trigger_words}")
except Exception as e:
    print(f"✗ Failed to initialize handler: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n4. Testing trigger detection...")
test_cases = [
    ("jarvis add error handling to the API", True),
    ("hey jarvis fix the bug in main.py", True),
    ("jarvis, create a new function", True),
    ("just some regular text", False),
    ("JARVIS refactor the code", True),  # Case insensitive
    ("this is not a jarvis command in the middle", False),  # Must be at start
]

all_passed = True
for text, should_detect in test_cases:
    command = handler.detect_trigger(text)
    detected = command is not None

    if detected == should_detect:
        status = "✓"
        if detected:
            print(f"{status} '{text}' → Command: '{command}'")
        else:
            print(f"{status} '{text}' → No trigger (expected)")
    else:
        status = "✗"
        all_passed = False
        print(f"{status} '{text}' → Expected trigger={should_detect}, got {detected}")

if not all_passed:
    print("\n✗ Some trigger detection tests failed")
    sys.exit(1)

print("\n" + "="*60)
print("✓ ALL TESTS PASSED!")
print("="*60)
print("\nClaude Code integration is ready to use!")
print("\nNext steps:")
print("1. Make sure claude-agent-sdk is installed: pip install claude-agent-sdk")
print("2. Run JARVIS and try saying: 'jarvis show me the core directory structure'")
print("3. Check docs/CLAUDE_CODE_INTEGRATION.md for full documentation")
