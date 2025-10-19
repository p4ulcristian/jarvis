# Claude Code Voice Integration

Voice-controlled coding with Claude Code in JARVIS.

## Overview

JARVIS now integrates with Claude Code SDK, allowing you to execute coding tasks using voice commands. Simply speak your trigger word (default: "jarvis") followed by your coding instruction, and Claude Code will execute it.

## Features

- **Voice-Activated Coding**: Speak natural language coding commands
- **Trigger Word Detection**: Automatically detects trigger words like "jarvis", "hey jarvis", etc.
- **Non-Blocking Execution**: Commands execute without blocking normal transcription
- **Configurable**: Customize trigger words, project path, and allowed tools
- **Logging**: Full command history and logging

## Installation

```bash
# Activate your virtual environment
source source-code/venv/bin/activate

# Install Claude Agent SDK
pip install claude-agent-sdk
```

The SDK is already added to `requirements.txt`.

## Configuration

Configure via environment variables in your `.env` file:

```bash
# Enable/disable Claude Code integration
ENABLE_CLAUDE_CODE=true

# Trigger words (comma-separated, case-insensitive)
CLAUDE_CODE_TRIGGER_WORDS=jarvis,hey jarvis,jarvis code

# Project path for Claude Code to work in
CLAUDE_CODE_PROJECT_PATH=/home/paul/Work/jarvis

# Tools Claude Code can use (comma-separated)
CLAUDE_CODE_ALLOWED_TOOLS=Read,Edit,Write,Bash,Grep,Glob
```

### Default Configuration

If not specified in `.env`, these defaults are used:

- **Enabled**: `true`
- **Trigger Words**: `jarvis`, `hey jarvis`, `jarvis code`
- **Project Path**: Current JARVIS project directory
- **Allowed Tools**: `Read`, `Edit`, `Write`, `Bash`, `Grep`, `Glob`

## Usage

### Basic Usage

1. **Hold Ctrl** (PTT - Push-to-Talk)
2. **Speak**: "jarvis add error handling to the API"
3. **Release Ctrl**
4. Claude Code executes your command!

### Example Voice Commands

```
"jarvis add error handling to the transcription module"
"hey jarvis fix the bug in main.py"
"jarvis create a new function for database queries"
"jarvis refactor the audio processing code"
"jarvis add type hints to all functions in core/config.py"
"jarvis generate unit tests for the keyboard typer"
```

### How It Works

1. **Voice Input**: You speak into the microphone
2. **Transcription**: NVIDIA Canary-1B Flash transcribes your speech
3. **Trigger Detection**: System checks for trigger words
4. **Command Extraction**: Extracts the command after the trigger word
5. **Claude Code Execution**: Sends command to Claude Code SDK
6. **Code Changes**: Claude Code makes the requested changes

### Non-Trigger Text

If your transcription doesn't contain a trigger word, it works normally - the text is pasted into your active window via clipboard.

Example:
- "jarvis fix the bug" → Claude Code executes
- "hello world" → Text is pasted normally

## Architecture

### Components

1. **`claude_code_handler.py`**: Core handler for trigger detection and command execution
2. **`jarvis_service.py`**: Integration point in main service
3. **`config.py`**: Configuration management

### Flow

```
Voice Input → Transcription → Trigger Detection
                                     ↓
                          Yes ←─ Contains Trigger? ─→ No
                          ↓                           ↓
                   Claude Code Execution      Normal Paste
                          ↓
                    Code Changes Made
```

### Trigger Detection Algorithm

1. Converts transcribed text to lowercase
2. Checks if text starts with any trigger word (longest match first)
3. Extracts command text after trigger word
4. Removes leading punctuation from command
5. Returns command or None

## Advanced Usage

### Custom Trigger Words

Add your own trigger words in `.env`:

```bash
CLAUDE_CODE_TRIGGER_WORDS=code assistant,ai code,assistant
```

Now you can say:
- "code assistant refactor this function"
- "ai code add tests"

### Restricting Tools

For safety, limit which tools Claude Code can use:

```bash
# Only allow reading and editing (no bash, no writes)
CLAUDE_CODE_ALLOWED_TOOLS=Read,Edit
```

### Disabling Claude Code

Temporarily disable without uninstalling:

```bash
ENABLE_CLAUDE_CODE=false
```

### Command History

Access command history programmatically:

```python
from services.claude_code_handler import ClaudeCodeHandler

handler = ClaudeCodeHandler()
history = handler.get_history(limit=10)

for command, response in history:
    print(f"Command: {command}")
    print(f"Response: {response[:100]}...")
```

## Troubleshooting

### "Claude Code integration disabled"

**Problem**: SDK not installed

**Solution**:
```bash
source source-code/venv/bin/activate
pip install claude-agent-sdk
```

### "No trigger detected"

**Problem**: Trigger word not recognized

**Solutions**:
1. Check your trigger words in `.env`
2. Ensure you're saying the trigger word at the START of your command
3. Check transcription accuracy (maybe Canary misheard the trigger word)

### "Command failed"

**Problem**: Claude Code couldn't execute the command

**Solutions**:
1. Check logs in terminal for detailed error
2. Verify `CLAUDE_CODE_PROJECT_PATH` is correct
3. Ensure you have necessary permissions
4. Check if requested files exist

### Commands execute but no changes

**Problem**: Tools may be restricted

**Solution**:
```bash
# Ensure Edit and Write are enabled
CLAUDE_CODE_ALLOWED_TOOLS=Read,Edit,Write,Bash,Grep,Glob
```

## Examples

### Example 1: Add Error Handling

**Voice**: "jarvis add try-except blocks to the audio capture module"

**Result**: Claude Code reads `core/audio.py` and adds appropriate error handling

### Example 2: Generate Tests

**Voice**: "hey jarvis create unit tests for the transcription worker"

**Result**: Claude Code creates new test file with comprehensive tests

### Example 3: Fix Bug

**Voice**: "jarvis fix the bug in keyboard listener where events aren't cleaned up"

**Result**: Claude Code reads code, identifies the issue, and fixes it

### Example 4: Refactor

**Voice**: "jarvis refactor the config class to use dataclasses"

**Result**: Claude Code converts Config class to use Python dataclasses

## Safety

### Built-in Safety Features

1. **Trigger Word Required**: Commands only execute with explicit trigger word
2. **Tool Restrictions**: Control which tools Claude Code can use
3. **Project Scope**: Claude Code only operates in specified project path
4. **Logging**: All commands logged for audit trail
5. **Error Handling**: Failures don't crash the system

### Best Practices

1. **Review Changes**: Always review code changes before committing
2. **Test First**: Test integration on non-critical code first
3. **Limit Tools**: Start with Read/Edit only, add Write/Bash as needed
4. **Use Version Control**: Always have git backup before testing
5. **Monitor Logs**: Watch logs for unexpected behavior

## Performance

- **Trigger Detection**: < 1ms (regex-based)
- **Command Execution**: Depends on complexity (typically 2-30 seconds)
- **Non-Blocking**: Normal transcription continues during execution

## Limitations

1. **Synchronous Execution**: Commands execute one at a time
2. **No Streaming Output**: Command output available only after completion
3. **No Interactive Commands**: Cannot handle commands requiring user input
4. **Project-Scoped**: Only works within configured project path

## Future Enhancements

Potential improvements:

- [ ] Async command execution in background thread
- [ ] Streaming command output to UI
- [ ] Multiple project support
- [ ] Command confirmation before execution
- [ ] Undo/rollback functionality
- [ ] Voice feedback (TTS) for command status

## FAQ

### Q: Can I use different trigger words for different actions?

A: Currently all trigger words trigger the same action. Future versions may support action-specific triggers.

### Q: Does this work without internet?

A: Claude Code requires internet connection. The transcription (Canary-1B) works offline.

### Q: Can I disable specific tools temporarily?

A: Yes, edit `CLAUDE_CODE_ALLOWED_TOOLS` in `.env` and restart JARVIS.

### Q: How do I see what Claude Code is doing?

A: Check the terminal output - all actions are logged in real-time.

### Q: Can Claude Code access files outside the project?

A: No, Claude Code is restricted to `CLAUDE_CODE_PROJECT_PATH` and subdirectories.

## Support

For issues or questions:

1. Check logs: `tail -f data/jarvis.log`
2. Review configuration in `.env`
3. Test with simple command: "jarvis show me the files in the core directory"

## License

Same as JARVIS project license.
