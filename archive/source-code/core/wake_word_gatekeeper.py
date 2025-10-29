#!/usr/bin/env python3
"""
Wake Word Gatekeeper
Enforces strict rules for conversation activation and transcription
"""
import logging
import time
from enum import Enum
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """Conversation states"""
    IDLE = "idle"  # Not in conversation, only looking for wake word
    ACTIVATED = "activated"  # Wake word detected, acknowledging
    LISTENING = "listening"  # Recording user speech
    PROCESSING = "processing"  # AI thinking
    RESPONDING = "responding"  # TTS playing
    IN_CONVERSATION = "in_conversation"  # Active conversation, no wake word needed


@dataclass
class GatekeeperConfig:
    """Gatekeeper configuration"""
    wake_word_timeout: float = 10.0  # Seconds after wake word before returning to IDLE
    conversation_timeout: float = 15.0  # Seconds of silence before ending conversation
    max_conversation_duration: float = 300.0  # Max conversation length (5 minutes)
    require_wake_word_first_time: bool = True  # Must say wake word before first interaction


class WakeWordGatekeeper:
    """
    Wake Word Gatekeeper

    Enforces strict conversation rules:
    1. Never transcribe speech without wake word detection first
    2. After wake word, enter conversation mode
    3. In conversation mode, allow follow-up questions without wake word
    4. Return to IDLE after timeout or explicit end command
    5. While in IDLE, ignore ALL speech (movies, music, background)
    """

    def __init__(self, config: GatekeeperConfig = None):
        """
        Initialize gatekeeper

        Args:
            config: Gatekeeper configuration
        """
        self.config = config or GatekeeperConfig()

        # State tracking
        self.state = ConversationState.IDLE
        self.last_wake_word_time = 0.0
        self.last_activity_time = 0.0
        self.conversation_start_time = 0.0

        # Statistics
        self.wake_word_count = 0
        self.total_conversations = 0
        self.rejected_utterances = 0

        logger.info(
            f"Gatekeeper initialized: wake_timeout={self.config.wake_word_timeout}s, "
            f"conv_timeout={self.config.conversation_timeout}s"
        )

    def on_wake_word_detected(self) -> bool:
        """
        Called when wake word is detected

        Returns:
            True if wake word accepted
        """
        current_time = time.time()

        # Always accept wake word
        self.wake_word_count += 1
        self.last_wake_word_time = current_time
        self.last_activity_time = current_time

        # Transition state
        old_state = self.state

        if self.state == ConversationState.IDLE:
            # Start new conversation
            self.state = ConversationState.ACTIVATED
            self.conversation_start_time = current_time
            self.total_conversations += 1

            logger.info(f"Wake word detected - activating conversation #{self.total_conversations}")

        elif self.state == ConversationState.IN_CONVERSATION:
            # Already in conversation - wake word resets timeout
            logger.debug("Wake word detected during conversation - resetting timeout")
            self.state = ConversationState.ACTIVATED

        elif self.state == ConversationState.RESPONDING:
            # User interrupted assistant
            logger.info("Wake word during response - user interrupting")
            self.state = ConversationState.ACTIVATED

        else:
            # Other states - reset to activated
            self.state = ConversationState.ACTIVATED

        return True

    def should_transcribe(self) -> tuple[bool, str]:
        """
        Check if speech should be transcribed

        Returns:
            Tuple of (should_transcribe: bool, reason: str)
        """
        current_time = time.time()

        # Check timeouts
        self._check_timeouts(current_time)

        # IDLE state - only wake word detection, NO transcription
        if self.state == ConversationState.IDLE:
            self.rejected_utterances += 1
            return False, "idle_no_wake_word"

        # ACTIVATED - ready to transcribe
        if self.state == ConversationState.ACTIVATED:
            return True, "activated"

        # LISTENING - actively recording
        if self.state == ConversationState.LISTENING:
            return True, "listening"

        # IN_CONVERSATION - follow-up questions allowed
        if self.state == ConversationState.IN_CONVERSATION:
            return True, "in_conversation"

        # PROCESSING or RESPONDING - don't transcribe
        if self.state in (ConversationState.PROCESSING, ConversationState.RESPONDING):
            return False, f"busy_{self.state.value}"

        # Default: don't transcribe
        return False, "unknown_state"

    def start_listening(self) -> None:
        """Transition to LISTENING state"""
        if self.state == ConversationState.ACTIVATED:
            self.state = ConversationState.LISTENING
            self.last_activity_time = time.time()
            logger.debug("State: LISTENING")

    def start_processing(self) -> None:
        """Transition to PROCESSING state"""
        if self.state in (ConversationState.LISTENING, ConversationState.ACTIVATED):
            self.state = ConversationState.PROCESSING
            self.last_activity_time = time.time()
            logger.debug("State: PROCESSING")

    def start_responding(self) -> None:
        """Transition to RESPONDING state"""
        if self.state == ConversationState.PROCESSING:
            self.state = ConversationState.RESPONDING
            self.last_activity_time = time.time()
            logger.debug("State: RESPONDING")

    def finish_response(self) -> None:
        """Called when TTS finishes - enter IN_CONVERSATION mode"""
        if self.state == ConversationState.RESPONDING:
            self.state = ConversationState.IN_CONVERSATION
            self.last_activity_time = time.time()
            logger.debug("State: IN_CONVERSATION (ready for follow-up)")

    def end_conversation(self, reason: str = "user_request") -> None:
        """
        End conversation and return to IDLE

        Args:
            reason: Reason for ending
        """
        logger.info(f"Ending conversation: {reason}")

        # Calculate conversation duration
        if self.conversation_start_time > 0:
            duration = time.time() - self.conversation_start_time
            logger.info(f"Conversation duration: {duration:.1f}s")

        self.state = ConversationState.IDLE
        self.last_activity_time = 0.0
        self.conversation_start_time = 0.0

    def _check_timeouts(self, current_time: float) -> None:
        """Check for various timeouts"""

        # Not in conversation - no timeouts to check
        if self.state == ConversationState.IDLE:
            return

        # Check conversation duration limit
        if self.conversation_start_time > 0:
            conversation_duration = current_time - self.conversation_start_time
            if conversation_duration > self.config.max_conversation_duration:
                logger.warning(f"Max conversation duration reached: {conversation_duration:.0f}s")
                self.end_conversation("max_duration")
                return

        # Check inactivity timeout (in IN_CONVERSATION state)
        if self.state == ConversationState.IN_CONVERSATION:
            time_since_activity = current_time - self.last_activity_time
            if time_since_activity > self.config.conversation_timeout:
                logger.info(f"Conversation timeout: {time_since_activity:.1f}s of inactivity")
                self.end_conversation("inactivity_timeout")
                return

        # Check wake word timeout (for ACTIVATED state)
        if self.state == ConversationState.ACTIVATED:
            time_since_wake = current_time - self.last_wake_word_time
            if time_since_wake > self.config.wake_word_timeout:
                logger.info(f"Wake word timeout: {time_since_wake:.1f}s")
                self.end_conversation("wake_word_timeout")
                return

    def get_state(self) -> ConversationState:
        """Get current conversation state"""
        return self.state

    def is_in_conversation(self) -> bool:
        """Check if currently in an active conversation"""
        return self.state != ConversationState.IDLE

    def get_stats(self) -> dict:
        """Get gatekeeper statistics"""
        return {
            'state': self.state.value,
            'wake_word_count': self.wake_word_count,
            'total_conversations': self.total_conversations,
            'rejected_utterances': self.rejected_utterances,
            'is_in_conversation': self.is_in_conversation(),
            'conversation_duration': (
                time.time() - self.conversation_start_time
                if self.conversation_start_time > 0 else 0.0
            )
        }

    def reset(self) -> None:
        """Reset to IDLE state"""
        self.state = ConversationState.IDLE
        self.last_wake_word_time = 0.0
        self.last_activity_time = 0.0
        self.conversation_start_time = 0.0
        logger.info("Gatekeeper reset to IDLE")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    print("=== Wake Word Gatekeeper Test ===\n")

    # Create gatekeeper
    config = GatekeeperConfig(
        wake_word_timeout=10.0,
        conversation_timeout=15.0
    )
    gatekeeper = WakeWordGatekeeper(config)

    # Test conversation flow
    print("Initial state:", gatekeeper.get_state())
    print()

    # Test 1: Try to transcribe without wake word (should fail)
    print("Test 1: Transcribe without wake word")
    should, reason = gatekeeper.should_transcribe()
    print(f"  Should transcribe: {should}, Reason: {reason}")
    print()

    # Test 2: Wake word detected
    print("Test 2: Wake word detected")
    gatekeeper.on_wake_word_detected()
    print(f"  State: {gatekeeper.get_state()}")
    should, reason = gatekeeper.should_transcribe()
    print(f"  Should transcribe: {should}, Reason: {reason}")
    print()

    # Test 3: Start listening
    print("Test 3: Start listening")
    gatekeeper.start_listening()
    print(f"  State: {gatekeeper.get_state()}")
    print()

    # Test 4: Process and respond
    print("Test 4: Processing and responding")
    gatekeeper.start_processing()
    print(f"  State: {gatekeeper.get_state()}")
    gatekeeper.start_responding()
    print(f"  State: {gatekeeper.get_state()}")
    gatekeeper.finish_response()
    print(f"  State: {gatekeeper.get_state()}")
    print()

    # Test 5: Follow-up question (no wake word needed)
    print("Test 5: Follow-up question")
    should, reason = gatekeeper.should_transcribe()
    print(f"  Should transcribe: {should}, Reason: {reason}")
    print()

    # Test 6: End conversation
    print("Test 6: End conversation")
    gatekeeper.end_conversation("user_request")
    print(f"  State: {gatekeeper.get_state()}")
    should, reason = gatekeeper.should_transcribe()
    print(f"  Should transcribe: {should}, Reason: {reason}")
    print()

    # Print stats
    print("Final stats:")
    stats = gatekeeper.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n✓ Test complete")
