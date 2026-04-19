from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SettingsFormState:
    threshold: float
    min_interval: float
    audio_enabled: bool
    audio_mode: str
    audio_file_path: str
    startup_phrase: str
    startup_delay: float
    startup_enabled: Optional[bool]
    active_routine: str

    @classmethod
    def from_config(cls, config, startup_enabled: Optional[bool] = None) -> "SettingsFormState":
        return cls(
            threshold=float(config.clap_settings.get("threshold", 0.15)),
            min_interval=float(config.clap_settings.get("min_interval", 0.2)),
            audio_enabled=bool(config.audio_settings.get("enabled", False)),
            audio_mode=str(config.audio_settings.get("mode", "tts")),
            audio_file_path=str(config.audio_settings.get("file_path", "")),
            startup_phrase=str(config.audio_settings.get("startup_phrase", "")),
            startup_delay=float(config.system_settings.get("startup_delay", 0.0)),
            startup_enabled=startup_enabled,
            active_routine=str(config.system_settings.get("active_routine", "morning_routine")),
        )


@dataclass
class RuntimeStatus:
    detector_available: bool
    detector_active: bool
    state: str
    clap_count: int
    peak: float


@dataclass
class AppRuntimeSnapshot:
    listening_enabled: bool
    active_routine: str
    runtime_ready: bool
