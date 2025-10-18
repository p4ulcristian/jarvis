"""
Configuration management for JARVIS
Loads settings from environment variables with sensible defaults
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


class Config:
    """Central configuration for JARVIS"""

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration

        Args:
            env_file: Path to .env file (defaults to .env in project root)
        """
        # Load .env file if it exists
        if env_file:
            load_dotenv(env_file)
        else:
            # Try to load from project root
            project_root = Path(__file__).parent.parent
            env_path = project_root / '.env'
            if env_path.exists():
                load_dotenv(env_path)

        # Feature Flags
        self.enable_microphone = self._get_bool('ENABLE_MICROPHONE', True)
        self.enable_model = self._get_bool('ENABLE_MODEL', True)
        self.enable_vad = self._get_bool('ENABLE_VAD', True)
        self.enable_ai_detection = self._get_bool('ENABLE_AI_DETECTION', False)
        self.enable_transcription = self._get_bool('ENABLE_TRANSCRIPTION', True)

        # Audio Configuration
        self.sample_rate = self._get_int('SAMPLE_RATE', 16000)
        self.chunk_size = self._get_int('CHUNK_SIZE', 1600)
        self.channels = 1  # Mono audio
        self.device_sample_rate = self._get_int('DEVICE_SAMPLE_RATE', 48000)

        # VAD Configuration
        self.silence_threshold = self._get_int('SILENCE_THRESHOLD', 10)
        self.min_speech_ratio = self._get_float('MIN_SPEECH_RATIO', 0.0001)
        self.frame_len = self._get_float('FRAME_LEN', 1.6)

        # Paths
        self.log_file = self._get_str('LOG_FILE', 'data/chat.txt')
        self.improved_log_file = self._get_str('IMPROVED_LOG_FILE', 'data/chat-revised.txt')
        self.trigger_file = self._get_str('TRIGGER_FILE', '/tmp/jarvis-type-trigger')
        self.keyboard_event_file = self._get_str('KEYBOARD_EVENT_FILE', '/tmp/jarvis-keyboard-events')
        self.boost_words_file = self._get_str('BOOST_WORDS_FILE', 'config/boost_words.txt')

        # AI Detection
        self.detection_cooldown = self._get_int('DETECTION_COOLDOWN', 5)
        self.buffer_duration = self._get_int('BUFFER_DURATION', 300)

        # API Keys
        self.openai_api_key = self._get_str('OPENAI_API_KEY', '')

        # Ollama Configuration
        self.ollama_url = self._get_str('OLLAMA_URL', 'http://localhost:11434/api/generate')
        self.ollama_model = self._get_str('OLLAMA_MODEL', 'qwen2.5:3b-instruct')

        # Debug
        self.debug_mode = self._get_bool('DEBUG_MODE', False)

        # Monitoring
        self.enable_metrics = self._get_bool('ENABLE_METRICS', False)
        self.metrics_port = self._get_int('METRICS_PORT', 9090)

    @staticmethod
    def _get_str(key: str, default: str) -> str:
        """Get string from environment"""
        return os.getenv(key, default)

    @staticmethod
    def _get_int(key: str, default: int) -> int:
        """Get integer from environment"""
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            return default

    @staticmethod
    def _get_float(key: str, default: float) -> float:
        """Get float from environment"""
        try:
            return float(os.getenv(key, str(default)))
        except ValueError:
            return default

    @staticmethod
    def _get_bool(key: str, default: bool) -> bool:
        """Get boolean from environment"""
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')

    def validate(self) -> list[str]:
        """
        Validate configuration and return list of errors

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check sample rates
        if self.sample_rate not in [8000, 16000, 22050, 44100, 48000]:
            errors.append(f"Invalid sample_rate: {self.sample_rate}")

        # Check paths exist (for required files)
        if self.enable_model and Path(self.boost_words_file).exists() is False:
            # Warning only, not an error
            pass

        return errors

    def __repr__(self) -> str:
        """String representation"""
        return f"Config(sample_rate={self.sample_rate}, debug_mode={self.debug_mode})"
