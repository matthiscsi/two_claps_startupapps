from __future__ import annotations

import copy
import os
import re
from typing import Callable, Optional

from src.validator import validate_config

KNOWN_APP_ALIASES = {"discord", "spotify"}


class UIValidationError(ValueError):
    pass


def parse_monitor_value(raw_value: str):
    if isinstance(raw_value, int):
        return raw_value

    text = str(raw_value).strip()
    if text.startswith("Monitor "):
        try:
            return int(text.split(":")[0].split(" ")[1])
        except (IndexError, ValueError):
            return 0

    try:
        return int(text)
    except ValueError:
        return text


def pick_default_monitor_option(monitor_options, current_monitor):
    if not monitor_options:
        return "Monitor 0: 1920x1080 (Primary)"

    selected_option = monitor_options[0]
    if current_monitor is not None:
        for option in monitor_options:
            if option.startswith(f"Monitor {current_monitor}:"):
                return option

    for option in monitor_options:
        if "(Primary)" in option:
            selected_option = option
            break
    return selected_option


def validate_routine_item_inputs(
    *,
    name: str,
    item_type: str,
    target: str,
    path_exists: Callable[[str], bool] = os.path.exists,
) -> Optional[str]:
    clean_name = name.strip()
    clean_target = target.strip()

    if not clean_name:
        raise UIValidationError("Name is required.")
    if not clean_target:
        raise UIValidationError("Target is required.")

    if item_type == "url" and not re.match(r"^https?://", clean_target):
        return "URL does not start with http:// or https://. Save anyway?"

    if item_type in {"app", "shortcut"} and not path_exists(clean_target):
        if clean_target.lower() not in KNOWN_APP_ALIASES:
            return f"Path '{clean_target}' does not seem to exist. Save anyway?"

    return None


def build_routine_item(
    *,
    name: str,
    item_type: str,
    target: str,
    args: str,
    monitor_value,
    position: str,
    delay: float,
    icon: str,
    window_wait_timeout: float | None = None,
    window_poll_interval: float | None = None,
):
    item = {
        "name": name.strip(),
        "type": item_type,
        "target": target.strip(),
        "args": args.strip(),
        "monitor": parse_monitor_value(monitor_value),
        "position": position,
        "delay": float(delay),
        "icon": icon.strip(),
    }
    if window_wait_timeout is not None:
        item["window_wait_timeout"] = max(1.0, float(window_wait_timeout))
    if window_poll_interval is not None:
        item["window_poll_interval"] = max(0.1, float(window_poll_interval))
    return item


def apply_form_state_to_config(config_manager, form_state, startup_apply_result=None):
    config_manager.data["clap_settings"]["threshold"] = float(form_state.threshold)
    config_manager.data["clap_settings"]["min_interval"] = float(form_state.min_interval)
    config_manager.data["audio_settings"]["enabled"] = bool(form_state.audio_enabled)
    config_manager.data["audio_settings"]["mode"] = str(form_state.audio_mode)
    config_manager.data["audio_settings"]["file_path"] = str(form_state.audio_file_path)
    config_manager.data["audio_settings"]["startup_phrase"] = str(form_state.startup_phrase)
    config_manager.data.setdefault("system", {})
    config_manager.data["system"]["startup_delay"] = max(0.0, float(form_state.startup_delay))
    config_manager.data["system"]["active_routine"] = str(form_state.active_routine)

    if startup_apply_result is not None:
        _, actual_state = startup_apply_result
        config_manager.data["system"]["run_on_startup"] = actual_state["enabled"]


def validate_full_config_data(config_data):
    validate_config(config_data)


def detect_duplicate_item_names(items):
    names = [str(item.get("name", "")).strip().lower() for item in items if isinstance(item, dict)]
    seen = set()
    duplicates = set()
    for name in names:
        if not name:
            continue
        if name in seen:
            duplicates.add(name)
        seen.add(name)
    return sorted(duplicates)


def describe_detector_state(*, detector_available: bool, detector_active: bool, state: str, clap_count: int, peak: float, threshold: float):
    if not detector_available:
        return "Device Error", "#a94442"
    if not detector_active:
        return "Waiting For Microphone", "#8a6d3b"

    normalized_state = str(state).upper()
    if clap_count > 0:
        return "Clap Detected", "#d35400"
    if normalized_state == "WAITING":
        return "Cooldown", "#f39c12"
    if normalized_state == "REJECTED":
        return "Ignored Noise", "#7f8c8d"
    if peak > max(0.15, threshold * 1.8):
        return "Too Loud", "#c0392b"
    if peak < max(0.01, threshold * 0.25):
        return "Noise Too Low", "#6c7a89"
    return "Listening", "#2e7d32"


def cloned_config_data(config_data):
    return copy.deepcopy(config_data)
