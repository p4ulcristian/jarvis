#!/usr/bin/env python3
"""
Speaker Recognition / Voice Identification
Identifies and filters audio to only respond to the enrolled user's voice
"""
import logging
import numpy as np
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
import pickle

logger = logging.getLogger(__name__)

# Try to import resemblyzer for speaker recognition
SPEAKER_REC_AVAILABLE = False
try:
    from resemblyzer import VoiceEncoder, preprocess_wav
    SPEAKER_REC_AVAILABLE = True
    logger.info("Speaker recognition available (resemblyzer)")
except ImportError:
    logger.warning("resemblyzer not installed - speaker recognition disabled")
    logger.warning("Install with: pip install resemblyzer")


@dataclass
class SpeakerProfile:
    """User's voice profile"""
    embedding: np.ndarray  # Voice embedding vector
    name: str = "user"
    threshold: float = 0.65  # Similarity threshold (0-1)


class SpeakerRecognition:
    """
    Speaker Recognition System

    Enrolls the user's voice and filters out non-matching voices.
    This prevents the assistant from responding to:
    - Movies/TV dialogue
    - Other people in the room
    - Music vocals
    - Radio/podcast voices
    """

    def __init__(
        self,
        profile_path: Optional[str] = None,
        similarity_threshold: float = 0.65,
        enabled: bool = True
    ):
        """
        Initialize speaker recognition

        Args:
            profile_path: Path to save/load user profile
            similarity_threshold: Min similarity to accept (0.0-1.0, default 0.65)
            enabled: Whether speaker recognition is enabled
        """
        self.enabled = enabled and SPEAKER_REC_AVAILABLE
        self.similarity_threshold = similarity_threshold
        self.profile_path = Path(profile_path) if profile_path else Path("data/user_voice_profile.pkl")

        self.encoder = None
        self.user_profile: Optional[SpeakerProfile] = None

        if not self.enabled:
            logger.warning("Speaker recognition disabled")
            return

        try:
            # Initialize voice encoder
            self.encoder = VoiceEncoder()
            logger.info("Voice encoder initialized")

            # Try to load existing profile
            if self.profile_path.exists():
                self.load_profile()
            else:
                logger.info(f"No voice profile found at {self.profile_path}")
                logger.info("User enrollment required")

        except Exception as e:
            logger.error(f"Failed to initialize speaker recognition: {e}", exc_info=True)
            self.enabled = False

    def enroll_user(
        self,
        audio_samples: List[np.ndarray],
        sample_rate: int = 16000,
        name: str = "user"
    ) -> bool:
        """
        Enroll user's voice from audio samples

        Args:
            audio_samples: List of audio chunks (float32, mono)
            sample_rate: Sample rate of audio
            name: User's name

        Returns:
            True if enrollment successful
        """
        if not self.enabled:
            logger.error("Speaker recognition not available")
            return False

        if not audio_samples:
            logger.error("No audio samples provided")
            return False

        logger.info(f"Enrolling user voice: {len(audio_samples)} samples, {sample_rate}Hz")

        try:
            embeddings = []

            for i, audio in enumerate(audio_samples):
                # Ensure audio is correct format
                if audio.dtype != np.float32:
                    audio = audio.astype(np.float32)

                # Resample if needed (resemblyzer expects 16kHz)
                if sample_rate != 16000:
                    from scipy import signal
                    audio = signal.resample(
                        audio,
                        int(len(audio) * 16000 / sample_rate)
                    ).astype(np.float32)

                # Preprocess (resemblyzer requires specific preprocessing)
                try:
                    # The preprocess_wav function expects audio in [-1, 1] range
                    audio_normalized = np.clip(audio, -1.0, 1.0)

                    # Get embedding
                    embedding = self.encoder.embed_utterance(audio_normalized)
                    embeddings.append(embedding)

                    logger.debug(f"Processed sample {i+1}/{len(audio_samples)}")

                except Exception as e:
                    logger.warning(f"Failed to process sample {i}: {e}")
                    continue

            if not embeddings:
                logger.error("No valid embeddings generated")
                return False

            # Average all embeddings to create user profile
            avg_embedding = np.mean(embeddings, axis=0)

            # Normalize
            avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)

            # Create profile
            self.user_profile = SpeakerProfile(
                embedding=avg_embedding,
                name=name,
                threshold=self.similarity_threshold
            )

            logger.info(f"User profile created: {len(embeddings)} samples averaged")

            # Save profile
            self.save_profile()

            return True

        except Exception as e:
            logger.error(f"Enrollment failed: {e}", exc_info=True)
            return False

    def is_user_speaking(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> bool:
        """
        Check if audio matches the enrolled user's voice

        Args:
            audio: Audio chunk to check (float32, mono)
            sample_rate: Sample rate

        Returns:
            True if voice matches user, False otherwise
        """
        if not self.enabled or self.user_profile is None:
            # No profile - accept all
            return True

        try:
            # Ensure correct format
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Resample if needed
            if sample_rate != 16000:
                from scipy import signal
                audio = signal.resample(
                    audio,
                    int(len(audio) * 16000 / sample_rate)
                ).astype(np.float32)

            # Normalize
            audio = np.clip(audio, -1.0, 1.0)

            # Get embedding
            embedding = self.encoder.embed_utterance(audio)
            embedding = embedding / np.linalg.norm(embedding)

            # Compare with user profile (cosine similarity)
            similarity = np.dot(embedding, self.user_profile.embedding)

            logger.debug(f"Voice similarity: {similarity:.3f} (threshold: {self.user_profile.threshold})")

            # Check if similarity exceeds threshold
            is_user = similarity >= self.user_profile.threshold

            if not is_user:
                logger.debug(f"Voice rejected: similarity {similarity:.3f} < {self.user_profile.threshold}")

            return is_user

        except Exception as e:
            logger.error(f"Speaker verification error: {e}", exc_info=True)
            # On error, accept (fail open)
            return True

    def get_voice_similarity(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> float:
        """
        Get similarity score for audio (0.0-1.0)

        Args:
            audio: Audio chunk
            sample_rate: Sample rate

        Returns:
            Similarity score (0.0-1.0)
        """
        if not self.enabled or self.user_profile is None:
            return 1.0

        try:
            # Ensure correct format
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Resample if needed
            if sample_rate != 16000:
                from scipy import signal
                audio = signal.resample(
                    audio,
                    int(len(audio) * 16000 / sample_rate)
                ).astype(np.float32)

            # Normalize
            audio = np.clip(audio, -1.0, 1.0)

            # Get embedding
            embedding = self.encoder.embed_utterance(audio)
            embedding = embedding / np.linalg.norm(embedding)

            # Cosine similarity
            similarity = np.dot(embedding, self.user_profile.embedding)

            return float(similarity)

        except Exception as e:
            logger.error(f"Similarity calculation error: {e}")
            return 1.0

    def save_profile(self) -> bool:
        """
        Save user profile to disk

        Returns:
            True if successful
        """
        if self.user_profile is None:
            logger.warning("No profile to save")
            return False

        try:
            # Create directory if needed
            self.profile_path.parent.mkdir(parents=True, exist_ok=True)

            # Save with pickle
            with open(self.profile_path, 'wb') as f:
                pickle.dump(self.user_profile, f)

            logger.info(f"Profile saved to {self.profile_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save profile: {e}")
            return False

    def load_profile(self) -> bool:
        """
        Load user profile from disk

        Returns:
            True if successful
        """
        if not self.profile_path.exists():
            logger.warning(f"Profile not found: {self.profile_path}")
            return False

        try:
            with open(self.profile_path, 'rb') as f:
                self.user_profile = pickle.load(f)

            logger.info(f"Profile loaded: {self.user_profile.name}")
            logger.info(f"Similarity threshold: {self.user_profile.threshold}")

            return True

        except Exception as e:
            logger.error(f"Failed to load profile: {e}")
            return False

    def delete_profile(self) -> bool:
        """Delete user profile"""
        try:
            if self.profile_path.exists():
                self.profile_path.unlink()
                logger.info("Profile deleted")

            self.user_profile = None
            return True

        except Exception as e:
            logger.error(f"Failed to delete profile: {e}")
            return False

    def is_enrolled(self) -> bool:
        """Check if user is enrolled"""
        return self.user_profile is not None


# Example usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=== Speaker Recognition Test ===\n")

    if not SPEAKER_REC_AVAILABLE:
        print("⚠️  resemblyzer not installed")
        print("Install with: pip install resemblyzer")
        exit(1)

    # Create speaker recognition system
    sr = SpeakerRecognition(
        profile_path="data/test_voice_profile.pkl",
        similarity_threshold=0.65
    )

    # Generate synthetic voice samples for testing
    print("Generating synthetic test data...")

    sample_rate = 16000
    duration = 1.0

    # Create several "voice" samples (just sine waves for demo)
    user_samples = []
    for freq in [200, 220, 240]:  # Simulate user voice variations
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = np.sin(2 * np.pi * freq * t).astype(np.float32) * 0.5
        user_samples.append(audio)

    # Enroll user
    print("\nEnrolling user voice...")
    if sr.enroll_user(user_samples, sample_rate, name="TestUser"):
        print("✓ Enrollment successful\n")
    else:
        print("✗ Enrollment failed")
        exit(1)

    # Test with matching voice
    print("Testing with matching voice...")
    t = np.linspace(0, duration, int(sample_rate * duration))
    test_matching = np.sin(2 * np.pi * 210 * t).astype(np.float32) * 0.5

    similarity = sr.get_voice_similarity(test_matching, sample_rate)
    is_user = sr.is_user_speaking(test_matching, sample_rate)
    print(f"  Similarity: {similarity:.3f}")
    print(f"  Recognized as user: {is_user}\n")

    # Test with non-matching voice
    print("Testing with non-matching voice...")
    test_different = np.sin(2 * np.pi * 500 * t).astype(np.float32) * 0.5

    similarity = sr.get_voice_similarity(test_different, sample_rate)
    is_user = sr.is_user_speaking(test_different, sample_rate)
    print(f"  Similarity: {similarity:.3f}")
    print(f"  Recognized as user: {is_user}\n")

    print("✓ Test complete")
