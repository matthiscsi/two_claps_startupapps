import threading

# Global lock to prevent concurrent PyAudio/PortAudio initialization which can cause native crashes.
# Using RLock to allow reentrant calls during cleanup/error paths.
PYAUDIO_LOCK = threading.RLock()
