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
        self.silence_threshold = self._get_int('SILENCE_THRESHOLD', 100)  # Increased from 10 to 100
        self.min_speech_ratio = self._get_float('MIN_SPEECH_RATIO', 0.01)  # Increased from 0.0001 to 0.01 (1%)
        self.frame_len = self._get_float('FRAME_LEN', 1.6)

        # Model Configuration
        self.model_name = self._get_str('MODEL_NAME', 'nvidia/canary-1b-flash')

        # Canary-specific Configuration
        self.canary_task = self._get_str('CANARY_TASK', 'asr')  # asr or ast (speech translation)
        self.canary_source_lang = self._get_str('CANARY_SOURCE_LANG', 'en')  # en, de, fr, es
        self.canary_target_lang = self._get_str('CANARY_TARGET_LANG', 'en')  # en, de, fr, es
        self.canary_pnc = self._get_str('CANARY_PNC', 'yes')  # yes/no for punctuation and capitalization
        self.canary_beam_size = self._get_int('CANARY_BEAM_SIZE', 1)  # 1 for greedy decoding (fastest)

        # Streaming Configuration
        self.streaming_chunk_size = self._get_int('STREAMING_CHUNK_SIZE', 8)  # Number of frames per chunk
        self.streaming_left_context = self._get_int('STREAMING_LEFT_CONTEXT', 32)  # Left context frames
        self.decoder_type = self._get_str('DECODER_TYPE', 'rnnt')  # 'rnnt' or 'ctc'

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

        # Chat Mode Configuration
        self.chat_model = self._get_str('CHAT_MODEL', 'qwen3:8b')
        self.wake_word = self._get_str('WAKE_WORD', 'jarvis')
        self.tts_personality = self._get_str('TTS_PERSONALITY', 'helpful and friendly')
        self.max_tts_sentences = self._get_int('MAX_TTS_SENTENCES', 2)
        self.chat_system_prompt = self._get_str('CHAT_SYSTEM_PROMPT',
            'You are Jarvis, a helpful voice assistant. '
            'Respond in 1-2 sentences maximum for voice output. '
            'Be casual, friendly, and concise.')
        self.enable_chat_mode = self._get_bool('ENABLE_CHAT_MODE', True)

        # Debug
        self.debug_mode = self._get_bool('DEBUG_MODE', False)

        # Terminal UI
        self.enable_ui = self._get_bool('ENABLE_UI', True)
        self.ui_refresh_rate = self._get_int('UI_REFRESH_RATE', 4)
        self.ui_log_history = self._get_int('UI_LOG_HISTORY', 50)

        # Keyboard & Typing
        self.typing_delay = self._get_float('TYPING_DELAY', 0.01)  # seconds between keystrokes
        self.paste_clipboard_delay = self._get_float('PASTE_CLIPBOARD_DELAY', 0.05)  # clipboard sync delay

        # Shutdown & Process Management
        self.shutdown_timeout = self._get_float('SHUTDOWN_TIMEOUT', 5.0)  # seconds per component
        self.process_startup_timeout = self._get_float('PROCESS_STARTUP_TIMEOUT', 3.0)  # keyboard listener startup
        self.graceful_shutdown_timeout = self._get_float('GRACEFUL_SHUTDOWN_TIMEOUT', 2.0)  # process termination

        # Error Recovery & Resilience
        self.audio_capture_max_retries = self._get_int('AUDIO_CAPTURE_MAX_RETRIES', 3)
        self.audio_capture_retry_delay = self._get_float('AUDIO_CAPTURE_RETRY_DELAY', 1.0)  # seconds
        self.transcription_max_retries = self._get_int('TRANSCRIPTION_MAX_RETRIES', 2)
        self.transcription_retry_delay = self._get_float('TRANSCRIPTION_RETRY_DELAY', 0.5)  # seconds
        self.enable_error_recovery = self._get_bool('ENABLE_ERROR_RECOVERY', True)

        # Health Checks
        self.enable_health_checks = self._get_bool('ENABLE_HEALTH_CHECKS', True)
        self.health_check_interval = self._get_float('HEALTH_CHECK_INTERVAL', 30.0)  # seconds
        self.health_check_audio_timeout = self._get_float('HEALTH_CHECK_AUDIO_TIMEOUT', 5.0)  # seconds

        # Monitoring
        self.enable_metrics = self._get_bool('ENABLE_METRICS', False)
        self.metrics_port = self._get_int('METRICS_PORT', 9090)

        # Claude Code Integration
        self.enable_claude_code = self._get_bool('ENABLE_CLAUDE_CODE', True)
        self.claude_code_trigger_words = self._get_str('CLAUDE_CODE_TRIGGER_WORDS', 'jarvis,hey jarvis,jarvis code').split(',')
        self.claude_code_project_path = self._get_str('CLAUDE_CODE_PROJECT_PATH', str(Path(__file__).parent.parent.parent))
        self.claude_code_allowed_tools = self._get_str('CLAUDE_CODE_ALLOWED_TOOLS', 'Read,Edit,Write,Bash,Grep,Glob').split(',')

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
