import os
import sys
import PyInstaller.__main__

def build():
    # Determine separator for path
    sep = ';' if sys.platform == 'win32' else ':'

    if not os.path.exists("src/main.py"):
        raise FileNotFoundError("src/main.py not found. Run build_exe.py from the repository root.")

    params = [
        'src/main.py',
        '--name=JarvisLauncher',
        '--onefile',
        '--clean',
        '--noconfirm',
        f'--add-data=config.yaml{sep}.',
        # Bundles the tray icon plus Control Center toolbar icons under assets/ui.
        f'--add-data=assets{sep}assets',
        '--paths=.',
        # Include hidden imports if necessary
        '--hidden-import=pkg_resources.py2_warn', # Sometimes needed for gTTS/others
        '--collect-submodules=pystray',
    ]

    if sys.platform == 'win32':
        params.append('--windowed') # Hide console on Windows
        params.append('--icon=assets/icon.ico') # Add icon if you have one

    print(f"Running PyInstaller with: {params}")
    PyInstaller.__main__.run(params)

if __name__ == "__main__":
    # Create a dummy config if it doesn't exist so it can be bundled
    if not os.path.exists('config.yaml'):
        from src.config import Config
        Config('config.yaml')

    build()
