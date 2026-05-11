from __future__ import annotations

import os

from src.config_backup import get_backup_dir
from src.logger import get_log_dir
from src.launch_history import get_launch_history_path
from src.ui_models import AppRuntimeSnapshot, RuntimeStatus


def _enabled_text(item: dict) -> str:
    return "enabled" if item.get("enabled", True) else "disabled"


def _delay_text(item: dict) -> str:
    try:
        return f"{float(item.get('delay', 0)):.1f}s"
    except (TypeError, ValueError):
        return str(item.get("delay"))


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
    max_interval: float,
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
        f"- Max interval: {float(max_interval):.2f}\n"
        f"- Log directory: {log_dir}\n"
        f"- Launch history: {get_launch_history_path(log_dir)}\n"
        f"- Config path: {os.path.abspath(config_path)}\n"
        f"- Config backups: {get_backup_dir(config_path)}\n"
    )


def build_routine_launch_plan(routine_name: str, items: list[dict]) -> str:
    lines = [f"Jarvis Routine Launch Plan: {routine_name}"]
    if not items:
        lines.append("- No startup items configured.")
        return "\n".join(lines)

    enabled_count = sum(1 for item in items if isinstance(item, dict) and item.get("enabled", True))
    lines.append(f"- Items: {len(items)} total, {enabled_count} enabled")
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            lines.append(f"{index}. Invalid item: {item!r}")
            continue
        parts = [
            f"{index}. {item.get('name', 'Unnamed')} ({_enabled_text(item)})",
            f"type={item.get('type', 'app')}",
            f"target={item.get('target', '')}",
            f"monitor={item.get('monitor', 'primary')}",
            f"position={item.get('position', 'full')}",
            f"delay={_delay_text(item)}",
        ]
        if item.get("window_title_match"):
            parts.append(f"window_title_match={item['window_title_match']}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)
