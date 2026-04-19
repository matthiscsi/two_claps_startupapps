import pytest

from src.ui_logic import (
    UIValidationError,
    apply_form_state_to_config,
    build_routine_item,
    parse_monitor_value,
    validate_routine_item_inputs,
)
from src.ui_models import SettingsFormState


class DummyConfig:
    def __init__(self):
        self.data = {
            "clap_settings": {"threshold": 0.15, "min_interval": 0.2},
            "audio_settings": {"enabled": False, "mode": "tts", "file_path": "", "startup_phrase": "Hi"},
            "system": {"startup_delay": 0.0, "run_on_startup": None, "active_routine": "morning_routine"},
        }


def test_parse_monitor_value_from_label():
    assert parse_monitor_value("Monitor 2: 1920x1080 @ 0,0") == 2
    assert parse_monitor_value("primary") == "primary"
    assert parse_monitor_value("3") == 3


def test_validate_routine_item_inputs_requires_name_and_target():
    with pytest.raises(UIValidationError):
        validate_routine_item_inputs(name="", item_type="app", target="calc.exe")
    with pytest.raises(UIValidationError):
        validate_routine_item_inputs(name="Calc", item_type="app", target="")


def test_validate_routine_item_inputs_warns_for_non_existing_path():
    msg = validate_routine_item_inputs(
        name="Thing",
        item_type="app",
        target="C:/missing/path.exe",
        path_exists=lambda _p: False,
    )
    assert "does not seem to exist" in msg


def test_build_routine_item_normalizes_and_converts_monitor():
    item = build_routine_item(
        name="  App ",
        item_type="app",
        target="  calc.exe ",
        args=" --flag ",
        monitor_value="Monitor 1: 1920x1080",
        position="full",
        delay=1,
        icon="  ",
    )
    assert item["name"] == "App"
    assert item["target"] == "calc.exe"
    assert item["monitor"] == 1
    assert item["args"] == "--flag"


def test_apply_form_state_to_config_updates_data():
    cfg = DummyConfig()
    state = SettingsFormState(
        threshold=0.3,
        min_interval=0.4,
        audio_enabled=True,
        audio_mode="file",
        audio_file_path="C:/x.wav",
        startup_phrase="Ready",
        startup_delay=2.0,
        startup_enabled=True,
        active_routine="work_routine",
    )
    apply_form_state_to_config(cfg, state, startup_apply_result=(True, {"enabled": True}))
    assert cfg.data["clap_settings"]["threshold"] == 0.3
    assert cfg.data["audio_settings"]["mode"] == "file"
    assert cfg.data["system"]["startup_delay"] == 2.0
    assert cfg.data["system"]["run_on_startup"] is True
    assert cfg.data["system"]["active_routine"] == "work_routine"
