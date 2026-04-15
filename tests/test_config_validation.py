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
