import time
import io
import os
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
        self.enabled = config.audio_settings.get("enabled", False)
        self.initialized = False
        self._lock = threading.Lock()
        logger.info(f"Audio engine initialized (enabled: {self.enabled})")
        if self.enabled:
            self.maybe_initialize()

    def maybe_initialize(self):
        if self.enabled:
            if pygame and not self.initialized:
                try:
                    # Initialize mixer with frequency consistent with gTTS
                    pygame.mixer.init(frequency=24000)
                    self.initialized = True
                    logger.info("Pygame mixer initialized for TTS.")
                except Exception as e:
                    logger.error(f"Failed to initialize pygame mixer: {e}")
                    self.enabled = False
            elif not pygame:
                logger.warning("Pygame not installed. Audio disabled.")
                self.enabled = False
        else:
            logger.info("TTS is disabled in configuration. Skipping initialization.")

    def play_file(self, file_path, block=False):
        if not self.enabled or not file_path:
            logger.info(f"Audio File (Disabled/No Path): {file_path}")
            return

        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return

        def _perform_play():
            if not self._lock.acquire(blocking=False):
                logger.warning("Jarvis is already playing audio. Ignoring.")
                return
            try:
                logger.info(f"Playing file: {file_path}")
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                logger.info(f"Finished playing file: {file_path}")
            except Exception as e:
                logger.error(f"Error playing audio file {file_path}: {e}")
            finally:
                self._lock.release()

        t = threading.Thread(target=_perform_play)
        t.daemon = True
        t.start()

        if block:
            t.join(timeout=30)

    def speak(self, text, block=False):
        if not self.enabled or not text:
            logger.info(f"TTS (Disabled/No Text): {text}")
            return

        if self.config.audio_settings.get("mode") == "file":
            file_path = self.config.audio_settings.get("file_path")
            if file_path:
                self.play_file(file_path, block=block)
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
