import time
import io
import logging
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

        if self.enabled and pygame:
            try:
                pygame.mixer.init()
                self.initialized = True
            except Exception as e:
                logger.error(f"Failed to initialize pygame mixer: {e}")
                self.enabled = False
        elif not pygame:
            logger.warning("Pygame not installed. Audio disabled.")
            self.enabled = False

    def speak(self, text):
        if not self.enabled or not text:
            logger.info(f"TTS (Disabled/No Text): {text}")
            return

        logger.info(f"Speaking: {text}")
        try:
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
            print(f"JARVIS: {text}") # Fallback to print

    def play_startup(self):
        phrase = self.config.audio_settings.get("startup_phrase")
        self.speak(phrase)

    def play_success(self):
        phrase = self.config.audio_settings.get("success_phrase")
        self.speak(phrase)
