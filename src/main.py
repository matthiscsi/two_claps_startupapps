import logging
import sys
import argparse
import os
import signal
import time
import threading
import ctypes
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
from src.startup_helper import get_startup_state, apply_startup_state, get_startup_command
from src.ui_models import AppRuntimeSnapshot

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

        # Reconcile startup state with config
        if sys.platform == "win32":
            try:
                self.logger.info("START: Reconciling startup registration with configuration...")
                intended_startup = self.config.system_settings.get("run_on_startup")
                startup_state = get_startup_state()
                is_enabled = startup_state["enabled"]
                current_cmd = startup_state["command"]
                expected_cmd = get_startup_command()

                # Migration logic: if key is missing (None), infer from current system state
                if intended_startup is None:
                    self.logger.info(f"Startup setting 'run_on_startup' is missing in config. Inferring from system state: {is_enabled}")
                    intended_startup = is_enabled
                    # Persist inferred value back to config
                    if 'system' not in self.config.data:
                        self.config.data['system'] = {}
                    self.config.data['system']['run_on_startup'] = intended_startup
                    self.config.save()
                    self.logger.info(f"Migrated missing 'run_on_startup' to: {intended_startup}")

                if intended_startup:
                    if not is_enabled or current_cmd != expected_cmd:
                        self.logger.info(f"Startup out of sync (intended: {intended_startup}, enabled: {is_enabled}, path mismatch: {current_cmd != expected_cmd}). Re-registering...")
                        apply_startup_state(True)
                    else:
                        self.logger.info("Startup registration is correct and in sync.")
                else:
                    if is_enabled:
                        self.logger.info("Startup is enabled in registry but disabled in config. De-registering...")
                        apply_startup_state(False)
                    else:
                        self.logger.info("Startup is correctly disabled.")
                self.logger.info("SUCCESS: Startup reconciliation complete.")
            except Exception as e:
                self.logger.error(f"FAIL: Error during startup reconciliation: {e}")

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

        # 3. Subsystem initialization (critical only, keep startup fast)
        self.logger.info("START: Initializing Launcher...")
        try:
            self.launcher = Launcher(self.config, dry_run=args.dry_run)
            self.logger.info("SUCCESS: Launcher initialized.")
        except Exception as e:
            self.logger.error(f"FAIL: Failed to initialize Launcher: {e}", exc_info=True)
            self.launcher = None

        # Non-critical systems are initialized after tray/UI become available.
        self.audio = None
        self.detector = None
        self.runtime_ready_event = threading.Event()
        self.start_time_monotonic = time.monotonic()
        self.startup_delay_seconds = max(0.0, float(self.config.system_settings.get("startup_delay", 0.0)))
        self.listening_enabled = True
        configured_active_routine = self.config.system_settings.get("active_routine")
        if configured_active_routine and configured_active_routine in self.config.routines:
            self.args.routine = configured_active_routine

        self.routine_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.tray_icon = None

    def on_trigger_routine(self, source="unknown"):
        def run():
            elapsed = time.monotonic() - self.start_time_monotonic
            remaining_startup_delay = self.startup_delay_seconds - elapsed
            if remaining_startup_delay > 0:
                self.logger.info(
                    "EVENT: routine_trigger_delayed source=%s remaining=%.2fs",
                    source,
                    remaining_startup_delay,
                )
                # Delay only routine execution, never tray/UI initialization.
                time.sleep(remaining_startup_delay)

            # Use non-blocking acquire to ignore duplicate triggers while routine is running
            if not self.routine_lock.acquire(blocking=False):
                self.logger.warning("EVENT: routine_trigger_ignored source=%s reason=already_running", source)
                return
            try:
                self.logger.info("EVENT: routine_triggered source=%s routine=%s", source, self.args.routine)
                if self.audio:
                    self.audio.play_startup()
                if self.launcher:
                    self.launcher.launch_routine(self.args.routine)
                if self.audio:
                    self.audio.play_success()
            finally:
                self.routine_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def on_clap_callback(self):
        if not self.listening_enabled:
            self.logger.info("EVENT: clap_ignored reason=listening_paused")
            return False
        self.on_trigger_routine(source="double_clap")
        return False

    def on_trigger_item(self, item, source="unknown"):
        if not isinstance(item, dict):
            self.logger.warning("EVENT: routine_item_test_ignored reason=invalid_item source=%s", source)
            return

        def run():
            if not self.routine_lock.acquire(blocking=False):
                self.logger.warning("EVENT: routine_item_test_ignored source=%s reason=already_running", source)
                return
            try:
                item_name = item.get("name", "Unnamed")
                self.logger.info("EVENT: routine_item_test source=%s item=%s", source, item_name)
                if self.launcher:
                    self.launcher.launch_item(item)
            finally:
                self.routine_lock.release()

        threading.Thread(target=run, daemon=True).start()

    def set_active_routine(self, routine_name, source="unknown"):
        if routine_name not in self.config.routines:
            self.logger.warning("EVENT: routine_switch_failed source=%s routine=%s reason=not_found", source, routine_name)
            return False
        self.args.routine = routine_name
        self.config.data.setdefault("system", {})
        self.config.data["system"]["active_routine"] = routine_name
        self.logger.info("EVENT: routine_switched source=%s routine=%s", source, routine_name)
        if self.tray_icon:
            try:
                self.tray_icon.update_menu()
            except Exception:
                pass
        return True

    def toggle_listening(self):
        self.listening_enabled = not self.listening_enabled
        self.logger.info("EVENT: listening_toggled enabled=%s", self.listening_enabled)
        if self.tray_icon:
            try:
                self.tray_icon.update_menu()
            except Exception:
                pass

    def runtime_snapshot(self):
        return AppRuntimeSnapshot(
            listening_enabled=self.listening_enabled,
            active_routine=self.args.routine,
            runtime_ready=self.runtime_ready_event.is_set(),
        )

    def _on_settings_saved(self):
        self.logger.info("EVENT: settings_saved_and_applied")
        # Update components with new config
        if self.detector:
            self.detector.refresh_settings(self.config.clap_settings)

        if self.audio:
            self.audio.enabled = self.config.audio_settings.get('enabled', True)
            self.audio.maybe_initialize()
        self.startup_delay_seconds = max(0.0, float(self.config.system_settings.get("startup_delay", 0.0)))
        active_routine = self.config.system_settings.get("active_routine")
        if active_routine:
            self.set_active_routine(active_routine, source="settings_apply")

    def _initialize_runtime_subsystems(self):
        self.logger.info("START: Initializing deferred runtime subsystems (audio + clap detector)...")

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

        self.logger.info("START: Initializing Clap Detector...")
        try:
            self.detector = ClapDetector(self.config)
            self.logger.info("SUCCESS: Clap Detector initialized.")
        except Exception as e:
            self.logger.error(f"FAIL: Failed to initialize ClapDetector: {e}", exc_info=True)
            self.detector = None
        finally:
            self.runtime_ready_event.set()

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
            self.on_trigger_routine(source="tray_manual")

        def on_settings(icon, item):
            self.logger.info("EVENT: tray_settings_clicked")
            self.show_settings()

        def on_toggle_listening(icon, item):
            self.toggle_listening()

        def make_routine_handler(routine_name):
            def _handler(icon, item):
                self.set_active_routine(routine_name, source="tray_switch")
            return _handler

        routine_items = [
            pystray.MenuItem(
                routine_name,
                make_routine_handler(routine_name),
                checked=lambda item, rn=routine_name: self.args.routine == rn,
                radio=True,
            )
            for routine_name in sorted(self.config.routines.keys())
        ]

        menu = pystray.Menu(
            pystray.MenuItem(lambda item: f"Trigger {self.args.routine}", on_trigger),
            pystray.MenuItem(
                "Listening Enabled",
                on_toggle_listening,
                checked=lambda item: self.listening_enabled,
            ),
            pystray.MenuItem("Switch Routine", pystray.Menu(*routine_items)),
            pystray.MenuItem("Settings...", on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", on_quit)
        )
        return pystray.Icon("JarvisLauncher", load_icon(), "Jarvis Launcher", menu=menu)

    def show_settings(self):
        self.logger.info(
            "EVENT: opening_settings_ui runtime_ready=%s detector_available=%s",
            self.runtime_ready_event.is_set(),
            self.detector is not None,
        )
        # SettingsUI handles singleton internally via _instance
        ui = SettingsUI(
            self.config,
            on_save_callback=self._on_settings_saved,
            detector=self.detector,
            runtime_snapshot_provider=self.runtime_snapshot,
            trigger_routine_callback=self.on_trigger_routine,
            switch_routine_callback=self.set_active_routine,
            trigger_item_callback=self.on_trigger_item,
        )
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
        if self.detector:
            self.detector._cleanup_audio()
        if self.audio:
            self.audio.shutdown()
        # The detector loop will check stop_event or be interrupted by sys.exit in signal handler

    def run(self):
        self.logger.info("START: Running Jarvis Launcher...")

        if self.args.calibrate:
            if not self.detector:
                self._initialize_runtime_subsystems()
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

        # Defer non-critical startup work until tray/UI are already available.
        threading.Thread(target=self._initialize_runtime_subsystems, daemon=True).start()

        def signal_handler(sig, frame):
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.logger.info(f"System ready. Routine '{self.args.routine}' will trigger on double clap.")
        if self.args.dry_run:
            self.logger.info("RUNNING IN DRY-RUN MODE")

        try:
            self.runtime_ready_event.wait()
            if self.detector:
                try:
                    self.detector.listen_for_double_clap(
                        callback=self.on_clap_callback,
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
