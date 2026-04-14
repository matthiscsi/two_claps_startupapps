import pytest
import os
from src.config import Config

def test_config_default_values():
    config = Config("test_config.yaml")
    assert config.get("clap_settings")["threshold"] == 0.2
    assert "morning_routine" in config.routines
    if os.path.exists("test_config.yaml"):
        os.remove("test_config.yaml")

def test_config_load_custom_values():
    with open("custom_config.yaml", "w") as f:
        f.write("clap_settings:\n  threshold: 0.5\n")

    config = Config("custom_config.yaml")
    assert config.clap_settings["threshold"] == 0.5
    # Ensure other defaults are preserved
    assert config.clap_settings["filter_low"] == 1400

    os.remove("custom_config.yaml")
