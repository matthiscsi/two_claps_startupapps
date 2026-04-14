import os
import sys
import subprocess

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
        target_path = os.path.join(os.getcwd(), "run_jarvis.bat")
        with open(target_path, "w") as f:
            f.write(f"@echo off\ncd /d {os.getcwd()}\nstart /b pythonw -m src.main\n")
        work_dir = os.getcwd()

    shortcut_path = os.path.join(startup_folder, "JarvisLauncher.lnk")

    vbs_script = f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{target_path}"
oLink.WorkingDirectory = "{work_dir}"
oLink.Save
"""
    vbs_file = "create_shortcut.vbs"
    with open(vbs_file, "w") as f:
        f.write(vbs_script)

    try:
        subprocess.run(["cscript", vbs_file], check=True)
        print(f"Successfully added Jarvis Launcher to startup: {shortcut_path}")
    except Exception as e:
        print(f"Failed to create startup shortcut: {e}")
    finally:
        if os.path.exists(vbs_file):
            os.remove(vbs_file)

if __name__ == "__main__":
    add_to_startup()
