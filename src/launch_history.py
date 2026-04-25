from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Iterable

from src.logger import get_log_dir

HISTORY_FILE_NAME = "launch_history.jsonl"
VALID_STATUSES = {"success", "skipped", "failure"}


def get_launch_history_path(log_dir: str | None = None) -> str:
    return os.path.join(log_dir or get_log_dir(), HISTORY_FILE_NAME)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_launch_result(
    result: dict | None,
    *,
    routine: str,
    source: str,
    dry_run: bool = False,
    timestamp: str | None = None,
) -> dict:
    result = result if isinstance(result, dict) else {}
    status = str(result.get("status", "failure")).lower()
    if status not in VALID_STATUSES:
        status = "failure"

    return {
        "timestamp": timestamp or utc_timestamp(),
        "routine": str(result.get("routine") or routine or ""),
        "item": str(result.get("item") or result.get("name") or ""),
        "source": str(result.get("source") or source or "unknown"),
        "status": status,
        "dry_run": bool(result.get("dry_run", dry_run)),
        "message": str(result.get("message") or ""),
        "item_type": str(result.get("item_type") or ""),
        "target": str(result.get("target") or ""),
    }


def append_launch_history(
    result: dict | None,
    *,
    routine: str,
    source: str,
    dry_run: bool = False,
    path: str | None = None,
) -> dict:
    entry = normalize_launch_result(result, routine=routine, source=source, dry_run=dry_run)
    history_path = path or get_launch_history_path()
    os.makedirs(os.path.dirname(os.path.abspath(history_path)), exist_ok=True)
    with open(history_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def append_launch_history_many(
    results: Iterable[dict | None],
    *,
    routine: str,
    source: str,
    dry_run: bool = False,
    path: str | None = None,
) -> list[dict]:
    return [
        append_launch_history(result, routine=routine, source=source, dry_run=dry_run, path=path)
        for result in results
    ]


def read_launch_history(
    *,
    path: str | None = None,
    limit: int = 100,
    status: str | None = None,
    routine: str | None = None,
) -> list[dict]:
    history_path = path or get_launch_history_path()
    if not os.path.exists(history_path):
        return []

    normalized_status = str(status).lower() if status else None
    entries: list[dict] = []
    with open(history_path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            if normalized_status and str(entry.get("status", "")).lower() != normalized_status:
                continue
            if routine and entry.get("routine") != routine:
                continue
            entries.append(entry)

    if limit <= 0:
        return entries
    return entries[-limit:]


def clear_launch_history(path: str | None = None) -> None:
    history_path = path or get_launch_history_path()
    os.makedirs(os.path.dirname(os.path.abspath(history_path)), exist_ok=True)
    with open(history_path, "w", encoding="utf-8"):
        pass


def format_launch_history(entries: Iterable[dict]) -> str:
    lines = ["Jarvis Launch History"]
    for entry in entries:
        item = entry.get("item") or "(routine)"
        dry = " dry-run" if entry.get("dry_run") else ""
        lines.append(
            f"- {entry.get('timestamp', '')} [{entry.get('status', 'unknown')}{dry}] "
            f"{entry.get('routine', '')} / {item}: {entry.get('message', '')}"
        )
    if len(lines) == 1:
        lines.append("- No launch history recorded yet.")
    return "\n".join(lines)
