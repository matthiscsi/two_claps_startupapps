import webbrowser
import subprocess
import time
import logging
import os
from screeninfo import get_monitors

try:
    import win32gui
    import win32con
    import pygetwindow as gw
except ImportError:
    win32gui = None
    win32con = None
    gw = None

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
            self.launch_item(item)

    def launch_item(self, item):
        name = item.get("name")
        item_type = item.get("type")
        path = item.get("path")
        monitor_idx = item.get("monitor", 0)
        delay = item.get("delay", 0)

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
                # Browser windows are hard to target immediately, we might need to wait
                time.sleep(1)
                self.position_window(name, monitor_idx, is_browser=True)
            elif item_type == "app":
                self.launch_app(path)
                # Wait a bit for the app to open
                time.sleep(2)
                self.position_window(name, monitor_idx)
            else:
                logger.warning(f"Unknown item type: {item_type}")
        except Exception as e:
            logger.error(f"Failed to launch {name}: {e}")

    def launch_app(self, path):
        # Special handling for common apps if needed
        if path.lower() == "discord":
            # On Windows, discord might be in LocalAppData
            local_app_data = os.environ.get("LOCALAPPDATA")
            if local_app_data:
                discord_path = os.path.join(local_app_data, "Discord", "Update.exe")
                if os.path.exists(discord_path):
                    subprocess.Popen([discord_path, "--processStart", "Discord.exe"])
                    return
            subprocess.Popen(["start", "discord"], shell=True) # Fallback
        elif path.lower() == "spotify":
            subprocess.Popen(["start", "spotify"], shell=True)
        else:
            subprocess.Popen(path, shell=True)

    def position_window(self, name, monitor_idx, is_browser=False):
        if win32gui is None or gw is None:
            logger.warning("Window management not available (non-Windows or missing libs).")
            return

        if monitor_idx >= len(self.monitors):
            logger.warning(f"Monitor index {monitor_idx} out of range. Defaulting to 0.")
            monitor_idx = 0

        target_monitor = self.monitors[monitor_idx]

        # Best effort to find the window
        # For browsers, the title changes. For Discord/Spotify, they are usually stable.
        time.sleep(1) # Give it another second

        found_window = None

        # Try finding by name in title
        all_windows = gw.getAllWindows()
        for win in all_windows:
            if name.lower() in win.title.lower():
                found_window = win
                break

        if not found_window and is_browser:
            # Try finding the active browser window
            found_window = gw.getActiveWindow()

        if found_window:
            logger.info(f"Positioning window '{found_window.title}' to monitor {monitor_idx}")
            try:
                # Move and maximize or just resize
                # win.moveTo(target_monitor.x, target_monitor.y)
                # win.maximize()

                # Using win32gui for more reliability
                hwnd = found_window._hWnd
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOP,
                                     target_monitor.x, target_monitor.y,
                                     target_monitor.width, target_monitor.height,
                                     win32con.SWP_SHOWWINDOW)
                # win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            except Exception as e:
                logger.error(f"Error positioning window: {e}")
        else:
            logger.warning(f"Could not find window for {name} to position it.")
