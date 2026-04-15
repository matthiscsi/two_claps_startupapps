import time
import numpy as np
from scipy import signal
import logging
from src.audio_lock import PYAUDIO_LOCK

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
                    logger.info("START: Querying default input device...")
                    device_info = self.p.get_default_input_device_info()
                    logger.info(f"SUCCESS: Using input device: {device_info.get('name')} (Index: {device_info.get('index')})")
                    logger.info(f"Device Details: Sample Rate: {device_info.get('defaultSampleRate')}, Max Input Channels: {device_info.get('maxInputChannels')}")
                except Exception as e:
                    logger.warning(f"FAIL: Could not retrieve default input device info: {e}", exc_info=True)

                logger.info(f"START: Opening audio stream (Rate: {self.sampling_rate}, Format: paFloat32, Channels: 1, FrameSize: {self.frame_size})...")
                self.stream = self.p.open(
                    format=pyaudio.paFloat32,
                    channels=1,
                    rate=self.sampling_rate,
                    input=True,
                    frames_per_buffer=self.frame_size,
                )
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

        self.clap_count = 0
        last_peak_time = -float("inf")
        filter_state = np.zeros((self.sos.shape[0], 2))
        start_time = time.time()

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
                current_time = time.time() - start_time

                if self.last_peak >= self.threshold:
                    if (current_time - last_peak_time) >= self.min_interval:
                        if (current_time - last_peak_time) > self.max_interval:
                            if self.clap_count > 0:
                                logger.info("First clap timed out. Starting count over.")
                            self.clap_count = 1
                        else:
                            self.clap_count += 1

                        logger.info(f"Clap detected! (Count: {self.clap_count}, Peak: {self.last_peak:.4f})")
                        last_peak_time = current_time

                        if self.clap_count == 2:
                            logger.info("Double clap detected!")
                            if callback:
                                should_stop = callback()
                                if should_stop:
                                    break
                            self.clap_count = 0 # Reset for next routine
                            self.state = "IDLE"
                        else:
                            self.state = "WAITING"
                    else:
                        logger.debug(f"Peak {self.last_peak:.4f} ignored: within min_interval cooldown.")

                # Update state for external polling
                if self.clap_count == 0:
                    self.state = "IDLE"
                elif (current_time - last_peak_time) > self.max_interval:
                    self.state = "IDLE"
                    self.clap_count = 0

        finally:
            self._cleanup_audio()
