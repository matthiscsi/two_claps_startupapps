import pytest
import os
from src.config import Config

def test_config_default_values():
    config = Config("test_config.yaml")
    assert config.get("clap_settings")["threshold"] == 0.15
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

def test_config_deep_copy_regression():
    from src.config import DEFAULT_CONFIG

    # Create first instance and mutate its nested data
    config1 = Config("config1.yaml")
    config1.data["clap_settings"]["threshold"] = 99.9

    # Create second instance
    config2 = Config("config2.yaml")

    # Check that DEFAULT_CONFIG and config2 are NOT affected by config1 mutation
    assert DEFAULT_CONFIG["clap_settings"]["threshold"] == 0.15
    assert config2.data["clap_settings"]["threshold"] == 0.15

    if os.path.exists("config1.yaml"): os.remove("config1.yaml")
    if os.path.exists("config2.yaml"): os.remove("config2.yaml")

def test_config_invalid_root_type_falls_back_to_defaults(tmp_path):
    config_file = tmp_path / "invalid_root.yaml"
    config_file.write_text("- not\n- a\n- dict\n", encoding="utf-8")

    config = Config(str(config_file))
    assert config.clap_settings["threshold"] == 0.15

def test_config_save_preserves_top_level_order(tmp_path):
    config_file = tmp_path / "ordered_config.yaml"
    config = Config(str(config_file))
    config.save()

    content = config_file.read_text(encoding="utf-8")
    assert content.index("clap_settings:") < content.index("routines:")
