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
    def __init__(self, config, dry_run=False, monitors=None):
        self.config = config
        self.dry_run = dry_run
        try:
            self.monitors = monitors if monitors is not None else get_monitors()
        except Exception as e:
            logger.warning(f"Could not detect monitors: {e}. Falling back to single default monitor.")
            # Fallback for headless/testing environments
            from dataclasses import dataclass
            @dataclass
            class MockMonitor:
                x: int = 0
                y: int = 0
                width: int = 1920
                height: int = 1080
            self.monitors = [MockMonitor()]

        logger.info(f"Detected {len(self.monitors)} monitors.")

    def launch_routine(self, routine_name):
        routines = self.config.routines
        if routine_name not in routines:
            logger.error(f"Routine '{routine_name}' not found in config.")
            return

        logger.info(f"--- Starting Routine: {routine_name} ---")
        items = routines[routine_name].get("items", [])
        logger.info(f"Found {len(items)} items to launch.")

        for i, item in enumerate(items):
            try:
                logger.info(f"[{i+1}/{len(items)}] Processing: {item.get('name')}")
                self.launch_item(item)
            except Exception as e:
                logger.error(f"Error executing routine item {item.get('name')}: {e}", exc_info=True)

        logger.info(f"--- Routine {routine_name} Completed ---")

    def launch_item(self, item):
        name = item.get("name")
        item_type = item.get("type")
        target = item.get("target")
        monitor = item.get("monitor", 0)
        position = item.get("position", "full")
        delay = item.get("delay", 0)
        window_title_match = item.get("window_title_match")

        # Normalize monitor
        monitor_idx = self._resolve_monitor_index(monitor)

        if self.is_app_running(name, window_title_match):
            logger.info(f"{name} is already running.")
            if self.dry_run:
                logger.info(f"[DRY-RUN] Would reposition {name}")
            else:
                self.position_window(name, monitor_idx, position=position,
                                     window_title_match=window_title_match,
                                     is_browser=(item_type=="url"))
            return

        if delay > 0:
            logger.info(f"Waiting {delay}s before launching {name}...")
            if not self.dry_run:
                time.sleep(delay)

        logger.info(f"Launching {name} ({item_type}) at {target} on monitor {monitor_idx}")

        if self.dry_run:
            logger.info(f"[DRY-RUN] Would launch {name}")
            return

        try:
            if item_type == "url":
                webbrowser.open(target)
                self.wait_and_position(name, monitor_idx, position,
                                       window_title_match=window_title_match, is_browser=True)
            elif item_type == "app":
                self.launch_app(target)
                self.wait_and_position(name, monitor_idx, position,
                                       window_title_match=window_title_match, is_browser=False)
            elif item_type == "shortcut":
                os.startfile(target)
                self.wait_and_position(name, monitor_idx, position,
                                       window_title_match=window_title_match, is_browser=False)
            else:
                logger.warning(f"Unknown item type: {item_type}")
        except Exception as e:
            logger.error(f"Failed to launch {name}: {e}")

    def _resolve_monitor_index(self, monitor):
        if monitor == "primary":
            return 0
        if monitor == "secondary":
            return 1 if len(self.monitors) > 1 else 0
        if isinstance(monitor, int):
            return monitor if monitor < len(self.monitors) else 0
        return 0

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

    def is_app_running(self, name, window_title_match=None):
        # 1. Try robust window detection
        if self.find_window_robustly(name, window_title_match) is not None:
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

    def find_window_robustly(self, name, window_title_match=None):
        if win32gui is None: return None

        found_hwnd = [None]

        # App-specific class names for more robust detection
        class_map = {
            "spotify": "SpotifyMainWindow",
            "discord": "Chrome_WidgetWin_1" # Discord uses Electron
        }
        target_class = class_map.get(name.lower())
        match_pattern = (window_title_match or name).lower()

        def callback(hwnd, extra):
            if not win32gui.IsWindowVisible(hwnd):
                return

            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)

            # Match by title or by class name if specific app
            if match_pattern in title.lower() or (target_class and class_name == target_class):
                # For apps like Discord, multiple windows might have the same class,
                # but only one has a meaningful title (usually).
                if target_class and class_name == target_class:
                    if not title: # Skip invisible/empty title windows of the same class
                        return

                if not found_hwnd[0]:
                    found_hwnd[0] = hwnd

        win32gui.EnumWindows(callback, None)
        return found_hwnd[0]

    def wait_and_position(self, name, monitor_idx, position, is_browser, window_title_match=None, timeout=15):
        """Wait for window to appear before positioning."""
        logger.info(f"Waiting up to {timeout}s for window '{name}'...")
        start_time = time.time()
        try:
            while time.time() - start_time < timeout:
                hwnd = self.find_window_robustly(name, window_title_match)
                if hwnd:
                    logger.info(f"Window found for '{name}' (hwnd: {hwnd}) after {time.time() - start_time:.1f}s.")
                    # Add a small extra delay after window appears to ensure it's ready for placement
                    time.sleep(1)
                    self.apply_position(hwnd, monitor_idx, position)
                    return
                time.sleep(1.0)
            logger.warning(f"Timeout waiting for window: {name}")
        except Exception as e:
            logger.error(f"Error in wait_and_position for '{name}': {e}", exc_info=True)

    def position_window(self, name, monitor_idx, position="full", window_title_match=None, is_browser=False):
        hwnd = self.find_window_robustly(name, window_title_match)
        if hwnd:
            self.apply_position(hwnd, monitor_idx, position)
        else:
            logger.warning(f"Could not find window for {name} to position it.")

    def apply_position(self, hwnd, monitor_idx, position):
        # Ensure monitor_idx is an integer
        if not isinstance(monitor_idx, int):
            monitor_idx = self._resolve_monitor_index(monitor_idx)

        if monitor_idx >= len(self.monitors):
            logger.warning(f"Monitor index {monitor_idx} out of range. Defaulting to monitor 0.")
            monitor_idx = 0
        target_monitor = self.monitors[monitor_idx]

        logger.info(f"Applying position '{position}' to hwnd {hwnd} on monitor {monitor_idx} ({target_monitor.width}x{target_monitor.height} @ {target_monitor.x},{target_monitor.y})")
        try:
            # Restore if minimized
            if win32gui and win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            x, y = target_monitor.x, target_monitor.y
            width, height = target_monitor.width, target_monitor.height

            if position == "left":
                width = width // 2
            elif position == "right":
                x = x + (width // 2)
                width = width // 2

            if win32gui:
                # Use SetWindowPos for reliability
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, x, y, width, height, win32con.SWP_SHOWWINDOW)
                logger.info(f"Window {hwnd} positioned successfully at {x},{y} ({width}x{height})")
            else:
                logger.info(f"[NON-WINDOWS] Would position window {hwnd} at {x},{y} ({width}x{height})")
        except Exception as e:
            logger.error(f"Error positioning window {hwnd}: {e}")
