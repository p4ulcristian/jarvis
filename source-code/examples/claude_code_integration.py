#!/usr/bin/env python3
"""
Example: Using Claude Code SDK with JARVIS
Shows how to programmatically use Claude Code for coding tasks
"""

import asyncio
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeCodeOptions,
    tool,
    create_sdk_mcp_server,
    HookMatcher
)


# Example 1: Simple Query
async def simple_example():
    """Basic usage - one-shot query"""
    print("=== Simple Query Example ===")

    options = ClaudeCodeOptions(
        cwd="/home/paul/Work/jarvis",
        allowed_tools=["Read", "Edit", "Grep", "Glob"]
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query("Show me the structure of the transcription module")

        async for msg in client.receive_response():
            print(f"Response: {msg}")


# Example 2: Custom Tools for JARVIS
@tool(
    name="get_transcription_stats",
    description="Get statistics about recent transcriptions",
    input_schema={}
)
async def get_transcription_stats(args):
    """Custom tool: Return transcription statistics"""
    # This is a mock - you'd implement real stats
    stats = {
        "total_transcriptions": 150,
        "avg_confidence": 0.92,
        "most_used_commands": ["open file", "search code", "run tests"]
    }

    return {
        "content": [
            {"type": "text", "text": f"Transcription Stats:\n{stats}"}
        ]
    }


@tool(
    name="voice_command_execute",
    description="Execute a voice command in JARVIS",
    input_schema={"command": str}
)
async def voice_command_execute(args):
    """Custom tool: Execute voice commands"""
    command = args["command"]

    # Mock execution - you'd integrate with your actual voice command system
    result = f"Executed voice command: {command}"

    return {
        "content": [
            {"type": "text", "text": result}
        ]
    }


async def custom_tools_example():
    """Example with custom JARVIS-specific tools"""
    print("\n=== Custom Tools Example ===")

    # Create MCP server with your tools
    server = create_sdk_mcp_server(
        name="jarvis_tools",
        version="1.0.0",
        tools=[get_transcription_stats, voice_command_execute]
    )

    options = ClaudeCodeOptions(
        cwd="/home/paul/Work/jarvis",
        allowed_tools=[
            "Read", "Edit", "Bash",
            "mcp__jarvis_tools__get_transcription_stats",
            "mcp__jarvis_tools__voice_command_execute"
        ],
        mcp_servers={"jarvis_tools": server}
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            "Get transcription stats and suggest improvements to the voice command system"
        )

        async for msg in client.receive_response():
            print(f"Response: {msg}")


# Example 3: Safety Hooks
async def safety_check_hook(input_data, tool_use_id, context):
    """Hook to validate bash commands before execution"""
    tool_name = input_data["tool_name"]

    if tool_name != "Bash":
        return {}

    command = input_data["tool_input"].get("command", "")

    # Block dangerous operations on production files
    dangerous = ["rm -rf", "sudo", "> /dev/"]

    for pattern in dangerous:
        if pattern in command:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Blocked dangerous command: {pattern}"
                }
            }

    print(f"[SAFETY] Allowing command: {command}")
    return {}


async def hooks_example():
    """Example with safety hooks"""
    print("\n=== Hooks Example ===")

    options = ClaudeCodeOptions(
        cwd="/home/paul/Work/jarvis",
        allowed_tools=["Read", "Bash"],
        hooks={
            "PreToolUse": [
                HookMatcher(matcher="Bash", hooks=[safety_check_hook])
            ]
        }
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query("List the python files in the source-code directory")

        async for msg in client.receive_response():
            print(f"Response: {msg}")


# Example 4: Real-world use case - Code Generation from Voice
class VoiceToCodeAgent:
    """Agent that converts voice descriptions to code using Claude Code"""

    def __init__(self, project_path: str):
        self.project_path = project_path

    async def generate_code_from_voice(self, voice_transcription: str):
        """Convert a voice description into actual code"""
        print(f"\n=== Voice Input: {voice_transcription} ===")

        options = ClaudeCodeOptions(
            cwd=self.project_path,
            allowed_tools=["Read", "Edit", "Write", "Bash", "Grep", "Glob"]
        )

        async with ClaudeSDKClient(options=options) as client:
            # Convert natural language to code task
            prompt = f"""
            Voice command transcription: "{voice_transcription}"

            Interpret this voice command and implement it in the codebase.
            """

            await client.query(prompt)

            async for msg in client.receive_response():
                print(f"Action: {msg}")


async def voice_to_code_example():
    """Example: Voice-driven coding"""
    agent = VoiceToCodeAgent("/home/paul/Work/jarvis")

    # Simulate voice inputs
    voice_inputs = [
        "Add a function to calculate the average transcription confidence score",
        "Create a helper to format timestamps in the transcription output",
    ]

    for voice_input in voice_inputs:
        await agent.generate_code_from_voice(voice_input)
        await asyncio.sleep(1)  # Rate limiting


# Main
async def main():
    """Run all examples"""
    print("Claude Code SDK Integration Examples for JARVIS\n")

    # Run examples (comment out the ones you don't want to run)
    await simple_example()
    # await custom_tools_example()
    # await hooks_example()
    # await voice_to_code_example()


if __name__ == "__main__":
    asyncio.run(main())
