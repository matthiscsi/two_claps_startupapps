import pytest

from src.validator import ConfigValidationError, validate_config


def test_invalid_clap_filter_range_raises():
    with pytest.raises(ConfigValidationError, match="filter_low must be lower"):
        validate_config(
            {
                "clap_settings": {
                    "filter_low": 2000,
                    "filter_high": 1500,
                }
            }
        )


def test_invalid_threshold_range_raises():
    with pytest.raises(ConfigValidationError, match="clap_settings.threshold must be between"):
        validate_config(
            {
                "clap_settings": {
                    "threshold": 2.0,
                }
            }
        )
