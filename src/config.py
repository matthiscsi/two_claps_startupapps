import yaml
import os
import sys
import copy
import shutil

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
        "threshold": 0.2,
        "min_interval": 0.2,
        "filter_low": 1400,
        "filter_high": 1800,
        "order": 2,
        "sampling_rate": 44100,
        "frame_duration": 0.02
    },
    "routines": {
        "morning_routine": [
            {
                "name": "HLN News",
                "type": "url",
                "path": "https://www.hln.be/",
                "monitor": 0,  # Main monitor
                "delay": 0
            },
            {
                "name": "Discord",
                "type": "app",
                "path": "discord", # Assuming it's in PATH or handled by special logic
                "monitor": 1,
                "delay": 2
            },
            {
                "name": "Spotify",
                "type": "app",
                "path": "spotify",
                "monitor": 1,
                "delay": 1
            }
        ]
    },
    "audio_settings": {
        "enabled": True,
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

        # If config doesn't exist locally, try to extract it from bundled assets
        if not os.path.exists(config_path):
            try:
                bundled_path = get_resource_path("config.yaml")
                if os.path.exists(bundled_path) and bundled_path != os.path.abspath(config_path):
                    shutil.copy(bundled_path, config_path)
                    print(f"Extracted bundled config to {config_path}")
            except Exception as e:
                print(f"Note: Could not extract bundled config: {e}")

        if os.path.exists(config_path):
            self.load()
        else:
            self.save()

    def load(self):
        with open(self.config_path, "r") as f:
            user_config = yaml.safe_load(f)
            if user_config:
                # Basic deep merge (one level for simplicity)
                for key, value in user_config.items():
                    if isinstance(value, dict) and key in self.data:
                        self.data[key].update(value)
                    else:
                        self.data[key] = value

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
