# Jarvis Launcher Architecture

This document explains the structure and conventions of the Jarvis Double-Clap Launcher.

## Directory Structure

- `src/`: Core source code.
  - `main.py`: Entry point. Handles CLI args and orchestrates the system.
- `experimental/`: Legacy or experimental features (e.g., AI assistant).
  - `config.py`: Configuration management (YAML).
  - `detector.py`: Clap detection logic using PyAudio and SciPy.
  - `launcher.py`: Routine execution and window management.
  - `audio.py`: TTS and sound feedback.
  - `logger.py`: Logging setup.
- `tests/`: Unit and integration tests.
- `config.yaml`: User configuration (apps, monitors, sensitivity).

## Key Conventions

1. **Modular Design**: Each component (detector, launcher, config) is independent and can be tested separately.
2. **Dry Run**: Always support a `--dry-run` mode to test routines without actually launching apps.
3. **Graceful Failures**: If an app fails to launch or a window cannot be positioned, log the error but don't crash the service.
4. **Windows-First**: While the core logic is cross-platform, window management is specific to Windows.

## Adding New Routine Types

To add a new routine type (e.g., "shell_command"):
1. Update `config.yaml` with the new type.
2. Update `Launcher.launch_item` in `src/launcher.py` to handle the new type.

## Development Workflow

1. Install dependencies: `pip install -r requirements.txt`
2. Run in dev mode: `python -m src.main --dry-run`
3. Run tests: `pytest`
4. Build EXE: `python build_exe.py` (Windows recommended)
