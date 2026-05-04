# Changelog

## Unreleased

### Improved
- Default config path now uses `%APPDATA%\JarvisLauncher\config.yaml` with safe migration from legacy local `config.yaml`.
- Tray menu now exposes explicit production actions: Open Settings, Enable/Disable Listening, Run Routine Now, View Logs, and Quit.
- Clap detector now supports optional `clap_settings.input_device_index` with fallback to default microphone if the configured device is unavailable.
- Windows release workflow now publishes portable zip and installer artifacts in addition to the standalone exe.
- Refactored clap timing logic into a dedicated `DoubleClapStateMachine` for cleaner behavior and better testability.
- Improved clap detector timing to use monotonic clock logic and explicit state transitions.
- Added runtime-safe clap settings refresh path (`ClapDetector.refresh_settings`).
- Hardened config loading with strict validation before applying user values.
- Improved config error messages with explicit value/range checks for clap settings.
- Added launcher guardrails for missing app/shortcut targets with actionable logs.
- Added per-item window wait tuning (`window_wait_timeout`, `window_poll_interval`).
- Improved app shutdown cleanup for detector audio stream and pygame mixer resources.
- Updated CI to run on Python 3.10 and 3.11 with compile sanity check.
- Hardened build script with root checks and PyInstaller improvements.
- Rewrote README with clearer setup, onboarding, troubleshooting, and release guidance.
- Decomposed settings UI responsibilities into dedicated modules for form models, routine-state operations, and UI logic helpers.
- Added Apply/Save/Reset workflow in settings for clearer active-vs-unsaved state.
- Improved runtime observability with explicit UI/app lifecycle event logs and trigger source tracking.
- Added runtime status text in settings to clarify detector availability and current clap state.
- Fixed settings window layout overflow with scrollable tab content and anchored footer actions.
- Improved general settings wording to be more user-facing and less technical.
- Added routine selection, cloning, deletion, item duplication, and manual routine trigger from settings.
- Added tray controls to pause/resume listening and switch active routine quickly.
- Added active routine persistence in config (`system.active_routine`) with validation.
- Modernized settings visual hierarchy with cleaner spacing, stronger section labels, and consistent button styles.
- Replaced clap numeric fields with guided sliders and live value displays.
- Added lightweight tooltips and an `Advanced` tab for troubleshooting guidance.
- Improved routine editor readability with clearer column labels, type markers, delay formatting, and empty-state messaging.
- Reduced intrusive popups by preferring inline status feedback for common actions.

### Added
- Inno Setup installer script with integrated uninstall support, startup entry cleanup, running-process stop, and optional user-data removal prompt.
- New config path tests covering AppData default path and legacy-config migration behavior.
- New clap-state unit tests: double clap, cooldown ignore, timeout reset.
- New validator range tests for clap filter and threshold validation.
- New launcher guardrail tests for missing paths.
- New tests for extracted UI logic (`test_ui_logic.py`).
- New tests for routine-state store behavior (`test_ui_routines.py`).
- New guided calibration logic with recommendations (`src/calibration.py`) and tests.
- New UI status logic tests and active routine validation tests.
- New UI theme helper module (`src/ui_theme.py`) for reusable styling/tooltip behavior.
