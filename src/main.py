import logging
import sys
import argparse
import os
import signal
import time
import threading
import ctypes
import traceback
from PIL import Image, ImageDraw

# Early logging setup to capture everything from the start
from src.logger import setup_logger
# We use a default log name initially; JarvisApp will refine it from config later.
setup_logger(level=logging.INFO, log_file="launcher.log")
logger = logging.getLogger("JarvisStartup")

def global_exception_handler(exctype, value, tb):
    """Global exception handler to capture unhandled crashes."""
    logger.critical("FAIL: UNHANDLED FATAL EXCEPTION (Global Hook)", exc_info=(exctype, value, tb))
    # On Windows, if we are in pythonw mode, there is no console.
    if sys.platform == "win32":
         try:
             ctypes.windll.user32.MessageBoxW(0, f"Jarvis Launcher crashed:\n\n{value}\n\nCheck logs for details.", "Critical Error", 0x10)
         except:
             pass
    logging.shutdown()
    sys.exit(1)

sys.excepthook = global_exception_handler
if hasattr(threading, 'excepthook'):
    threading.excepthook = lambda args: global_exception_handler(args.exc_type, args.exc_value, args.exc_traceback)

import os
import signal
import time
import threading
import ctypes
import traceback
from PIL import Image, ImageDraw

try:
    import pystray
except (ImportError, Exception):
    # pystray can throw exceptions on import if display environment is missing (e.g. Linux without X)
    pystray = None

from src.config import Config, get_resource_path
from src.detector import ClapDetector
from src.launcher import Launcher
from src.audio import AudioEngine
from src.ui import SettingsUI

class JarvisApp:
    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger("JarvisApp")

        # Set AppUserModelID for proper taskbar grouping on Windows
        if sys.platform == "win32":
            try:
                self.logger.info("START: Setting AppUserModelID for Windows...")
                myappid = "com.jarvis.launcher.v1"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                self.logger.info("SUCCESS: AppUserModelID set.")
            except Exception as e:
                self.logger.warning(f"FAIL: Could not set AppUserModelID: {e}")

        # 1. Config loading
        self.logger.info(f"START: Loading configuration from {args.config}...")
        try:
            self.config = Config(args.config)
            self.logger.info("SUCCESS: Configuration loaded.")
        except Exception as e:
            self.logger.error(f"FAIL: Critical failure loading config: {e}", exc_info=True)
            # Fallback to default config if possible
            self.config = Config(None)

        if args.no_audio:
            self.config.data["audio_settings"]["enabled"] = False

        # 2. Re-setup logger with config-specific settings
        log_settings = self.config.get("logging", {})
        try:
            setup_logger(
                level=getattr(logging, log_settings.get("level", "INFO")),
                log_file=log_settings.get("file")
            )
            self.logger = logging.getLogger("JarvisApp")
        except Exception as e:
            print(f"Error setting up logger from config: {e}")

        # 3. Subsystem initialization
        self.logger.info("START: Initializing subsystems...")

        self.logger.info("START: Initializing Audio Engine...")
        try:
            self.audio = AudioEngine(self.config)
            if self.audio and self.audio.initialized:
                self.logger.info("SUCCESS: Audio Engine initialized.")
            elif self.audio and not self.audio.enabled:
                self.logger.info("SUCCESS: Audio Engine initialized (Disabled).")
            else:
                self.logger.warning("FAIL: Audio Engine initialization incomplete.")
        except Exception as e:
            self.logger.error(f"FAIL: Failed to initialize AudioEngine: {e}", exc_info=True)
            self.audio = None

        self.logger.info("START: Initializing Launcher...")
        try:
            self.launcher = Launcher(self.config, dry_run=args.dry_run)
            self.logger.info("SUCCESS: Launcher initialized.")
        except Exception as e:
            self.logger.error(f"FAIL: Failed to initialize Launcher: {e}", exc_info=True)
            self.launcher = None

        self.logger.info("START: Initializing Clap Detector...")
        try:
            self.detector = ClapDetector(self.config)
            self.logger.info("SUCCESS: Clap Detector initialized.")
        except Exception as e:
            self.logger.error(f"FAIL: Failed to initialize ClapDetector: {e}", exc_info=True)
            self.detector = None

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
                if self.audio:
                    self.audio.play_startup()
                if self.launcher:
                    self.launcher.launch_routine(self.args.routine)
                if self.audio:
                    self.audio.play_success()
            finally:
                self.routine_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def _on_settings_saved(self):
        self.logger.info("Settings saved. Updating runtime components...")
        # Update components with new config
        if self.detector:
            self.detector.settings = self.config.clap_settings
            self.detector.threshold = self.config.clap_settings.get('threshold', 0.2)
            self.detector.min_interval = self.config.clap_settings.get('min_interval', 0.2)

        if self.audio:
            self.audio.enabled = self.config.audio_settings.get('enabled', True)
            self.audio.maybe_initialize()

    def create_tray_icon(self):
        self.logger.info("START: Creating Tray Icon...")
        if not pystray or self.args.no_tray:
            self.logger.info("SUCCESS: Tray icon creation skipped.")
            return None

        def load_icon():
            icon_path = get_resource_path(os.path.join("assets", "icon.png"))
            if os.path.exists(icon_path):
                return Image.open(icon_path)
            # Fallback dummy icon
            image = Image.new("RGB", (64, 64), (0, 0, 0))
            dc = ImageDraw.Draw(image)
            dc.rectangle((22, 22, 42, 42), fill=(0, 255, 255))
            return image

        def on_quit(icon, item):
            self.logger.info("Quit selected from tray.")
            self.shutdown()

        def on_trigger(icon, item):
            self.on_trigger_routine()

        def on_settings(icon, item):
            self.show_settings()

        menu = pystray.Menu(
            pystray.MenuItem(f"Trigger {self.args.routine}", on_trigger),
            pystray.MenuItem("Settings...", on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", on_quit)
        )
        return pystray.Icon("JarvisLauncher", load_icon(), "Jarvis Launcher", menu=menu)

    def show_settings(self):
        self.logger.info("START: Opening settings UI...")
        # SettingsUI handles singleton internally via _instance
        ui = SettingsUI(self.config, on_save_callback=self._on_settings_saved, detector=self.detector)
        # We run it in a thread to keep the tray responsive.
        # Non-daemon so it doesn't get killed instantly, but on Windows
        # we need to be careful with Tkinter and threads.
        ui_thread = threading.Thread(target=ui.open)
        ui_thread.start()

    def shutdown(self):
        self.logger.info("Initiating graceful shutdown...")
        self.stop_event.set()
        if self.tray_icon:
            self.tray_icon.stop()
        # The detector loop will check stop_event or be interrupted by sys.exit in signal handler

    def run(self):
        self.logger.info("START: Running Jarvis Launcher...")

        if self.args.calibrate:
            if not self.detector:
                self.logger.error("Detector not initialized. Cannot run calibration.")
                return
            self.logger.info("ENTERING CALIBRATION MODE. Press Ctrl+C to exit.")
            self.detector.calibrate(stop_event=self.stop_event)
            return

        # Start tray icon in a separate thread
        self.logger.info("START: Initializing System Tray...")
        try:
            self.tray_icon = self.create_tray_icon()
            if self.tray_icon:
                def run_tray():
                    try:
                        self.tray_icon.run()
                    except Exception as e:
                        self.logger.error(f"FAIL: System tray icon crashed: {e}", exc_info=True)

                threading.Thread(target=run_tray, daemon=True).start()
                self.logger.info("SUCCESS: System Tray started.")
            else:
                self.logger.info("SUCCESS: System Tray skipped (disabled or not available).")
        except Exception as e:
            self.logger.error(f"FAIL: Failed to create or start tray icon: {e}", exc_info=True)

        # If not minimized, show settings window immediately
        if not self.args.minimized and not self.args.calibrate and not self.args.no_tray:
            self.show_settings()

        def signal_handler(sig, frame):
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.logger.info(f"System ready. Routine '{self.args.routine}' will trigger on double clap.")
        if self.args.dry_run:
            self.logger.info("RUNNING IN DRY-RUN MODE")

        try:
            if self.detector:
                try:
                    self.detector.listen_for_double_clap(
                        callback=lambda: self.on_trigger_routine() or False,
                        stop_event=self.stop_event
                    )
                except Exception as e:
                    self.logger.error(f"FAIL: Clap detector crashed or failed to start: {e}", exc_info=True)
                    self.logger.info("Falling back to idle mode (Tray/UI only).")
                    while not self.stop_event.is_set():
                        time.sleep(1)
            else:
                self.logger.warning("Detector not available. Entering idle mode (Tray/UI only).")
                while not self.stop_event.is_set():
                    time.sleep(1)
        except Exception as e:
            self.logger.error(f"FAIL: Fatal error in main loop: {e}", exc_info=True)
            # Last resort fallback to keep app alive if possible
            while not self.stop_event.is_set():
                time.sleep(1)
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
    parser.add_argument("--minimized", action="store_true", help="Start minimized to tray (don't show UI)")
    return parser.parse_args()

if __name__ == "__main__":
    try:
        args = parse_args()
        startup_mode = "Automatic (Minimized)" if args.minimized else "Manual"
        logger.info(f"START: Jarvis Launcher starting in {startup_mode} mode.")
        logger.info(f"Command line args: {args}")

        # Enable DPI awareness on Windows
        if sys.platform == 'win32':
            try:
                logger.info("START: Setting DPI awareness...")
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
                logger.info("SUCCESS: DPI awareness set.")
            except Exception as e:
                logger.warning(f"FAIL: Could not set DPI awareness: {e}")

        app = JarvisApp(args)
        app.run()
    except Exception as e:
        logger.critical(f"FAIL: UNHANDLED FATAL EXCEPTION: {e}", exc_info=True)
        # On Windows, if we are in pythonw mode, there is no console.
        # For fatal startup errors, we might want a message box if possible.
        if sys.platform == "win32":
             try:
                 ctypes.windll.user32.MessageBoxW(0, f"Jarvis Launcher failed to start:\n\n{e}\n\nCheck logs for details.", "Critical Error", 0x10)
             except:
                 pass
        sys.exit(1)
