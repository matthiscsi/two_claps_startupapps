import webbrowser
import subprocess
import time
import logging
import os
import psutil
from screeninfo import get_monitors

try:
    import win32gui
    import win32con
except ImportError:
    win32gui = None
    win32con = None

logger = logging.getLogger(__name__)

class Launcher:
    def __init__(self, config, dry_run=False):
        self.config = config
        self.dry_run = dry_run
        self.monitors = get_monitors()
        logger.info(f"Detected {len(self.monitors)} monitors.")

    def launch_routine(self, routine_name):
        routines = self.config.routines
        if routine_name not in routines:
            logger.error(f"Routine '{routine_name}' not found in config.")
            return

        logger.info(f"Executing routine: {routine_name}")
        for item in routines[routine_name]:
            try:
                self.launch_item(item)
            except Exception as e:
                logger.error(f"Error executing routine item {item.get('name')}: {e}")

    def launch_item(self, item):
        name = item.get("name")
        item_type = item.get("type")
        path = item.get("path")
        monitor_idx = item.get("monitor", 0)
        position = item.get("position", "full")
        delay = item.get("delay", 0)

        if self.is_app_running(name):
            logger.info(f"{name} is already running. Repositioning...")
            self.position_window(name, monitor_idx, position=position, is_browser=(item_type=="url"))
            return

        if delay > 0:
            logger.info(f"Waiting {delay}s before launching {name}...")
            if not self.dry_run:
                time.sleep(delay)

        logger.info(f"Launching {name} ({item_type}) at {path} on monitor {monitor_idx}")

        if self.dry_run:
            logger.info(f"[DRY-RUN] Would launch {name}")
            return

        try:
            if item_type == "url":
                webbrowser.open(path)
                self.wait_and_position(name, monitor_idx, position, is_browser=True)
            elif item_type == "app":
                self.launch_app(path)
                self.wait_and_position(name, monitor_idx, position, is_browser=False)
            else:
                logger.warning(f"Unknown item type: {item_type}")
        except Exception as e:
            logger.error(f"Failed to launch {name}: {e}")

    def launch_app(self, path):
        if path.lower() == "discord":
            local_app_data = os.environ.get("LOCALAPPDATA")
            if local_app_data:
                discord_path = os.path.join(local_app_data, "Discord", "Update.exe")
                if os.path.exists(discord_path):
                    subprocess.Popen([discord_path, "--processStart", "Discord.exe"])
                    return
            subprocess.Popen(["start", "discord"], shell=True)
        elif path.lower() == "spotify":
            subprocess.Popen(["start", "spotify"], shell=True)
        else:
            subprocess.Popen(path, shell=True)

    def is_app_running(self, name):
        # 1. Try robust window detection
        if self.find_window_robustly(name) is not None:
            return True

        # 2. Fallback to process-based detection (Windows)
        logger.info(f"Window for {name} not found. Checking processes...")
        name_lower = name.lower()
        try:
            for proc in psutil.process_iter(['name', 'exe']):
                proc_name = proc.info['name']
                if proc_name and name_lower in proc_name.lower():
                    logger.info(f"Found process matching {name}: {proc_name}")
                    return True

                # Check exe path for cases like Spotify.exe
                exe_path = proc.info['exe']
                if exe_path and name_lower in exe_path.lower():
                    logger.info(f"Found process exe matching {name}: {exe_path}")
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

        return False

    def find_window_robustly(self, name):
        if win32gui is None: return None

        found_hwnd = [None]

        # App-specific class names for more robust detection
        class_map = {
            "spotify": "SpotifyMainWindow",
            "discord": "Chrome_WidgetWin_1" # Discord uses Electron
        }
        target_class = class_map.get(name.lower())

        def callback(hwnd, extra):
            if not win32gui.IsWindowVisible(hwnd):
                return

            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)

            # Match by title or by class name if specific app
            if name.lower() in title.lower() or (target_class and class_name == target_class):
                # For apps like Discord, multiple windows might have the same class,
                # but only one has a meaningful title (usually).
                if target_class and class_name == target_class:
                    if not title: # Skip invisible/empty title windows of the same class
                        return

                if not found_hwnd[0]:
                    found_hwnd[0] = hwnd

        win32gui.EnumWindows(callback, None)
        return found_hwnd[0]

    def wait_and_position(self, name, monitor_idx, position, is_browser, timeout=10):
        """Wait for window to appear before positioning."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            hwnd = self.find_window_robustly(name)
            if hwnd:
                self.apply_position(hwnd, monitor_idx, position)
                return
            time.sleep(0.5)
        logger.warning(f"Timeout waiting for window: {name}")

    def position_window(self, name, monitor_idx, position="full", is_browser=False):
        hwnd = self.find_window_robustly(name)
        if hwnd:
            self.apply_position(hwnd, monitor_idx, position)
        else:
            logger.warning(f"Could not find window for {name} to position it.")

    def apply_position(self, hwnd, monitor_idx, position):
        if monitor_idx >= len(self.monitors):
            monitor_idx = 0
        target_monitor = self.monitors[monitor_idx]

        logger.info(f"Applying position {position} to hwnd {hwnd} on monitor {monitor_idx}")
        try:
            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            x, y = target_monitor.x, target_monitor.y
            width, height = target_monitor.width, target_monitor.height

            if position == "left":
                width = width // 2
            elif position == "right":
                x = x + (width // 2)
                width = width // 2

            # Use SetWindowPos for reliability
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, x, y, width, height, win32con.SWP_SHOWWINDOW)
        except Exception as e:
            logger.error(f"Error positioning window: {e}")
