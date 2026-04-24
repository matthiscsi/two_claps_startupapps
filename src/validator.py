import logging
import os
import re

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    pass


VALID_ITEM_TYPES = {"app", "url", "shortcut"}
VALID_MONITOR_ALIASES = {"primary", "secondary"}
VALID_POSITIONS = {"full", "left", "right", "top", "bottom"}


def validate_config(data):
    """Validate full config structure and value ranges."""
    if not isinstance(data, dict):
        raise ConfigValidationError("Config must be a dictionary.")

    _validate_clap_settings(data.get("clap_settings"))
    _validate_routines(data.get("routines"))
    _validate_audio_settings(data.get("audio_settings"))
    _validate_system_settings(data.get("system"), data.get("routines"))


def _validate_clap_settings(settings):
    if settings is None:
        return
    if not isinstance(settings, dict):
        raise ConfigValidationError("clap_settings must be a dictionary.")

    _require_number(settings, "threshold", min_value=0.0, max_value=1.0, context="clap_settings")
    _require_number(settings, "min_interval", min_value=0.0, max_value=5.0, context="clap_settings")
    _require_number(settings, "max_interval", min_value=0.1, max_value=10.0, context="clap_settings")
    _require_number(settings, "frame_duration", min_value=0.005, max_value=0.2, context="clap_settings")
    _require_number(
        settings, "sampling_rate", min_value=8000, max_value=192000, context="clap_settings", integer=True
    )
    _require_number(settings, "filter_low", min_value=20, max_value=10000, context="clap_settings")
    _require_number(settings, "filter_high", min_value=20, max_value=20000, context="clap_settings")

    filter_low = settings.get("filter_low")
    filter_high = settings.get("filter_high")
    if isinstance(filter_low, (int, float)) and isinstance(filter_high, (int, float)):
        if filter_low >= filter_high:
            raise ConfigValidationError("clap_settings.filter_low must be lower than clap_settings.filter_high.")


def _validate_routines(routines):
    if routines is None:
        return
    if not isinstance(routines, dict):
        raise ConfigValidationError("routines must be a dictionary.")

    for name, routine in routines.items():
        if not isinstance(routine, dict):
            raise ConfigValidationError(f"Routine '{name}' must be a dictionary.")

        items = routine.get("items")
        if items is None:
            raise ConfigValidationError(f"Routine '{name}' is missing 'items' list.")
        if not isinstance(items, list):
            raise ConfigValidationError(f"Routine '{name}.items' must be a list.")

        for i, item in enumerate(items):
            _validate_item(item, f"routines.{name}.items[{i}]")


def _validate_item(item, context):
    if not isinstance(item, dict):
        raise ConfigValidationError(f"Item at {context} must be a dictionary.")

    required_fields = ["name", "type", "target"]
    for field in required_fields:
        if field not in item:
            raise ConfigValidationError(f"Item at {context} is missing required field '{field}'.")

    name = item["name"]
    item_type = item["type"]
    target = item["target"]

    if not name or not isinstance(name, str):
        raise ConfigValidationError(f"Item at {context} has an invalid name.")

    if item_type not in VALID_ITEM_TYPES:
        raise ConfigValidationError(
            f"Item '{name}' at {context} has unsupported type '{item_type}'. "
            f"Valid types are: {', '.join(sorted(VALID_ITEM_TYPES))}"
        )

    if not target or not isinstance(target, str):
        raise ConfigValidationError(f"Item '{name}' at {context} has an invalid target.")

    if item_type == "url" and not re.match(r"^https?://", target):
        logger.warning(
            "Item '%s' target '%s' does not look like a valid URL (should start with http:// or https://).",
            name,
            target,
        )

    enabled = item.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigValidationError(f"Item '{name}' has invalid enabled value '{enabled}'. Must be true or false.")

    monitor = item.get("monitor", 0)
    if not isinstance(monitor, (int, str)):
        raise ConfigValidationError(
            f"Item '{name}' has invalid monitor '{monitor}'. Must be an integer or 'primary'/'secondary'."
        )
    if isinstance(monitor, str) and monitor not in VALID_MONITOR_ALIASES:
        raise ConfigValidationError(
            f"Item '{name}' has invalid monitor alias '{monitor}'. "
            f"Valid aliases are: {', '.join(sorted(VALID_MONITOR_ALIASES))}"
        )

    position = item.get("position", "full")
    if position not in VALID_POSITIONS:
        raise ConfigValidationError(
            f"Item '{name}' has invalid position '{position}'. "
            f"Valid positions are: {', '.join(sorted(VALID_POSITIONS))}"
        )

    delay = item.get("delay", 0)
    if not isinstance(delay, (int, float)) or delay < 0:
        raise ConfigValidationError(f"Item '{name}' has invalid delay '{delay}'. Must be a non-negative number.")

    if "window_wait_timeout" in item:
        wait_timeout = item["window_wait_timeout"]
        if not isinstance(wait_timeout, (int, float)) or wait_timeout < 1:
            raise ConfigValidationError(f"Item '{name}' has invalid window_wait_timeout '{wait_timeout}'. Must be at least 1 second.")

    if "window_poll_interval" in item:
        poll_interval = item["window_poll_interval"]
        if not isinstance(poll_interval, (int, float)) or poll_interval < 0.1:
            raise ConfigValidationError(f"Item '{name}' has invalid window_poll_interval '{poll_interval}'. Must be at least 0.1 seconds.")


def _validate_audio_settings(settings):
    if settings is None:
        return
    if not isinstance(settings, dict):
        raise ConfigValidationError("audio_settings must be a dictionary.")

    valid_modes = ["tts", "file"]
    mode = settings.get("mode", "tts")
    if mode not in valid_modes:
        raise ConfigValidationError(f"audio_settings.mode must be one of: {', '.join(valid_modes)}")

    if mode == "file":
        file_path = settings.get("file_path")
        if not file_path:
            logger.warning("Audio mode is 'file' but no file_path is provided.")
        elif not os.path.exists(file_path):
            logger.warning("Audio file not found: %s", file_path)


def _validate_system_settings(settings, routines):
    if settings is None:
        return
    if not isinstance(settings, dict):
        raise ConfigValidationError("system settings must be a dictionary.")

    if "run_on_startup" in settings and settings["run_on_startup"] is not None and not isinstance(
        settings["run_on_startup"], bool
    ):
        raise ConfigValidationError("system.run_on_startup must be a boolean or null.")
    if "startup_delay" in settings:
        delay = settings["startup_delay"]
        if not isinstance(delay, (int, float)) or delay < 0:
            raise ConfigValidationError("system.startup_delay must be a non-negative number.")
    if "active_routine" in settings:
        routine_name = settings["active_routine"]
        if not isinstance(routine_name, str) or not routine_name.strip():
            raise ConfigValidationError("system.active_routine must be a non-empty string.")
        if isinstance(routines, dict) and routines and routine_name not in routines:
            raise ConfigValidationError(
                f"system.active_routine '{routine_name}' does not exist in routines."
            )


def _require_number(settings, key, min_value, max_value, context, integer=False):
    if key not in settings:
        return
    value = settings[key]
    expected_types = (int,) if integer else (int, float)
    if not isinstance(value, expected_types):
        expected = "an integer" if integer else "a number"
        raise ConfigValidationError(f"{context}.{key} must be {expected}.")
    if value < min_value or value > max_value:
        raise ConfigValidationError(f"{context}.{key} must be between {min_value} and {max_value}. Got: {value}")
