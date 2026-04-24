from __future__ import annotations

import os

from src.logger import get_log_dir
from src.ui_models import AppRuntimeSnapshot, RuntimeStatus


def resolve_log_file_path(config_data: dict, log_dir: str | None = None) -> str:
    """Resolve the configured log file path exactly like the app logger does."""
    log_name = str((config_data or {}).get("logging", {}).get("file", "launcher.log"))
    if os.path.isabs(log_name):
        return log_name
    return os.path.join(log_dir or get_log_dir(), log_name)


def tail_text_file(path: str, line_count: int = 80) -> str:
    """Return the last lines of a text file with friendly empty/missing states."""
    if not os.path.exists(path):
        return f"Log file not found yet: {path}"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
        return "".join(lines[-line_count:]).strip() or "(Log file is currently empty)"
    except Exception as exc:
        return f"Unable to read log file {path}: {exc}"


def build_troubleshooting_summary(
    *,
    snapshot: AppRuntimeSnapshot,
    status: RuntimeStatus,
    threshold: float,
    min_interval: float,
    log_dir: str,
    config_path: str,
    startup_enabled: bool | None = None,
) -> str:
    startup_text = "unknown" if startup_enabled is None else str(bool(startup_enabled))
    return (
        "Jarvis Troubleshooting Summary\n"
        f"- Active routine: {snapshot.active_routine}\n"
        f"- Listening enabled: {snapshot.listening_enabled}\n"
        f"- Runtime ready: {snapshot.runtime_ready}\n"
        f"- Startup enabled: {startup_text}\n"
        f"- Detector state: {status.state}\n"
        f"- Detector active: {status.detector_active}\n"
        f"- Clap count: {status.clap_count}\n"
        f"- Last peak: {status.peak:.3f}\n"
        f"- Threshold: {float(threshold):.3f}\n"
        f"- Min interval: {float(min_interval):.2f}\n"
        f"- Log directory: {log_dir}\n"
        f"- Config path: {os.path.abspath(config_path)}\n"
    )
