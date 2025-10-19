#!/usr/bin/env python3
"""
Qwen Agent - Conversation Manager with Tool Support
Uses Qwen3:8b as the main conversational agent with Claude Code SDK as a tool
"""
import logging
import ollama
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Response from Qwen agent"""
    text: str  # Full response text
    short_text: str  # Shortened for TTS
    tool_used: Optional[str] = None  # "claude_code" if tool was called
    success: bool = True


class QwenAgent:
    """
    Qwen3-based conversational agent with Claude Code as a tool

    Architecture:
    - Qwen3:8b is the main conversation manager
    - Can answer questions directly
    - Can use Claude Code SDK as a tool for coding tasks
    """

    def __init__(
        self,
        model: str = "qwen3:8b",
        system_prompt: str = None,
        claude_handler = None,  # ClaudeCodeHandler instance
        max_history: int = 10,
        max_tts_sentences: int = 2
    ):
        """
        Initialize Qwen agent

        Args:
            model: Ollama model to use
            system_prompt: System prompt for personality
            claude_handler: ClaudeCodeHandler instance for tool calling
            max_history: Max conversation exchanges to remember
            max_tts_sentences: Max sentences for TTS output
        """
        self.model = model
        self.max_history = max_history
        self.max_tts_sentences = max_tts_sentences
        self.claude_handler = claude_handler

        # System prompt defines personality and tool usage
        self.system_prompt = system_prompt or (
            "You are Jarvis, a helpful voice assistant with coding capabilities.\n\n"
            "RESPONSE STYLE:\n"
            "- Keep verbal responses to 1-2 sentences for voice output\n"
            "- Be casual, friendly, and concise\n"
            "- For simple questions, answer directly\n\n"
            "CODING TASKS:\n"
            "- For coding/development tasks, use the execute_code_command tool\n"
            "- Examples: refactoring, adding features, fixing bugs, code analysis\n"
            "- After using the tool, summarize what was done in 1-2 sentences\n\n"
            "Remember: You're speaking to the user, so keep it conversational!"
        )

        # Conversation history
        self.messages: List[Dict[str, str]] = []

        # Define Claude Code as a tool
        self.tools = [{
            'type': 'function',
            'function': {
                'name': 'execute_code_command',
                'description': (
                    'Execute a coding task using Claude Code SDK. '
                    'Use this for: refactoring code, adding features, fixing bugs, '
                    'analyzing code, creating files, modifying code structure, etc.'
                ),
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'command': {
                            'type': 'string',
                            'description': 'The coding task to execute (e.g., "refactor the audio module to use async")'
                        }
                    },
                    'required': ['command']
                }
            }
        }]

        logger.info(f"Qwen Agent initialized: model={model}, claude_handler={'available' if claude_handler else 'disabled'}")

    def clear_history(self) -> None:
        """Clear conversation history"""
        self.messages = []
        logger.debug("Conversation history cleared")

    def _trim_history(self) -> None:
        """Trim conversation history to max_history exchanges"""
        # Keep system message + last N exchanges (user + assistant pairs)
        max_messages = (self.max_history * 2) + 1  # +1 for system message
        if len(self.messages) > max_messages:
            # Keep system message and recent exchanges
            self.messages = [self.messages[0]] + self.messages[-(self.max_history * 2):]

    async def chat(self, user_message: str) -> AgentResponse:
        """
        Process user message with Qwen3 agent

        Args:
            user_message: User's message/question

        Returns:
            Agent response
        """
        try:
            # Add user message to history
            self.messages.append({
                'role': 'user',
                'content': user_message
            })

            logger.info(f"Processing message: '{user_message}'")

            # Build messages with system prompt
            messages = [{'role': 'system', 'content': self.system_prompt}] + self.messages

            # Call Qwen3 with tools
            response = ollama.chat(
                model=self.model,
                messages=messages,
                tools=self.tools if self.claude_handler else None,
                stream=False  # For now, non-streaming for simplicity
            )

            # Check if tool was called
            message = response.get('message', {})
            tool_calls = message.get('tool_calls', [])

            if tool_calls:
                # Qwen3 wants to use Claude Code!
                logger.info("Tool call detected - executing Claude Code")
                return await self._handle_tool_call(tool_calls, messages)

            # Direct response (no tool used)
            assistant_message = message.get('content', '')

            # Add assistant response to history
            self.messages.append({
                'role': 'assistant',
                'content': assistant_message
            })

            # Trim history
            self._trim_history()

            # Extract short version for TTS
            short_text = self._extract_short_response(assistant_message)

            logger.debug(f"Direct response: {assistant_message}")

            return AgentResponse(
                text=assistant_message,
                short_text=short_text,
                tool_used=None,
                success=True
            )

        except Exception as e:
            logger.error(f"Error in chat: {e}", exc_info=True)
            return AgentResponse(
                text="Sorry, I encountered an error processing your request.",
                short_text="Sorry, I had an error.",
                tool_used=None,
                success=False
            )

    async def _handle_tool_call(
        self,
        tool_calls: List[Dict[str, Any]],
        messages: List[Dict[str, str]]
    ) -> AgentResponse:
        """
        Handle Claude Code tool call

        Args:
            tool_calls: List of tool calls from Qwen3
            messages: Current message history

        Returns:
            Agent response after tool execution
        """
        try:
            # Extract first tool call
            tool_call = tool_calls[0]
            function_name = tool_call.get('function', {}).get('name')
            arguments = tool_call.get('function', {}).get('arguments', {})

            if function_name != 'execute_code_command':
                logger.warning(f"Unknown function: {function_name}")
                return AgentResponse(
                    text="I tried to use an unknown tool.",
                    short_text="Sorry, tool error.",
                    success=False
                )

            # Extract command
            command = arguments.get('command', '')
            logger.info(f"Executing Claude Code command: '{command}'")

            # Execute via Claude Code handler
            if not self.claude_handler or not self.claude_handler.enabled:
                logger.warning("Claude Code handler not available")
                return AgentResponse(
                    text="I wanted to help with coding, but Claude Code isn't available.",
                    short_text="Code tools aren't available right now.",
                    success=False
                )

            # Execute the command
            success = await self.claude_handler.execute_command(command)

            # Prepare tool result
            tool_result = {
                'success': success,
                'message': f"Successfully executed: {command}" if success else f"Failed to execute: {command}"
            }

            # Add tool call to messages
            self.messages.append({
                'role': 'assistant',
                'content': '',
                'tool_calls': tool_calls
            })

            # Add tool result to messages
            messages_with_tool = messages + [
                {'role': 'assistant', 'content': '', 'tool_calls': tool_calls},
                {'role': 'tool', 'content': str(tool_result)}
            ]

            # Get Qwen3's final response after tool execution
            final_response = ollama.chat(
                model=self.model,
                messages=messages_with_tool,
                stream=False
            )

            final_message = final_response.get('message', {}).get('content', '')

            # Add final response to history
            self.messages.append({
                'role': 'assistant',
                'content': final_message
            })

            # Trim history
            self._trim_history()

            # Extract short version
            short_text = self._extract_short_response(final_message)

            logger.info(f"Tool execution complete: {final_message}")

            return AgentResponse(
                text=final_message,
                short_text=short_text,
                tool_used='claude_code',
                success=success
            )

        except Exception as e:
            logger.error(f"Error handling tool call: {e}", exc_info=True)
            return AgentResponse(
                text="I tried to help with coding but encountered an error.",
                short_text="Sorry, coding task failed.",
                tool_used='claude_code',
                success=False
            )

    def _extract_short_response(self, full_response: str) -> str:
        """
        Extract short version of response for TTS

        Args:
            full_response: Full response text

        Returns:
            Shortened response
        """
        if not full_response:
            return ""

        # Split into sentences
        import re
        sentences = re.split(r'[.!?]+', full_response)

        # Filter empty and take first N
        sentences = [s.strip() for s in sentences if s.strip()]
        short = '. '.join(sentences[:self.max_tts_sentences])

        # Add period if needed
        if short and not short.endswith(('.', '!', '?')):
            short += '.'

        return short

    def is_available(self) -> bool:
        """
        Check if Qwen agent is available

        Returns:
            True if Ollama server is reachable
        """
        try:
            ollama.list()
            return True
        except:
            return False


# Example usage
if __name__ == "__main__":
    import asyncio

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def test_agent():
        """Test the Qwen agent"""
        # Create agent (without Claude handler for testing)
        agent = QwenAgent()

        print("=== Testing Qwen Agent ===\n")

        # Test simple chat
        print("1. Simple question:")
        response = await agent.chat("What's 2+2?")
        print(f"   Full: {response.text}")
        print(f"   TTS:  {response.short_text}\n")

        # Test conversation history
        print("2. Follow-up question:")
        response = await agent.chat("And what's that times 3?")
        print(f"   Full: {response.text}")
        print(f"   TTS:  {response.short_text}\n")

        # Test coding request (will try to call tool)
        print("3. Coding request:")
        response = await agent.chat("Refactor the audio module to use async/await")
        print(f"   Full: {response.text}")
        print(f"   TTS:  {response.short_text}")
        print(f"   Tool: {response.tool_used}\n")

    asyncio.run(test_agent())
