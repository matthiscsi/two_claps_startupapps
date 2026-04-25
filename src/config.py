import yaml
import os
import sys
import copy
import shutil
import logging
from src.validator import validate_config, ConfigValidationError

logger = logging.getLogger(__name__)

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

DEFAULT_CONFIG = {
    "clap_settings": {
        "threshold": 0.15,
        "min_interval": 0.2,
        "filter_low": 1400,
        "filter_high": 1800,
        "order": 2,
        "sampling_rate": 44100,
        "frame_duration": 0.02
    },
    "routines": {
        "morning_routine": {
            "items": [
                {
                    "name": "HLN News",
                    "enabled": True,
                    "type": "url",
                    "target": "https://www.hln.be/",
                    "monitor": "primary",
                    "position": "full",
                    "delay": 0
                },
                {
                    "name": "Discord",
                    "enabled": True,
                    "type": "app",
                    "target": "discord",
                    "monitor": 1,
                    "position": "full",
                    "delay": 2
                },
                {
                    "name": "Spotify",
                    "enabled": True,
                    "type": "app",
                    "target": "spotify",
                    "monitor": 1,
                    "position": "full",
                    "delay": 1
                }
            ]
        }
    },
    "audio_settings": {
        "enabled": False,
        "mode": "tts",  # "tts" or "file"
        "file_path": "",
        "startup_phrase": "Good morning, Boss. Initializing systems.",
        "success_phrase": "Systems online. Have a productive day."
    },
    "system": {
        "run_on_startup": None,
        "startup_delay": 0.0,
        "active_routine": "morning_routine",
        "first_run_completed": False,
        "last_control_center_version": "2",
    },
    "logging": {
        "level": "INFO",
        "file": "launcher.log"
    }
}

class Config:
    def __init__(self, config_path="config.yaml"):
        self.config_path = config_path
        self.data = copy.deepcopy(DEFAULT_CONFIG)

        if not self.config_path:
            print("Using default internal configuration (no config path provided).")
            return

        # If config doesn't exist locally, try to extract it from bundled assets
        try:
            if not os.path.exists(self.config_path):
                try:
                    bundled_path = get_resource_path("config.yaml")
                    if os.path.exists(bundled_path) and bundled_path != os.path.abspath(self.config_path):
                        shutil.copy(bundled_path, self.config_path)
                        print(f"Extracted bundled config to {self.config_path}")
                except Exception as e:
                    print(f"Note: Could not extract bundled config: {e}")
        except TypeError:
            # Handles cases where config_path might be an invalid type for os.path.exists
            print(f"Warning: Invalid config path type: {type(self.config_path)}. Using defaults.")
            return

        if os.path.exists(self.config_path):
            self.load()
        else:
            self.save()

    def load(self):
        logger.info(f"START: Loading config from {self.config_path}")
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f)
                if user_config is None:
                    logger.warning("Config file is empty. Using defaults.")
                    return
                if not isinstance(user_config, dict):
                    raise ConfigValidationError("Root config must be a dictionary.")

                self._migrate_config(user_config)
                merged = self._deep_merge(copy.deepcopy(self.data), user_config)
                validate_config(merged)
                self.data = merged
                logger.info("SUCCESS: Config validated.")
            logger.info(f"SUCCESS: Loaded config from {self.config_path}")
        except (yaml.YAMLError, ConfigValidationError) as e:
            logger.error(
                "FAIL: Invalid config '%s': %s. Falling back to defaults. "
                "Tip: open Settings and save to regenerate a safe config.",
                self.config_path,
                e,
            )
        except Exception as e:
            logger.error(f"FAIL: Error loading config '{self.config_path}': {e}. Using defaults.")

    def _migrate_config(self, config):
        """Migrate old config format to new format."""
        if "routines" in config:
            for name, routine in config["routines"].items():
                if isinstance(routine, list):
                    # Old format: list of items directly under routine name
                    print(f"Migrating routine '{name}' to new format...")
                    items = []
                    for item in routine:
                        new_item = copy.deepcopy(item)
                        if "path" in new_item:
                            new_item["target"] = new_item.pop("path")
                        if "position" not in new_item:
                            new_item["position"] = "full"
                        items.append(new_item)
                    config["routines"][name] = {"items": items}

        system = config.setdefault("system", {})
        if "active_routine" not in system:
            routines = config.get("routines", {})
            if isinstance(routines, dict) and routines:
                first_routine_name = next(iter(routines.keys()))
                system["active_routine"] = first_routine_name
            else:
                system["active_routine"] = "morning_routine"
        system.setdefault("first_run_completed", False)
        system.setdefault("last_control_center_version", "2")

    def save(self, create_backup=False, backup_reason="save"):
        if create_backup:
            try:
                from src.config_backup import create_config_backup

                create_config_backup(self.config_path, reason=backup_reason)
            except Exception:
                logger.warning("Could not create config backup before save.", exc_info=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.data, f, default_flow_style=False)

    def get(self, key, default=None):
        return self.data.get(key, default)

    @property
    def clap_settings(self):
        return self.data["clap_settings"]

    @property
    def routines(self):
        return self.data["routines"]

    @property
    def audio_settings(self):
        return self.data["audio_settings"]

    @property
    def system_settings(self):
        return self.data.get(
            "system",
            {
                "run_on_startup": None,
                "startup_delay": 0.0,
                "active_routine": "morning_routine",
                "first_run_completed": False,
                "last_control_center_version": "2",
            },
        )

    def _deep_merge(self, base, update):
        for key, value in update.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
