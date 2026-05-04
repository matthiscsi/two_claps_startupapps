import time
import numpy as np
from scipy import signal
import logging
from collections import deque
from src.audio_lock import PYAUDIO_LOCK
from src.clap_state import ClapDecision, DoubleClapStateMachine

try:
    import pyaudio
except ImportError:
    pyaudio = None

logger = logging.getLogger(__name__)

class ClapDetector:
    def __init__(self, config):
        self.settings = config.clap_settings
        self.sampling_rate = self.settings["sampling_rate"]
        self.frame_size = int(self.sampling_rate * self.settings["frame_duration"])
        self.threshold = self.settings["threshold"]
        self.min_interval = self.settings["min_interval"]
        self.max_interval = self.settings.get("max_interval", 2.0) # 2 seconds default timeout

        self.sos = signal.butter(
            self.settings["order"],
            [self.settings["filter_low"], self.settings["filter_high"]],
            btype="bandpass",
            fs=self.sampling_rate,
            output="sos",
        )
        self.p = None
        self.stream = None
        self.last_peak = 0.0
        self.clap_count = 0
        self.state = "IDLE"
        self.recent_peaks = deque(maxlen=8)
        self.max_transient_duration_sec = self.settings.get("max_transient_duration", 0.012)
        self.crest_factor_min = self.settings.get("crest_factor_min", 4.0)
        self.sustained_peak_ratio = self.settings.get("sustained_peak_ratio", 0.60)
        self.max_sustained_frames = int(self.settings.get("max_sustained_frames", 3))
        self.input_device_index = self.settings.get("input_device_index")
        self.machine = DoubleClapStateMachine(
            min_interval=self.min_interval,
            max_interval=self.max_interval,
        )

    def refresh_settings(self, settings):
        """Apply runtime-safe clap settings updates without restarting the process."""
        self.settings = settings
        self.threshold = settings.get("threshold", self.threshold)
        self.min_interval = settings.get("min_interval", self.min_interval)
        self.max_interval = settings.get("max_interval", self.max_interval)
        self.max_transient_duration_sec = settings.get("max_transient_duration", self.max_transient_duration_sec)
        self.crest_factor_min = settings.get("crest_factor_min", self.crest_factor_min)
        self.sustained_peak_ratio = settings.get("sustained_peak_ratio", self.sustained_peak_ratio)
        self.max_sustained_frames = int(settings.get("max_sustained_frames", self.max_sustained_frames))
        self.input_device_index = settings.get("input_device_index", self.input_device_index)
        self.machine = DoubleClapStateMachine(
            min_interval=self.min_interval,
            max_interval=self.max_interval,
        )

    def _is_transient_clap(self, frame_filtered):
        """
        Lightweight clap classifier based on transient behavior:
        - high instantaneous peak
        - short above-threshold duration
        - high crest factor (spiky, not sustained)
        - reject sustained high-energy frames (voice, barking, etc.)
        """
        peak = float(np.max(np.abs(frame_filtered)))
        if peak < self.threshold:
            return False, "below_threshold"

        rms = float(np.sqrt(np.mean(frame_filtered ** 2)) + 1e-9)
        crest_factor = peak / rms
        if crest_factor < self.crest_factor_min:
            return False, f"low_crest_factor({crest_factor:.2f})"

        above_rel = np.abs(frame_filtered) > (peak * 0.35)
        active_samples = int(np.count_nonzero(above_rel))
        active_duration = active_samples / float(self.sampling_rate)
        if active_duration > self.max_transient_duration_sec:
            return False, f"too_long({active_duration:.4f}s)"

        high_frames = sum(1 for p in self.recent_peaks if p >= (self.threshold * self.sustained_peak_ratio))
        if high_frames >= self.max_sustained_frames:
            return False, f"sustained_energy({high_frames}frames)"

        return True, "ok"

    def _initialize_audio(self):
        logger.info("START: Initializing audio input for clap detection...")
        if pyaudio is None:
            logger.error("FAIL: PyAudio is not installed. Clap detection unavailable.")
            return False

        with PYAUDIO_LOCK:
            try:
                logger.info("START: Creating PyAudio instance...")
                self.p = pyaudio.PyAudio()
                logger.info("SUCCESS: PyAudio instance created.")

                try:
                    if isinstance(self.input_device_index, int):
                        logger.info("START: Querying configured input device index=%s...", self.input_device_index)
                        device_info = self.p.get_device_info_by_index(self.input_device_index)
                    else:
                        logger.info("START: Querying default input device...")
                        device_info = self.p.get_default_input_device_info()
                    logger.info(f"SUCCESS: Using input device: {device_info.get('name')} (Index: {device_info.get('index')})")
                    logger.info(f"Device Details: Sample Rate: {device_info.get('defaultSampleRate')}, Max Input Channels: {device_info.get('maxInputChannels')}")
                except Exception as e:
                    logger.warning(f"FAIL: Could not retrieve default input device info: {e}", exc_info=True)
                    device_info = None

                stream_kwargs = dict(
                    format=pyaudio.paFloat32,
                    channels=1,
                    rate=self.sampling_rate,
                    input=True,
                    frames_per_buffer=self.frame_size,
                )
                if device_info and isinstance(device_info.get("index"), int):
                    stream_kwargs["input_device_index"] = int(device_info["index"])

                logger.info(
                    "START: Opening audio stream (Rate: %s, Format: paFloat32, Channels: 1, FrameSize: %s, InputDevice: %s)...",
                    self.sampling_rate,
                    self.frame_size,
                    stream_kwargs.get("input_device_index", "default"),
                )
                try:
                    self.stream = self.p.open(**stream_kwargs)
                except Exception as e:
                    if "input_device_index" in stream_kwargs:
                        logger.warning(
                            "Configured input device failed (index=%s). Falling back to default input device. Error: %s",
                            stream_kwargs["input_device_index"],
                            e,
                        )
                        stream_kwargs.pop("input_device_index", None)
                        self.stream = self.p.open(**stream_kwargs)
                    else:
                        raise
                logger.info("SUCCESS: Audio stream object created.")

                logger.info("START: Starting audio stream...")
                self.stream.start_stream()
                logger.info("SUCCESS: Audio stream started.")

                return True
            except Exception as e:
                logger.error(f"FAIL: Failed to initialize audio input for clap detection: {e}", exc_info=True)
                self._cleanup_audio()
                return False

    def _cleanup_audio(self):
        with PYAUDIO_LOCK:
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except:
                    pass
                self.stream = None
            if self.p:
                try:
                    self.p.terminate()
                except:
                    pass
                self.p = None

    def calibrate(self, stop_event=None):
        """Calibration mode to check volume levels."""
        if not self._initialize_audio():
            logger.error("Could not start calibration due to audio initialization failure.")
            return
        logger.info("Calibration started. Peak levels will be printed. Press Ctrl+C to stop.")
        try:
            while stop_event is None or not stop_event.is_set():
                frame_data = self.stream.read(self.frame_size, exception_on_overflow=False)
                frame = np.frombuffer(frame_data, dtype=np.float32)
                # Apply bandpass filter to see what the detector "sees"
                frame_filtered, _ = signal.sosfilt(self.sos, frame, zi=np.zeros((self.sos.shape[0], 2)))
                peak = np.max(np.abs(frame_filtered))
                if peak > 0.01: # Filter out absolute silence
                    # Create a simple visual bar
                    bar = "#" * int(peak * 50)
                    print(f"Level: {peak:.4f} {bar}")
                time.sleep(0.05)
        finally:
            self._cleanup_audio()

    def get_status(self):
        """Returns current detection status for UI polling."""
        return {
            "peak": self.last_peak,
            "threshold": self.threshold,
            "state": self.state,
            "clap_count": self.clap_count
        }

    def listen_for_double_clap(self, callback=None, stop_event=None):
        """
        Listens continuously for two claps.
        Calls callback() when detected.
        If callback returns True, it stops listening.
        """
        if not self._initialize_audio():
            logger.error("Clap detection could not start: Audio initialization failed.")
            # Wait for stop event even if audio fails to prevent tight loop or instant exit
            if stop_event:
                while not stop_event.is_set():
                    time.sleep(1)
            return

        self.machine.reset()
        self.clap_count = 0
        filter_state = np.zeros((self.sos.shape[0], 2))
        start_time = time.monotonic()

        logger.info("Listening for claps...")
        first_frame = True
        try:
            while stop_event is None or not stop_event.is_set():
                try:
                    # Reducing block size for read can sometimes help with latency
                    frame_data = self.stream.read(self.frame_size, exception_on_overflow=False)
                    if first_frame:
                        logger.info("SUCCESS: First audio frame received.")
                        first_frame = False
                except Exception as e:
                    logger.error(f"Error reading audio stream: {e}")
                    time.sleep(0.1)
                    continue
                frame = np.frombuffer(frame_data, dtype=np.float32)

                # Apply bandpass filter
                frame_filtered, filter_state = signal.sosfilt(self.sos, frame, zi=filter_state)

                # Detect peaks
                self.last_peak = np.max(np.abs(frame_filtered))
                self.recent_peaks.append(self.last_peak)
                current_time = time.monotonic() - start_time

                clap_like, reason = self._is_transient_clap(frame_filtered)
                if clap_like:
                    event = self.machine.register_clap(current_time)
                    self.clap_count = event.clap_count
                    self.state = event.state

                    if event.decision == ClapDecision.ACCEPTED:
                        logger.info(f"Clap detected! (Count: {self.clap_count}, Peak: {self.last_peak:.4f})")
                    elif event.decision == ClapDecision.DOUBLE_CLAP:
                        logger.info("Double clap detected!")
                        if callback:
                            should_stop = callback()
                            if should_stop:
                                break
                    elif event.reason == "min_interval":
                        logger.debug(f"Peak {self.last_peak:.4f} ignored: within min_interval cooldown.")
                elif self.last_peak >= self.threshold:
                    event = self.machine.reject(reason)
                    self.clap_count = event.clap_count
                    self.state = event.state
                    logger.debug(f"Rejected non-clap transient candidate. peak={self.last_peak:.4f}, reason={reason}")

                tick = self.machine.on_tick(current_time)
                self.clap_count = tick.clap_count
                self.state = tick.state

        finally:
            self._cleanup_audio()
