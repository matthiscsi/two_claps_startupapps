import argparse
import sys
import os
import signal
import time
import logging
import threading
from PIL import Image, ImageDraw

try:
    import pystray
except ImportError:
    pystray = None

from src.config import Config, get_resource_path
from src.detector import ClapDetector
from src.launcher import Launcher
from src.audio import AudioEngine
from src.logger import setup_logger
from src.ui import SettingsUI

class JarvisApp:
    def __init__(self, args):
        self.args = args

        # Don't use get_resource_path for the config file if we want it to be user-editable.
        # But for the default, it's fine.
        # Better: use the provided path directly, which defaults to config.yaml in current dir.
        self.config = Config(args.config)

        if args.no_audio:
            self.config.data["audio_settings"]["enabled"] = False

        log_settings = self.config.get("logging", {})
        self.logger = setup_logger(
            level=getattr(logging, log_settings.get("level", "INFO")),
            log_file=log_settings.get("file")
        )

        self.audio = AudioEngine(self.config)
        self.launcher = Launcher(self.config, dry_run=args.dry_run)
        self.detector = ClapDetector(self.config)

        self.routine_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.tray_icon = None

    def on_trigger_routine(self):
        def run():
            # Use non-blocking acquire to ignore duplicate triggers while routine is running
            if not self.routine_lock.acquire(blocking=False):
                self.logger.warning("Routine already in progress. Ignoring trigger.")
                return
            try:
                self.logger.info(f"Triggering routine: {self.args.routine}")
                self.audio.play_startup()
                self.launcher.launch_routine(self.args.routine)
                self.audio.play_success()
            finally:
                self.routine_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def _on_settings_saved(self):
        self.logger.info("Settings saved. Updating runtime components...")
        # Update components with new config
        self.detector.settings = self.config.clap_settings
        self.detector.threshold = self.config.clap_settings.get('threshold', 0.2)
        self.detector.min_interval = self.config.clap_settings.get('min_interval', 0.2)

        self.audio.enabled = self.config.audio_settings.get('enabled', True)

    def create_tray_icon(self):
        if not pystray or self.args.no_tray:
            return None

        def create_image():
            width = 64
            height = 64
            image = Image.new('RGB', (width, height), (0, 0, 0))
            dc = ImageDraw.Draw(image)
            dc.rectangle((width // 2 - 10, height // 2 - 10, width // 2 + 10, height // 2 + 10), fill=(0, 255, 255))
            return image

        def on_quit(icon, item):
            self.logger.info("Quit selected from tray.")
            self.shutdown()

        def on_trigger(icon, item):
            self.on_trigger_routine()

        def on_settings(icon, item):
            self.logger.info("Opening settings UI...")
            ui = SettingsUI(self.config, on_save_callback=self._on_settings_saved)
            # Need to run UI in a thread because we are in the tray thread
            threading.Thread(target=ui.open, daemon=True).start()

        menu = pystray.Menu(
            pystray.MenuItem(f"Trigger {self.args.routine}", on_trigger),
            pystray.MenuItem("Settings", on_settings),
            pystray.MenuItem("Quit", on_quit)
        )
        return pystray.Icon("JarvisLauncher", create_image(), "Jarvis Launcher", menu=menu)

    def shutdown(self):
        self.logger.info("Initiating graceful shutdown...")
        self.stop_event.set()
        if self.tray_icon:
            self.tray_icon.stop()
        # The detector loop will check stop_event or be interrupted by sys.exit in signal handler

    def run(self):
        self.logger.info("Initializing Jarvis Launcher...")

        if self.args.calibrate:
            self.logger.info("ENTERING CALIBRATION MODE. Press Ctrl+C to exit.")
            self.detector.calibrate(stop_event=self.stop_event)
            return

        # Start tray icon in a separate thread
        self.tray_icon = self.create_tray_icon()
        if self.tray_icon:
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

        def signal_handler(sig, frame):
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.logger.info(f"System ready. Routine '{self.args.routine}' will trigger on double clap.")
        if self.args.dry_run:
            self.logger.info("RUNNING IN DRY-RUN MODE")

        try:
            self.detector.listen_for_double_clap(
                callback=lambda: self.on_trigger_routine() or False,
                stop_event=self.stop_event
            )
        except Exception as e:
            self.logger.error(f"Fatal error in detector: {e}")
            if self.args.dry_run:
                while not self.stop_event.is_set():
                    time.sleep(1)
            else:
                sys.exit(1)
        finally:
            self.shutdown()

def parse_args():
    parser = argparse.ArgumentParser(description="Double-clap routine launcher (Jarvis style)")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--routine", default="morning_routine", help="Routine to run on double clap")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually launch apps, just log")
    parser.add_argument("--no-audio", action="store_true", help="Disable audio/TTS")
    parser.add_argument("--calibrate", action="store_true", help="Calibration mode to check volume levels")
    parser.add_argument("--no-tray", action="store_true", help="Disable system tray icon")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    app = JarvisApp(args)
    app.run()
