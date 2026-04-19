# Jarvis Double-Clap Launcher

Jarvis is a Windows-first background utility that listens for a double clap and launches a named startup routine (apps, URLs, and shortcuts), then positions windows across monitors.

## What It Does

- Detects clap-like transients and triggers on two valid claps.
- Runs configurable routines from `config.yaml`.
- Reuses already-running apps when possible instead of relaunching.
- Supports monitor targeting (`primary`, `secondary`, or index) and window positions (`full`, `left`, `right`, `top`, `bottom`).
- Runs from system tray with manual trigger, settings, and graceful quit.

## Quick Start (Windows)

1. Install Python 3.10+.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run:

```bash
python -m src.main
```

4. Open tray icon -> `Settings...` and tune microphone threshold if needed.

## First-Run Tips

- Start with a quiet room and clap once or twice to verify meter movement.
- If false positives happen, raise `clap_settings.threshold`.
- If double-clap feels too strict, lower `clap_settings.min_interval` slightly or increase `clap_settings.max_interval`.
- Keep routine item names close to real window titles for better repositioning.

## Configuration

Jarvis reads `config.yaml`. Invalid config now falls back safely to defaults and logs actionable errors.

### Example

```yaml
clap_settings:
  threshold: 0.15
  min_interval: 0.2
  max_interval: 2.0
  filter_low: 1400
  filter_high: 1800
  frame_duration: 0.02
  sampling_rate: 44100

system:
  run_on_startup: true
  startup_delay: 0.0

routines:
  morning_routine:
    items:
      - name: "News"
        type: "url"
        target: "https://www.hln.be/"
        monitor: "primary"
        position: "full"
      - name: "Discord"
        type: "app"
        target: "discord"
        monitor: "secondary"
        position: "left"
        delay: 2
        window_wait_timeout: 20
```

### Routine Item Fields

- `name` (required): Display name and window matching hint.
- `type` (required): `app`, `url`, `shortcut`.
- `target` (required): Executable path/command, URL, or `.lnk`.
- `monitor`: Monitor index or `primary`/`secondary`.
- `position`: `full`, `left`, `right`, `top`, `bottom`.
- `delay`: Delay before launch.
- `window_title_match`: Optional title substring override.
- `window_wait_timeout`: Optional seconds to wait for window before positioning timeout.
- `window_poll_interval`: Optional polling interval when waiting for window.

## CLI

```bash
python -m src.main --help
```

Main flags:
- `--routine <name>`
- `--dry-run`
- `--calibrate`
- `--no-audio`
- `--no-tray`
- `--minimized`

## Build Windows Executable

```bash
python build_exe.py
```

Output: `dist/JarvisLauncher.exe`

## Testing

```bash
python -m pytest -q
```

## Troubleshooting

- `PyAudio is not installed`: clap detection cannot start. Install PyAudio wheel for your Python version.
- `Timeout waiting for window`: app launched but did not expose a window title in time. Increase item `delay` or `window_wait_timeout`.
- `target was not found`: verify absolute paths for `app` and `shortcut` items.
- No tray icon: run without `--no-tray`, or verify desktop/session supports tray integration.
- Startup toggle mismatch: run Jarvis as the same Windows user that owns the startup registry entry.

## CI / Release

- `CI` workflow: multi-version Python tests + source compile sanity check.
- `Build and Release Windows Executable`: runs tests, builds with PyInstaller, uploads artifact, and publishes tagged releases.

## Notes

- Experimental and legacy code is isolated in `experimental/`.
- This project is optimized for Windows behavior first.
