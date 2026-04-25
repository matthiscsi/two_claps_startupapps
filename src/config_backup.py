from __future__ import annotations

import os
import shutil
from datetime import datetime

import yaml

from src.validator import validate_config

BACKUP_DIR_NAME = "backups"
BACKUP_KEEP_COUNT = 8


def get_backup_dir(config_path: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(config_path)) or os.getcwd()
    return os.path.join(base_dir, BACKUP_DIR_NAME)


def _backup_sort_key(path: str) -> tuple[float, str]:
    try:
        return (os.path.getmtime(path), path)
    except OSError:
        return (0.0, path)


def list_config_backups(config_path: str, *, backup_dir: str | None = None) -> list[dict]:
    directory = backup_dir or get_backup_dir(config_path)
    if not os.path.isdir(directory):
        return []
    backups = []
    for name in os.listdir(directory):
        if not name.startswith("config-") or not name.endswith((".yaml", ".yml")):
            continue
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        stat = os.stat(path)
        backups.append(
            {
                "path": path,
                "name": name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return sorted(backups, key=lambda item: _backup_sort_key(item["path"]), reverse=True)


def prune_config_backups(config_path: str, *, keep: int = BACKUP_KEEP_COUNT, backup_dir: str | None = None) -> list[str]:
    backups = list_config_backups(config_path, backup_dir=backup_dir)
    removed = []
    for backup in backups[max(0, keep):]:
        try:
            os.remove(backup["path"])
            removed.append(backup["path"])
        except OSError:
            continue
    return removed


def create_config_backup(
    config_path: str,
    *,
    keep: int = BACKUP_KEEP_COUNT,
    backup_dir: str | None = None,
    reason: str = "manual",
) -> str | None:
    if not config_path or not os.path.exists(config_path) or os.path.getsize(config_path) == 0:
        return None

    directory = backup_dir or get_backup_dir(config_path)
    os.makedirs(directory, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    reason_suffix = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in reason.strip().lower())
    reason_suffix = reason_suffix.strip("-") or "manual"
    backup_path = os.path.join(directory, f"config-{stamp}-{reason_suffix}.yaml")
    counter = 2
    while os.path.exists(backup_path):
        backup_path = os.path.join(directory, f"config-{stamp}-{reason_suffix}-{counter}.yaml")
        counter += 1
    shutil.copy2(config_path, backup_path)
    prune_config_backups(config_path, keep=keep, backup_dir=directory)
    return backup_path


def load_config_backup(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("Backup does not contain a config dictionary.")
    validate_config(data)
    return data


def restore_config_backup(config_path: str, backup_path: str, *, keep: int = BACKUP_KEEP_COUNT) -> dict:
    data = load_config_backup(backup_path)
    create_config_backup(config_path, keep=keep, reason="before-restore")
    os.makedirs(os.path.dirname(os.path.abspath(config_path)) or os.getcwd(), exist_ok=True)
    shutil.copy2(backup_path, config_path)
    return data
