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
                    "type": "url",
                    "target": "https://www.hln.be/",
                    "monitor": "primary",
                    "position": "full",
                    "delay": 0
                },
                {
                    "name": "Discord",
                    "type": "app",
                    "target": "discord",
                    "monitor": 1,
                    "position": "full",
                    "delay": 2
                },
                {
                    "name": "Spotify",
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
            with open(self.config_path, "r") as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    self._migrate_config(user_config)
                    # Basic deep merge (one level for simplicity)
                    for key, value in user_config.items():
                        if isinstance(value, dict) and key in self.data:
                            self.data[key].update(value)
                        else:
                            self.data[key] = value

                    # Validate after loading and merging
                    try:
                        validate_config(self.data)
                        logger.info("SUCCESS: Config validated.")
                    except ConfigValidationError as e:
                        logger.warning(f"FAIL: Config validation warning: {e}. Some settings may be reset to defaults.")
            logger.info(f"SUCCESS: Loaded config from {self.config_path}")
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

    def save(self):
        with open(self.config_path, "w") as f:
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
