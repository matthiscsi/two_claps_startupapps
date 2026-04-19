# Changelog

## Unreleased

### Improved
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

### Added
- New clap-state unit tests: double clap, cooldown ignore, timeout reset.
- New validator range tests for clap filter and threshold validation.
- New launcher guardrail tests for missing paths.
- New tests for extracted UI logic (`test_ui_logic.py`).
- New tests for routine-state store behavior (`test_ui_routines.py`).
- New guided calibration logic with recommendations (`src/calibration.py`) and tests.
- New UI status logic tests and active routine validation tests.
