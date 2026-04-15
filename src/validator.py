import logging
import re

logger = logging.getLogger(__name__)

class ConfigValidationError(Exception):
    pass

def validate_config(data):
    """
    Validate the configuration data.
    Raises ConfigValidationError if any issues are found.
    """
    if not isinstance(data, dict):
        raise ConfigValidationError("Config must be a dictionary.")

    _validate_clap_settings(data.get("clap_settings"))
    _validate_routines(data.get("routines"))
    _validate_audio_settings(data.get("audio_settings"))

def _validate_clap_settings(settings):
    if settings is None:
        return
    if not isinstance(settings, dict):
        raise ConfigValidationError("clap_settings must be a dictionary.")

    # Optional: validate specific fields
    if "threshold" in settings and not isinstance(settings["threshold"], (int, float)):
        raise ConfigValidationError("clap_settings.threshold must be a number.")
    if "min_interval" in settings and (not isinstance(settings["min_interval"], (int, float)) or settings["min_interval"] < 0):
        raise ConfigValidationError("clap_settings.min_interval must be a non-negative number.")

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

    valid_types = ["app", "url", "shortcut"]
    if item_type not in valid_types:
        raise ConfigValidationError(f"Item '{name}' at {context} has unsupported type '{item_type}'. Valid types are: {', '.join(valid_types)}")

    if not target or not isinstance(target, str):
        raise ConfigValidationError(f"Item '{name}' at {context} has an invalid target.")

    if item_type == "url":
        # Simple URL validation
        if not re.match(r'^https?://', target):
            logger.warning(f"Item '{name}' target '{target}' does not look like a valid URL (should start with http:// or https://).")

    # Monitor validation
    monitor = item.get("monitor", 0)
    if not isinstance(monitor, (int, str)):
         raise ConfigValidationError(f"Item '{name}' has invalid monitor '{monitor}'. Must be an integer or 'primary'/'secondary'.")
    if isinstance(monitor, str) and monitor not in ["primary", "secondary"]:
         raise ConfigValidationError(f"Item '{name}' has invalid monitor alias '{monitor}'. Valid aliases are: primary, secondary")

    # Position validation
    position = item.get("position", "full")
    valid_positions = ["full", "left", "right", "top", "bottom"]
    if position not in valid_positions:
        raise ConfigValidationError(f"Item '{name}' has invalid position '{position}'. Valid positions are: {', '.join(valid_positions)}")

    # Delay validation
    delay = item.get("delay", 0)
    if not isinstance(delay, (int, float)) or delay < 0:
        raise ConfigValidationError(f"Item '{name}' has invalid delay '{delay}'. Must be a non-negative number.")

def _validate_audio_settings(settings):
    if settings is None:
        return
    if not isinstance(settings, dict):
        raise ConfigValidationError("audio_settings must be a dictionary.")
