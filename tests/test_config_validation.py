import pytest
import os
import yaml
from src.config import Config
from src.validator import validate_config, ConfigValidationError

def test_config_migration(tmp_path):
    config_file = tmp_path / "old_config.yaml"
    old_data = {
        "routines": {
            "morning_routine": [
                {"name": "App1", "type": "app", "path": "path1", "monitor": 0}
            ]
        }
    }
    with open(config_file, "w") as f:
        yaml.dump(old_data, f)

    config = Config(str(config_file))

    # Check if migrated
    assert "morning_routine" in config.routines
    assert "items" in config.routines["morning_routine"]
    assert config.routines["morning_routine"]["items"][0]["target"] == "path1"
    assert config.routines["morning_routine"]["items"][0]["name"] == "App1"
    assert config.system_settings["first_run_completed"] is False

def test_validate_valid_config():
    valid_data = {
        "routines": {
            "test": {
                "items": [
                    {"name": "App", "type": "app", "target": "calc.exe", "monitor": "primary", "position": "full", "delay": 1}
                ]
            }
        }
    }
    # Should not raise
    validate_config(valid_data)

def test_validate_invalid_type():
    invalid_data = {
        "routines": {
            "test": {
                "items": [
                    {"name": "App", "type": "invalid", "target": "calc.exe"}
                ]
            }
        }
    }
    with pytest.raises(ConfigValidationError, match="unsupported type"):
        validate_config(invalid_data)

def test_validate_missing_target():
    invalid_data = {
        "routines": {
            "test": {
                "items": [
                    {"name": "App", "type": "app"}
                ]
            }
        }
    }
    with pytest.raises(ConfigValidationError, match="missing required field 'target'"):
        validate_config(invalid_data)

def test_validate_invalid_monitor():
    invalid_data = {
        "routines": {
            "test": {
                "items": [
                    {"name": "App", "type": "app", "target": "calc.exe", "monitor": "invalid_alias"}
                ]
            }
        }
    }
    with pytest.raises(ConfigValidationError, match="invalid monitor alias"):
        validate_config(invalid_data)


def test_validate_disabled_item_and_wait_settings():
    valid_data = {
        "routines": {
            "test": {
                "items": [
                    {
                        "name": "App",
                        "enabled": False,
                        "type": "app",
                        "target": "calc.exe",
                        "window_wait_timeout": 2,
                        "window_poll_interval": 0.2,
                    }
                ]
            }
        }
    }
    validate_config(valid_data)


def test_validate_invalid_enabled_value():
    invalid_data = {
        "routines": {
            "test": {
                "items": [
                    {"name": "App", "enabled": "yes", "type": "app", "target": "calc.exe"}
                ]
            }
        }
    }
    with pytest.raises(ConfigValidationError, match="invalid enabled"):
        validate_config(invalid_data)


def test_validate_first_run_system_metadata_types():
    invalid_first_run = {
        "routines": {"test": {"items": [{"name": "App", "type": "app", "target": "calc.exe"}]}},
        "system": {"active_routine": "test", "first_run_completed": "nope"},
    }
    with pytest.raises(ConfigValidationError, match="first_run_completed"):
        validate_config(invalid_first_run)

    invalid_version = {
        "routines": {"test": {"items": [{"name": "App", "type": "app", "target": "calc.exe"}]}},
        "system": {"active_routine": "test", "last_control_center_version": 2},
    }
    with pytest.raises(ConfigValidationError, match="last_control_center_version"):
        validate_config(invalid_version)
