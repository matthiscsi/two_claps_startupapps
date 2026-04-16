import os
import sys
import logging

logger = logging.getLogger(__name__)

# Try to import winreg for Windows registry access
try:
    import winreg
except ImportError:
    winreg = None

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "JarvisLauncher"

def format_bat_content(work_dir):
    # Properly quote paths for CMD/BAT
    # The 'cd /d' command needs the path in double quotes
    return f'@echo off\ncd /d "{work_dir}"\nstart /b pythonw -m src.main\n'

def format_vbs_script(shortcut_path, target_path, work_dir):
    # Properly escape quotes and handle spaces for VBScript strings
    # In VBScript, quotes inside a string are doubled ""
    vbs_shortcut = shortcut_path.replace('"', '""')
    vbs_target = target_path.replace('"', '""')
    vbs_work = work_dir.replace('"', '""')

    return f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{vbs_shortcut}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{vbs_target}"
oLink.WorkingDirectory = "{vbs_work}"
oLink.Save
"""

def get_startup_command():
    """Returns the command to run the app on startup."""
    if getattr(sys, 'frozen', False):
        # Bundled EXE
        exe_path = sys.executable
        return f'"{exe_path}" --minimized'
    else:
        # Running as script
        python_exe = sys.executable
        script_path = os.path.abspath(sys.modules['__main__'].__file__ if '__main__' in sys.modules else "src/main.py")
        # Ensure we use 'pythonw' if possible to avoid console window
        if python_exe.lower().endswith("python.exe"):
            pythonw_exe = python_exe.lower().replace("python.exe", "pythonw.exe")
            if os.path.exists(pythonw_exe):
                python_exe = pythonw_exe

        # Determine the root directory to set as CWD if needed,
        # but the registry command usually just needs the full command.
        # For a script, we might need: pythonw -m src.main --minimized
        # But we need to be in the right directory.
        # A better way for scripts might be a .bat file or just the full -m path if PYTHONPATH is set.
        # However, for the most reliable startup of the script in dev,
        # we'll assume it's run from the project root.
        root_dir = os.getcwd()
        return f'"{python_exe}" -m src.main --minimized'

def is_startup_enabled(return_command=False):
    """
    Checks if the app is registered in the Windows startup registry.
    If return_command is True, returns (is_enabled, command_string).
    """
    if sys.platform != "win32" or winreg is None:
        return (False, None) if return_command else False

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            try:
                value, _ = winreg.QueryValueEx(key, APP_NAME)
                logger.info(f"Startup registry found: {value}")
                return (True, value) if return_command else True
            except (FileNotFoundError, OSError):
                logger.info("Startup registry entry not found.")
                return (False, None) if return_command else False
    except Exception as e:
        logger.debug(f"Non-critical: Failed to check startup registry: {e}")
        return (False, None) if return_command else False

def get_startup_state():
    """
    Returns canonical startup state from the OS registry as:
    {
      "enabled": bool,
      "command": str|None
    }
    """
    enabled, command = is_startup_enabled(return_command=True)
    state = {"enabled": bool(enabled), "command": command}
    logger.info(f"Startup state read from system: enabled={state['enabled']}, command={state['command']}")
    return state

def set_startup(enabled):
    """Adds or removes the app from the Windows startup registry."""
    if sys.platform != "win32" or winreg is None:
        logger.warning("Startup management is only available on Windows.")
        return False

    # Clean up legacy startup folder shortcut if it exists
    _cleanup_legacy_shortcut()

    try:
        if enabled:
            cmd = get_startup_command()
            logger.info(f"Attempting to enable startup with command: {cmd}")
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            logger.info("SUCCESS: Startup registry entry created/updated.")
        else:
            logger.info("Attempting to disable startup...")
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                        logger.info("SUCCESS: Disabled startup (registry entry removed).")
                    except (FileNotFoundError, OSError):
                        logger.info("Startup registry entry already absent.")
            except (FileNotFoundError, OSError):
                # Key itself might not exist or be accessible
                pass
        return True
    except Exception as e:
        logger.error(f"Failed to update startup registry: {e}")
        return False

def apply_startup_state(enabled):
    """
    Apply desired startup state, verify it from the registry, and return:
    (operation_success, actual_state_dict)
    """
    logger.info(f"Startup toggle requested: enabled={enabled}")
    op_ok = set_startup(enabled)
    actual_state = get_startup_state()
    verified = actual_state["enabled"] == bool(enabled)
    if op_ok and verified:
        logger.info(f"Startup toggle verified successfully: enabled={actual_state['enabled']}")
        return True, actual_state

    logger.error(
        f"Startup toggle verification failed. requested={enabled}, op_ok={op_ok}, actual={actual_state['enabled']}"
    )
    return False, actual_state

def _cleanup_legacy_shortcut():
    """Removes the old .lnk file from the Startup folder if it exists."""
    try:
        startup_folder = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
        if os.path.exists(startup_folder):
            shortcut_path = os.path.join(startup_folder, "JarvisLauncher.lnk")
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
                logger.info("Removed legacy startup shortcut.")

            # Also check for the .bat file created by the old script
            old_bat = os.path.join(os.getcwd(), "run_jarvis.bat")
            if os.path.exists(old_bat):
                os.remove(old_bat)
                logger.info("Removed legacy startup .bat file.")
    except Exception as e:
        logger.debug(f"Legacy cleanup failed (non-critical): {e}")

# Keeping add_to_startup for backward compatibility if needed,
# but it now just uses the new registry logic.
def add_to_startup():
    set_startup(True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1 and sys.argv[1] == "--disable":
        set_startup(False)
    else:
        set_startup(True)
    print(f"Startup enabled: {is_startup_enabled()}")
