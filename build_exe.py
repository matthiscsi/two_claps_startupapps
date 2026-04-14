import PyInstaller.__main__
import os
import sys

def build():
    # Determine separator for path
    sep = os.pathsep

    params = [
        'src/main.py',
        '--name=JarvisLauncher',
        '--onefile',
        '--clean',
        '--add-data=config.yaml:.',
        # Include hidden imports if necessary
        '--hidden-import=pkg_resources.py2_warn', # Sometimes needed for gTTS/others
    ]

    if sys.platform == 'win32':
        params.append('--windowed') # Hide console on Windows
        params.append('--icon=NONE') # Add icon if you have one

    print(f"Running PyInstaller with: {params}")
    PyInstaller.__main__.run(params)

if __name__ == "__main__":
    # Create a dummy config if it doesn't exist so it can be bundled
    if not os.path.exists('config.yaml'):
        from src.config import Config
        Config('config.yaml')

    build()
