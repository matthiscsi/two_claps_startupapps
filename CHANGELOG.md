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

### Added
- New clap-state unit tests: double clap, cooldown ignore, timeout reset.
- New validator range tests for clap filter and threshold validation.
- New launcher guardrail tests for missing paths.
