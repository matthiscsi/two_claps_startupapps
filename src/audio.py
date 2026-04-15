import time
import io
import logging
import threading
from gtts import gTTS

try:
    import pygame
except ImportError:
    pygame = None

logger = logging.getLogger(__name__)

class AudioEngine:
    def __init__(self, config):
        self.config = config
        self.enabled = config.audio_settings.get("enabled", True)
        self.initialized = False
        self._lock = threading.Lock()
        if self.enabled:
            self.maybe_initialize()

    def maybe_initialize(self):
        if self.enabled and pygame and not self.initialized:
            try:
                # Initialize mixer with frequency consistent with gTTS
                pygame.mixer.init(frequency=24000)
                self.initialized = True
                logger.info("Pygame mixer initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize pygame mixer: {e}")
                self.enabled = False
        elif not pygame:
            logger.warning("Pygame not installed. Audio disabled.")
            self.enabled = False

    def speak(self, text, block=False):
        if not self.enabled or not text:
            logger.info(f"TTS (Disabled/No Text): {text}")
            return

        def _perform_speak():
            if not self._lock.acquire(blocking=False):
                logger.warning("Jarvis is already speaking. Ignoring.")
                return
            try:
                logger.info(f"Speaking: {text}")
                tts = gTTS(text=text, lang="en")
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)

                pygame.mixer.music.load(fp)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in TTS: {e}")
            finally:
                self._lock.release()

        t = threading.Thread(target=_perform_speak)
        t.daemon = True
        t.start()

        if block:
            t.join(timeout=10)

    def play_startup(self, block=False):
        phrase = self.config.audio_settings.get("startup_phrase")
        if phrase:
            self.speak(phrase, block=block)

    def play_success(self):
        phrase = self.config.audio_settings.get("success_phrase")
        if phrase:
            self.speak(phrase)
