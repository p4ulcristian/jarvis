#!/usr/bin/env python3
"""
System Audio Capture
Captures both microphone input and system audio output for AEC
Works with PulseAudio/PipeWire
"""
import logging
import numpy as np
import sounddevice as sd
import subprocess
import time
from typing import Optional, Tuple, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import resampling library
try:
    import resampy
    RESAMPY_AVAILABLE = True
except ImportError:
    try:
        from scipy import signal
        RESAMPY_AVAILABLE = False
        logger.info("Using scipy for resampling (resampy not available)")
    except ImportError:
        logger.error("No resampling library available - install resampy or scipy")
        raise ImportError("Need resampy or scipy for audio resampling")


@dataclass
class AudioDeviceInfo:
    """Information about an audio device"""
    index: int
    name: str
    channels: int
    sample_rate: int
    is_input: bool
    is_output: bool
    is_monitor: bool


class SystemAudioCapture:
    """
    Captures both microphone input and system audio output

    This provides the two audio streams needed for AEC:
    1. Microphone input (user voice + echo)
    2. System audio output (what's playing on speakers - reference signal)

    The AEC module will subtract stream #2 from stream #1 to remove echo.
    """

    def __init__(
        self,
        mic_device_name: Optional[str] = None,
        sample_rate: int = 16000,
        chunk_size: int = 1600,
        channels: int = 1
    ):
        """
        Initialize system audio capture

        Args:
            mic_device_name: Microphone device name (auto-detect if None)
            sample_rate: Target sample rate (16kHz for speech)
            chunk_size: Samples per chunk
            channels: Number of channels (1=mono, 2=stereo)
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels

        # Find audio devices
        self.devices = self._enumerate_devices()

        # Auto-select devices
        self.mic_device = self._find_microphone(mic_device_name)
        self.monitor_device = self._find_system_monitor()

        # If monitor not found through sounddevice, try PulseAudio/PipeWire directly
        if not self.monitor_device:
            self.monitor_device = self._find_monitor_via_pactl()

        if not self.mic_device:
            logger.warning("No microphone device found!")
        else:
            logger.info(f"Microphone: {self.mic_device.name}")

        if not self.monitor_device:
            logger.warning("No system audio monitor found!")
        else:
            logger.info(f"System monitor: {self.monitor_device.name}")

        # Streams
        self.mic_stream = None
        self.monitor_stream = None
        self.is_capturing = False

    def _enumerate_devices(self) -> Dict[int, AudioDeviceInfo]:
        """Enumerate all audio devices"""
        devices = {}

        try:
            device_count = sd.query_devices()

            for i, dev in enumerate(device_count):
                # Detect if it's a monitor device (loopback)
                name_lower = dev['name'].lower()
                is_monitor = any(keyword in name_lower for keyword in
                    ['monitor', 'loopback', 'what-u-hear', 'wave out mix', 'stereo mix'])

                devices[i] = AudioDeviceInfo(
                    index=i,
                    name=dev['name'],
                    channels=dev['max_input_channels'],
                    sample_rate=int(dev['default_samplerate']),
                    is_input=dev['max_input_channels'] > 0,
                    is_output=dev['max_output_channels'] > 0,
                    is_monitor=is_monitor
                )

        except Exception as e:
            logger.error(f"Error enumerating devices: {e}")

        return devices

    def _find_microphone(self, preferred_name: Optional[str] = None) -> Optional[AudioDeviceInfo]:
        """Find the best microphone device"""
        candidates = []

        for dev in self.devices.values():
            # Must be input and not a monitor
            if not dev.is_input or dev.is_monitor:
                continue

            # If preferred name specified, prioritize it
            if preferred_name and preferred_name.lower() in dev.name.lower():
                return dev

            # Skip unwanted devices
            name_lower = dev.name.lower()
            if any(skip in name_lower for skip in ['hdmi', 'dummy', 'null']):
                continue

            candidates.append(dev)

        # Prefer USB microphones
        for dev in candidates:
            if 'usb' in dev.name.lower():
                return dev

        # Return first candidate
        return candidates[0] if candidates else None

    def _find_system_monitor(self) -> Optional[AudioDeviceInfo]:
        """Find system audio monitor (loopback) device"""
        # First pass: look for explicit monitor devices
        for dev in self.devices.values():
            if dev.is_input and 'monitor' in dev.name.lower():
                logger.info(f"Found monitor device: {dev.name}")
                return dev

        # Second pass: any device marked as monitor
        for dev in self.devices.values():
            if dev.is_monitor and dev.is_input:
                logger.info(f"Found monitor device: {dev.name}")
                return dev

        # If no monitor found, try to list PulseAudio/PipeWire sources
        logger.warning("No monitor device found in sounddevice list")
        logger.info("Checking for PulseAudio/PipeWire monitor sources...")

        try:
            result = subprocess.run(
                ['pactl', 'list', 'sources', 'short'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and 'monitor' in result.stdout.lower():
                logger.info("Monitor source detected in PulseAudio/PipeWire")
                logger.info("Re-scanning devices...")
                # Try re-enumerating devices
                self.devices = self._enumerate_devices()
                for dev in self.devices.values():
                    if dev.is_input and 'monitor' in dev.name.lower():
                        return dev
        except Exception as e:
            logger.debug(f"Could not query pactl: {e}")

        logger.warning("No system audio monitor available - AEC will be disabled")
        return None

    def _find_monitor_via_pactl(self) -> Optional[AudioDeviceInfo]:
        """Find monitor device using pactl directly"""
        try:
            result = subprocess.run(
                ['pactl', 'list', 'sources', 'short'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode != 0:
                return None

            # Look for monitor source
            for line in result.stdout.strip().split('\n'):
                if 'monitor' in line.lower():
                    parts = line.split()
                    if len(parts) >= 2:
                        monitor_name = parts[1]
                        logger.info(f"Found PipeWire/PulseAudio monitor: {monitor_name}")

                        # Try to find this device in sounddevice list by partial match
                        for dev in self.devices.values():
                            # Match by checking if device name contains parts of monitor name
                            if dev.is_input:
                                # Try various matching strategies
                                if ('hdmi' in monitor_name.lower() and 'hdmi' in dev.name.lower()) or \
                                   ('digital' in monitor_name.lower() and 'digital' in dev.name.lower()) or \
                                   (monitor_name in dev.name):
                                    logger.info(f"Matched monitor to sounddevice: {dev.name}")
                                    return dev

                        # If not found in sounddevice, create a pseudo device
                        # We'll use the name directly with sounddevice
                        logger.info(f"Using monitor source name directly: {monitor_name}")
                        return AudioDeviceInfo(
                            index=-1,  # Special marker for name-based device
                            name=monitor_name,
                            channels=2,
                            sample_rate=48000,
                            is_input=True,
                            is_output=False,
                            is_monitor=True
                        )
        except Exception as e:
            logger.debug(f"Could not find monitor via pactl: {e}")

        return None

    def list_devices(self) -> None:
        """Print all available audio devices"""
        print("\n=== Available Audio Devices ===\n")

        for dev in self.devices.values():
            device_type = []
            if dev.is_input:
                device_type.append("INPUT")
            if dev.is_output:
                device_type.append("OUTPUT")
            if dev.is_monitor:
                device_type.append("MONITOR")

            print(f"[{dev.index}] {dev.name}")
            print(f"    Type: {', '.join(device_type)}")
            print(f"    Channels: {dev.channels}, Sample Rate: {dev.sample_rate}Hz")
            print()

    def start_capture(self) -> bool:
        """
        Start capturing both microphone and system audio

        Returns:
            True if successful, False otherwise
        """
        if self.is_capturing:
            logger.warning("Already capturing")
            return True

        if not self.mic_device:
            logger.error("No microphone device available")
            return False

        try:
            # Start microphone stream - let sounddevice choose blocksize
            self.mic_stream = sd.InputStream(
                device=self.mic_device.index,
                samplerate=self.mic_device.sample_rate,
                channels=self.channels,
                dtype='float32',
            )
            self.mic_stream.start()
            logger.info(f"Microphone stream started: {self.mic_device.sample_rate}Hz")

            # Start monitor stream (if available)
            if self.monitor_device:
                # Use device name if index is -1, otherwise use index
                device_spec = self.monitor_device.name if self.monitor_device.index == -1 else self.monitor_device.index

                self.monitor_stream = sd.InputStream(
                    device=device_spec,
                    samplerate=self.monitor_device.sample_rate,
                    channels=self.channels,
                    dtype='float32',
                )
                self.monitor_stream.start()
                logger.info(f"System monitor stream started: {self.monitor_device.name}, {self.monitor_device.sample_rate}Hz")
            else:
                logger.warning("No system monitor - AEC will be limited")

            self.is_capturing = True
            return True

        except Exception as e:
            logger.error(f"Failed to start capture: {e}", exc_info=True)
            self.stop_capture()
            return False

    def _resample_audio(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """
        Resample audio from orig_sr to target_sr

        Args:
            audio: Input audio array
            orig_sr: Original sample rate
            target_sr: Target sample rate

        Returns:
            Resampled audio array
        """
        if orig_sr == target_sr:
            return audio

        try:
            if RESAMPY_AVAILABLE:
                # Use resampy (high quality)
                resampled = resampy.resample(audio, orig_sr, target_sr, filter='kaiser_best')
            else:
                # Use scipy (fallback)
                from scipy import signal
                num_samples = int(len(audio) * target_sr / orig_sr)
                resampled = signal.resample(audio, num_samples)

            return resampled.astype(np.float32)
        except Exception as e:
            logger.error(f"Resampling error: {e}")
            return audio

    def get_frames(self, timeout: float = 1.0) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Get synchronized audio frames from both streams
        Both streams are resampled to target sample_rate and time-aligned

        Args:
            timeout: Timeout in seconds

        Returns:
            Tuple of (mic_audio, system_audio) both at self.sample_rate
            Either can be None if not available
        """
        if not self.is_capturing:
            return None, None

        mic_audio = None
        system_audio = None

        try:
            # Calculate chunk sizes based on native sample rates
            # We want the same TIME duration from both streams
            target_duration = self.chunk_size / self.sample_rate  # Duration in seconds

            # Read from microphone
            if self.mic_stream:
                # Calculate how many samples to read at native rate for target duration
                mic_native_chunk = int(target_duration * self.mic_device.sample_rate)

                data, overflowed = self.mic_stream.read(mic_native_chunk)
                if overflowed:
                    logger.warning("Microphone buffer overflowed")

                if data is not None:
                    raw_audio = data.flatten()
                    # Resample to target rate
                    mic_audio = self._resample_audio(
                        raw_audio,
                        self.mic_device.sample_rate,
                        self.sample_rate
                    )

            # Read from system monitor
            if self.monitor_stream:
                # Calculate how many samples to read at native rate for target duration
                monitor_native_chunk = int(target_duration * self.monitor_device.sample_rate)

                data, overflowed = self.monitor_stream.read(monitor_native_chunk)
                if overflowed:
                    logger.warning("Monitor buffer overflowed")

                if data is not None:
                    raw_audio = data.flatten()
                    # Resample to target rate
                    system_audio = self._resample_audio(
                        raw_audio,
                        self.monitor_device.sample_rate,
                        self.sample_rate
                    )

            # Ensure both buffers are exactly the same size after resampling
            if mic_audio is not None and system_audio is not None:
                # Trim or pad to match self.chunk_size exactly
                target_len = self.chunk_size

                if len(mic_audio) > target_len:
                    mic_audio = mic_audio[:target_len]
                elif len(mic_audio) < target_len:
                    mic_audio = np.pad(mic_audio, (0, target_len - len(mic_audio)), mode='constant')

                if len(system_audio) > target_len:
                    system_audio = system_audio[:target_len]
                elif len(system_audio) < target_len:
                    system_audio = np.pad(system_audio, (0, target_len - len(system_audio)), mode='constant')

                # Final verification
                if len(mic_audio) != len(system_audio):
                    logger.warning(f"Buffer size mismatch after alignment: mic={len(mic_audio)}, sys={len(system_audio)}")

        except Exception as e:
            logger.error(f"Error reading audio frames: {e}")

        return mic_audio, system_audio

    def stop_capture(self) -> None:
        """Stop all audio streams"""
        if self.mic_stream:
            try:
                self.mic_stream.stop()
                self.mic_stream.close()
            except Exception as e:
                logger.error(f"Error stopping mic stream: {e}")
            self.mic_stream = None

        if self.monitor_stream:
            try:
                self.monitor_stream.stop()
                self.monitor_stream.close()
            except Exception as e:
                logger.error(f"Error stopping monitor stream: {e}")
            self.monitor_stream = None

        self.is_capturing = False
        logger.info("Audio capture stopped")

    @staticmethod
    def setup_pulseaudio_loopback() -> bool:
        """
        Setup PulseAudio/PipeWire loopback for system audio monitoring

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load loopback module
            result = subprocess.run(
                ['pactl', 'load-module', 'module-loopback'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                logger.info("PulseAudio loopback module loaded")
                return True
            else:
                logger.error(f"Failed to load loopback: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Timeout loading loopback module")
            return False
        except FileNotFoundError:
            logger.error("pactl not found - is PulseAudio/PipeWire installed?")
            return False
        except Exception as e:
            logger.error(f"Error setting up loopback: {e}")
            return False


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=== System Audio Capture Test ===\n")

    # Create capture instance
    capture = SystemAudioCapture(
        sample_rate=16000,
        chunk_size=1600,
        channels=1
    )

    # List all devices
    capture.list_devices()

    # Try to setup loopback
    print("Setting up PulseAudio loopback...")
    if SystemAudioCapture.setup_pulseaudio_loopback():
        print("✓ Loopback enabled\n")
    else:
        print("✗ Loopback failed - you may need to run manually:\n")
        print("  pactl load-module module-loopback\n")

    # Start capture
    print("Starting capture test (5 seconds)...")
    if not capture.start_capture():
        print("✗ Failed to start capture")
        exit(1)

    # Capture for 5 seconds
    start_time = time.time()
    frames_captured = 0

    while time.time() - start_time < 5.0:
        mic_audio, sys_audio = capture.get_frames(timeout=1.0)

        if mic_audio is not None:
            frames_captured += 1
            mic_level = np.abs(mic_audio).max()
            sys_level = np.abs(sys_audio).max() if sys_audio is not None else 0.0

            print(f"Frame {frames_captured}: Mic={mic_level:.4f}, System={sys_level:.4f}")

        time.sleep(0.1)

    # Stop capture
    capture.stop_capture()
    print(f"\n✓ Captured {frames_captured} frames")
