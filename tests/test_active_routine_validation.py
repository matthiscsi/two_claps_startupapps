import pytest

from src.validator import ConfigValidationError, validate_config


def test_active_routine_must_exist():
    with pytest.raises(ConfigValidationError, match="active_routine"):
        validate_config(
            {
                "routines": {"morning_routine": {"items": []}},
                "system": {"active_routine": "missing_routine"},
            }
        )


def test_active_routine_valid():
    validate_config(
        {
            "routines": {"morning_routine": {"items": []}},
            "system": {"active_routine": "morning_routine"},
        }
    )
