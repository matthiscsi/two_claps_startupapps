import os
import sys
import subprocess

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

def add_to_startup():
    if sys.platform != "win32":
        print("Startup helper only works on Windows.")
        return

    # Use a .vbs script to create a shortcut to the EXE or the python command
    startup_folder = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")

    # Check if we are running as EXE (bundled) or script
    if getattr(sys, 'frozen', False):
        target_path = sys.executable
        work_dir = os.path.dirname(sys.executable)
    else:
        # For script, we need to create a .bat file
        current_dir = os.getcwd()
        target_path = os.path.join(current_dir, "run_jarvis.bat")
        bat_content = format_bat_content(current_dir)
        with open(target_path, "w") as f:
            f.write(bat_content)
        work_dir = current_dir

    shortcut_path = os.path.join(startup_folder, "JarvisLauncher.lnk")
    vbs_script = format_vbs_script(shortcut_path, target_path, work_dir)

    vbs_file = "create_shortcut.vbs"
    with open(vbs_file, "w") as f:
        f.write(vbs_script)

    try:
        subprocess.run(["cscript", vbs_file], check=True)
        print(f"Successfully added Jarvis Launcher to startup: {shortcut_path}")
    except Exception as e:
        print(f"Failed to create startup shortcut: {e}")
        print(f"Ensure target exists: {target_path}")
    finally:
        if os.path.exists(vbs_file):
            os.remove(vbs_file)

if __name__ == "__main__":
    add_to_startup()
