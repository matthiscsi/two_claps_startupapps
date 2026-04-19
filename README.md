# Jarvis Double-Clap Launcher

Jarvis is a Windows-first background utility that listens for a double clap and launches a named startup routine (apps, URLs, and shortcuts), then positions windows across monitors.

## What It Does

- Detects clap-like transients and triggers on two valid claps.
- Runs configurable routines from `config.yaml`.
- Reuses already-running apps when possible instead of relaunching.
- Supports monitor targeting (`primary`, `secondary`, or index) and window positions (`full`, `left`, `right`, `top`, `bottom`).
- Runs from system tray with manual trigger, settings, and graceful quit.
- Provides guided clap calibration and live runtime status in settings.
- Supports selecting and switching active routines quickly from tray and settings.

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
5. Use `Guided Calibration...` in the General tab for first-run setup.

## First-Run Tips

- Start with a quiet room and clap once or twice to verify meter movement.
- Prefer guided calibration before changing values manually.
- If false positives happen, raise `clap_settings.threshold`.
- If one clap counts twice, raise `clap_settings.min_interval`.
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
  active_routine: morning_routine

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

### System Fields

- `system.active_routine`: Default routine used by clap trigger and tray actions.

## Architecture

Core modules:
- `src/main.py`: app lifecycle orchestration (tray, runtime initialization, clap listener loop, shutdown).
- `src/detector.py` + `src/clap_state.py`: clap signal processing and double-clap state machine.
- `src/launcher.py`: routine launching, app/window detection, positioning.
- `src/config.py` + `src/validator.py`: config load, migration, validation.
- `src/calibration.py`: guided calibration recommendation logic.

UI modules:
- `src/ui.py`: Tk view orchestration and widget wiring.
- `src/ui_models.py`: typed UI form/runtime state objects.
- `src/ui_logic.py`: UI-side validation, monitor parsing, config-apply helpers.
- `src/ui_routines.py`: routine item store operations (add/edit/remove/reorder).
- `src/ui_layout.py`: scroll-safe settings layout helpers for DPI/smaller displays.

### Extension Points

- Add new UI panel: create tab widgets in `src/ui.py` and keep non-widget rules in `src/ui_logic.py`.
- Add new routine item fields: update `build_routine_item` in `src/ui_logic.py`, then extend launcher handling.
- Add new validation rules: extend `src/validator.py`; UI will surface save errors through existing error flow.
- Add new clap tuning settings: wire defaults in `src/config.py`, validate in `src/validator.py`, and apply in `ClapDetector.refresh_settings`.

## Settings Experience

- The settings window now keeps action buttons visible and uses scrollable tab content.
- General tab provides plain-language clap controls plus live state (`Listening`, `Noise Too Low`, `Clap Detected`, `Cooldown`, `Ignored Noise`, `Device Error`).
- Guided Calibration:
  - Measures ambient peaks.
  - Collects clap samples.
  - Recommends threshold and cooldown.
  - Applies values with one click (then `Apply`/`Save` persists).
- Routines tab now supports:
  - Selecting active routine.
  - Creating, cloning, deleting routines.
  - Duplicating items.
  - Triggering selected routine immediately.

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
- Calibration unavailable: detector stream is not ready yet. Wait for runtime to initialize and try again.
- Settings clipping on high DPI: scroll inside the tab content; footer buttons stay anchored and always visible.

## CI / Release

- `CI` workflow: multi-version Python tests + source compile sanity check.
- `Build and Release Windows Executable`: runs tests, builds with PyInstaller, uploads artifact, and publishes tagged releases.

## Notes

- Experimental and legacy code is isolated in `experimental/`.
- This project is optimized for Windows behavior first.
