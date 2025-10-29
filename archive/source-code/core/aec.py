#!/usr/bin/env python3
"""
Acoustic Echo Cancellation (AEC)
Removes echo from microphone input using system audio as reference
"""
import logging
import numpy as np
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import AEC libraries (graceful degradation)
AEC_AVAILABLE = False
AEC_ENGINE = None

try:
    from speexdsp import EchoCanceller
    AEC_ENGINE = 'speex'
    AEC_AVAILABLE = True
    logger.info("Using Speex DSP for AEC")
except ImportError:
    try:
        # Alternative: webrtc-noise-gain
        import webrtc_audio_processing as webrtc
        AEC_ENGINE = 'webrtc'
        AEC_AVAILABLE = True
        logger.info("Using WebRTC for AEC")
    except ImportError:
        logger.warning("No AEC library available - install speexdsp-python or webrtc-noise-gain")
        logger.warning("Echo cancellation will be disabled")


@dataclass
class AECConfig:
    """AEC configuration"""
    sample_rate: int = 16000
    frame_size: int = 160  # 10ms at 16kHz
    filter_length: int = 1600  # 100ms at 16kHz (typical echo delay)
    enabled: bool = True


class AdaptiveAEC:
    """
    Adaptive Acoustic Echo Cancellation

    Removes echo from microphone input by subtracting the reference signal
    (system audio output) from the microphone input.

    This allows the assistant to:
    - Hear only your voice, not its own TTS
    - Ignore movies, music, and other system audio
    - Work in any audio environment
    """

    def __init__(self, config: AECConfig = None):
        """
        Initialize AEC

        Args:
            config: AEC configuration
        """
        self.config = config or AECConfig()
        self.enabled = self.config.enabled and AEC_AVAILABLE

        self.echo_canceller = None

        if not self.enabled:
            logger.warning("AEC disabled - echo cancellation will not work")
            logger.warning("Install: pip install speexdsp-python")
            return

        try:
            if AEC_ENGINE == 'speex':
                # SpeexDSP echo canceller
                self.echo_canceller = EchoCanceller.create(
                    frame_size=self.config.frame_size,
                    filter_length=self.config.filter_length,
                    sample_rate=self.config.sample_rate
                )
                logger.info(
                    f"Speex AEC initialized: frame={self.config.frame_size}, "
                    f"filter={self.config.filter_length}, rate={self.config.sample_rate}Hz"
                )

            elif AEC_ENGINE == 'webrtc':
                # WebRTC audio processing
                self.echo_canceller = webrtc.AudioProcessing()
                self.echo_canceller.set_sample_rate_hz(self.config.sample_rate)
                self.echo_canceller.set_stream_delay_ms(0)
                self.echo_canceller.enable_echo_cancellation(True)
                logger.info(f"WebRTC AEC initialized: rate={self.config.sample_rate}Hz")

            self.enabled = True

        except Exception as e:
            logger.error(f"Failed to initialize AEC: {e}", exc_info=True)
            self.enabled = False

    def process(
        self,
        mic_input: np.ndarray,
        reference_signal: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Process audio frame to remove echo

        Args:
            mic_input: Microphone input (user voice + echo)
            reference_signal: System audio output (what's playing on speakers)
                            If None, no echo cancellation is performed

        Returns:
            Cleaned audio (echo removed)
        """
        if not self.enabled or reference_signal is None:
            # AEC disabled or no reference - return original
            return mic_input

        if not self.echo_canceller:
            return mic_input

        try:
            # Ensure both signals are same length
            min_len = min(len(mic_input), len(reference_signal))
            mic = mic_input[:min_len]
            ref = reference_signal[:min_len]

            if AEC_ENGINE == 'speex':
                # Speex expects int16 format
                mic_int16 = (mic * 32767).astype(np.int16)
                ref_int16 = (ref * 32767).astype(np.int16)

                # Process in frames
                output_frames = []
                frame_size = self.config.frame_size

                for i in range(0, len(mic_int16) - frame_size, frame_size):
                    mic_frame = mic_int16[i:i+frame_size]
                    ref_frame = ref_int16[i:i+frame_size]

                    # Echo cancellation
                    cleaned_frame = self.echo_canceller.process(
                        input_frame=mic_frame,
                        echo_frame=ref_frame
                    )

                    output_frames.append(cleaned_frame)

                # Concatenate frames and convert back to float32
                if output_frames:
                    output = np.concatenate(output_frames)
                    output_float = output.astype(np.float32) / 32767.0
                    return output_float
                else:
                    return mic

            elif AEC_ENGINE == 'webrtc':
                # WebRTC processing
                # Convert to int16
                mic_int16 = (mic * 32767).astype(np.int16)
                ref_int16 = (ref * 32767).astype(np.int16)

                # Process
                self.echo_canceller.process_stream(
                    input_frame=mic_int16,
                    output_frame=mic_int16,  # In-place processing
                    echo_frame=ref_int16,
                    delay_ms=0
                )

                # Convert back
                output_float = mic_int16.astype(np.float32) / 32767.0
                return output_float

            else:
                return mic

        except Exception as e:
            logger.error(f"AEC processing error: {e}", exc_info=True)
            # On error, return original signal
            return mic_input

    def reset(self) -> None:
        """Reset AEC state"""
        if not self.enabled or not self.echo_canceller:
            return

        try:
            if AEC_ENGINE == 'speex':
                # Recreate canceller
                self.echo_canceller = EchoCanceller.create(
                    frame_size=self.config.frame_size,
                    filter_length=self.config.filter_length,
                    sample_rate=self.config.sample_rate
                )
            elif AEC_ENGINE == 'webrtc':
                # Reset WebRTC state
                self.echo_canceller.reset()

            logger.debug("AEC state reset")

        except Exception as e:
            logger.error(f"Error resetting AEC: {e}")


class SimpleAEC:
    """
    Simple echo cancellation using spectral subtraction
    Fallback when speexdsp/webrtc not available
    """

    def __init__(self, alpha: float = 0.9):
        """
        Args:
            alpha: Subtraction factor (0.0-1.0)
        """
        self.alpha = alpha
        logger.info(f"Simple AEC initialized (alpha={alpha})")

    def process(
        self,
        mic_input: np.ndarray,
        reference_signal: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Simple spectral subtraction

        Args:
            mic_input: Microphone input
            reference_signal: Reference signal (system audio)

        Returns:
            Cleaned audio
        """
        if reference_signal is None:
            return mic_input

        try:
            # Ensure same length
            min_len = min(len(mic_input), len(reference_signal))
            mic = mic_input[:min_len]
            ref = reference_signal[:min_len]

            # Simple time-domain subtraction
            # This is naive but better than nothing
            cleaned = mic - (self.alpha * ref)

            # Clamp to prevent overflow
            cleaned = np.clip(cleaned, -1.0, 1.0)

            return cleaned

        except Exception as e:
            logger.error(f"Simple AEC error: {e}")
            return mic_input


# Example usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=== AEC Test ===\n")

    # Check if AEC is available
    print(f"AEC Available: {AEC_AVAILABLE}")
    print(f"AEC Engine: {AEC_ENGINE}\n")

    if not AEC_AVAILABLE:
        print("⚠️  No AEC library found!")
        print("Install with: pip install speexdsp-python")
        print("\nFalling back to SimpleAEC...")
        aec = SimpleAEC()
    else:
        # Create AEC instance
        config = AECConfig(
            sample_rate=16000,
            frame_size=160,
            filter_length=1600
        )
        aec = AdaptiveAEC(config)

    # Test with synthetic data
    print("Testing with synthetic echo...")

    # Generate test signal (user speech)
    duration = 1.0  # 1 second
    sample_rate = 16000
    t = np.linspace(0, duration, int(sample_rate * duration))
    user_speech = np.sin(2 * np.pi * 440 * t).astype(np.float32)  # 440Hz tone

    # Generate reference signal (system audio / echo source)
    echo_signal = np.sin(2 * np.pi * 880 * t).astype(np.float32)  # 880Hz tone

    # Mic receives both
    mic_input = user_speech + (0.5 * echo_signal)

    print(f"Input signal energy: {np.mean(np.abs(mic_input)):.4f}")
    print(f"Echo signal energy: {np.mean(np.abs(echo_signal)):.4f}")

    # Process with AEC
    cleaned = aec.process(mic_input, echo_signal)

    print(f"Output signal energy: {np.mean(np.abs(cleaned)):.4f}")
    print(f"Echo reduction: {(1 - np.mean(np.abs(cleaned)) / np.mean(np.abs(mic_input))) * 100:.1f}%")

    print("\n✓ AEC test complete")
