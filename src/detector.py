import time
import numpy as np
from scipy import signal
import logging

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
        self.window = signal.windows.hann(self.frame_size)
        self.p = None
        self.stream = None

    def _initialize_audio(self):
        if pyaudio is None:
            raise ImportError("PyAudio is not installed. Clap detection unavailable.")
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sampling_rate,
            input=True,
            frames_per_buffer=self.frame_size,
        )

    def _cleanup_audio(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.p:
            self.p.terminate()

    def calibrate(self):
        """Calibration mode to check volume levels."""
        self._initialize_audio()
        logger.info("Calibration started. Peak levels will be printed. Press Ctrl+C to stop.")
        try:
            while True:
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

    def listen_for_double_clap(self, callback=None):
        """
        Listens continuously for two claps.
        Calls callback() when detected.
        If callback returns True, it stops listening.
        """
        self._initialize_audio()

        clap_count = 0
        last_peak_time = -float("inf")
        filter_state = np.zeros((self.sos.shape[0], 2))
        start_time = time.time()

        logger.info("Listening for claps...")
        try:
            while True:
                frame_data = self.stream.read(self.frame_size, exception_on_overflow=False)
                frame = np.frombuffer(frame_data, dtype=np.float32)
                frame = frame * self.window

                # Apply bandpass filter
                frame_filtered, filter_state = signal.sosfilt(self.sos, frame, zi=filter_state)

                # Detect peaks
                peaks, _ = signal.find_peaks(
                    np.abs(frame_filtered), height=self.threshold
                )
                current_time = time.time() - start_time

                if peaks.size > 0 and (current_time - last_peak_time) >= self.min_interval:
                    if (current_time - last_peak_time) > self.max_interval:
                        logger.info("First clap timed out. Starting count over.")
                        clap_count = 1
                    else:
                        clap_count += 1

                    logger.info(f"Clap detected! (Count: {clap_count})")
                    last_peak_time = current_time

                    if clap_count == 2:
                        logger.info("Double clap detected!")
                        if callback:
                            should_stop = callback()
                            if should_stop:
                                break
                        clap_count = 0 # Reset for next routine
        finally:
            self._cleanup_audio()
