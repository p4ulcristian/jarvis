"""
Constants and magic values for JARVIS
Centralized location for hardcoded values, thresholds, and data structures
"""

# Transcription Filter Constants
# ==================================================

# Hallucination phrases to filter out
# NOTE: Only filter phrases that are clearly hallucinations, not common words
HALLUCINATION_PHRASES = {
    'thanks for watching',
    'please subscribe',
    'uh', 'um', 'ah', 'mm', 'hmm',
    '.', '...'
    # Removed: 'you', 'okay', 'ok', 'thank you' - these are real words!
}

# Word corrections for common misrecognitions
WORD_CORRECTIONS = {
    'jarve': 'Jarvis',
    'jarvy': 'Jarvis',
    'jarry': 'Jarvis',
    'jervis': 'Jarvis',
    'jarvie': 'Jarvis',
    'jarvey': 'Jarvis',
    'jadrice': 'Jarvis',
    'jobies': 'Jarvis',
    'jarbies': 'Jarvis',
    'jeremies': 'Jarvis',
}

# Transcription Processing Thresholds
# ==================================================

# Minimum text length to accept (characters)
MIN_TEXT_LENGTH = 2

# Maximum consecutive character repeats before flagging as hallucination
# Example: "Dohhhhhhhhh..." would be flagged if > MAX_CHAR_REPEATS
MAX_CHAR_REPEATS = 15

# Canary-1B Flash model constraints
MAX_CHUNK_DURATION_SECONDS = 30.0  # Model trained on <30s audio

# Speech Buffer Configuration
# ==================================================

# Minimum duration to accumulate before transcribing (seconds)
MIN_BUFFER_DURATION = 0.4  # Reduced for faster response

# Maximum duration to buffer before forcing transcription (seconds)
MAX_BUFFER_DURATION = 5.0  # Auto-flush to prevent crashes during continuous audio

# Number of silence chunks to wait before flushing buffer
SILENCE_CHUNKS_TO_FLUSH = 2  # 200ms of silence

# Audio Processing Constants
# ==================================================

# Valid sample rates for audio processing
VALID_SAMPLE_RATES = [8000, 16000, 22050, 44100, 48000]

# Audio energy calculation
SPEECH_AMPLITUDE_MAX = 2000.0  # Maximum amplitude for normalization

# Resampling ratios
RESAMPLE_RATIOS = {
    (48000, 16000): 3,  # 48kHz -> 16kHz: take every 3rd sample
    (44100, 16000): 3,  # 44.1kHz -> 16kHz: take every ~3rd sample
}

# UI Constants
# ==================================================

# Audio level visualization
UI_AUDIO_SEGMENTS = 5  # Number of segments in vertical bar meter
UI_AUDIO_LEVEL_THRESHOLDS = {
    'loud': 70,    # Level > 70%: loud (amber warning)
    'active': 40,  # Level > 40%: active (bright green)
    'talking': 10, # Level > 10%: talking (light green)
    'idle': 0      # Level <= 10%: idle (dim green)
}

# Pip-Boy Green Monochrome Theme Colors
UI_COLORS = {
    'background': '#0a0e0a',
    'panel_bg': '#0d1409',
    'border': '#00ff00',
    'bright_green': '#00ff00',
    'light_green': '#33ff33',
    'dim_green': '#226622',
    'amber_warning': '#ffaa00',
    'error_red': '#ff6600',
    'black': '#000000'
}

# UI Status Icons
UI_ICONS = {
    'loud': '[!]',
    'active': '[*]',
    'talking': '[>]',
    'idle': '[-]',
    'debug': '[?]',
    'info': '[i]',
    'warning': '[!]',
    'error': '[X]',
    'critical': '[!!]'
}

# Keyboard Event Constants
# ==================================================

# Keyboard event types
KEYBOARD_EVENTS = {
    'PTT_START': 'PTT_START',      # Push-to-talk started
    'PTT_STOP': 'PTT_STOP',        # Push-to-talk stopped (trigger typing)
    'PTT_CANCEL': 'PTT_CANCEL'     # Push-to-talk cancelled (Ctrl+key combo)
}

# System Constants
# ==================================================

# Default paths
DEFAULT_PATHS = {
    'log_file': 'data/chat.txt',
    'improved_log_file': 'data/chat-revised.txt',
    'trigger_file': '/tmp/jarvis-type-trigger',
    'keyboard_event_file': '/tmp/jarvis-keyboard-events',
    'boost_words_file': 'config/boost_words.txt'
}

# Export directory
EXPORT_DIR = '~/jarvis_exports'

# Threading & Process Management
# ==================================================

# Default timeout values (seconds)
DEFAULT_TIMEOUTS = {
    'keyboard_listener_startup': 3.0,
    'keyboard_listener_shutdown': 2.0,
    'component_shutdown': 5.0,
    'thread_join': 2.0
}

# Retry configuration
DEFAULT_RETRY_CONFIG = {
    'max_retries': 3,
    'initial_delay': 1.0,
    'max_delay': 10.0,
    'exponential_base': 2.0
}

# Health check intervals (seconds)
HEALTH_CHECK_INTERVALS = {
    'audio_capture': 30.0,
    'model_inference': 60.0,
    'keyboard_listener': 15.0
}
