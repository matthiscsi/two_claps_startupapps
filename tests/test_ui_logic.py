import pytest

from src.ui_logic import (
    UIValidationError,
    apply_form_state_to_config,
    build_routine_item,
    choose_routine_selection,
    describe_monitor_placement,
    is_routine_item_enabled,
    monitor_layout_preview_rect,
    normalize_routine_timing,
    parse_monitor_value,
    summarize_routine_next_action,
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


def test_choose_routine_selection_prefers_current_then_configured():
    routines = ["morning", "work"]
    assert choose_routine_selection(routines, current_selection="work", configured_selection="morning") == "work"
    assert choose_routine_selection(routines, current_selection="missing", configured_selection="morning") == "morning"
    assert choose_routine_selection(routines, current_selection="missing", configured_selection="also_missing") == "morning"
    assert choose_routine_selection([], current_selection="work", configured_selection="morning") == ""


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
    assert item["enabled"] is True


def test_build_routine_item_preserves_advanced_fields():
    item = build_routine_item(
        name="App",
        enabled=False,
        item_type="app",
        target="calc.exe",
        args="",
        monitor_value="primary",
        position="left",
        delay=0,
        icon="",
        window_title_match="Calculator",
        window_wait_timeout=0.2,
        window_poll_interval=0.01,
    )
    assert item["enabled"] is False
    assert item["window_title_match"] == "Calculator"
    assert item["window_wait_timeout"] == 1.0
    assert item["window_poll_interval"] == 0.1


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


def test_describe_monitor_placement_includes_taskbar_safe_hint():
    summary = describe_monitor_placement("Monitor 1: 2560x1440 @ 1920,0", "left")
    assert "Monitor 1" in summary
    assert "taskbar-safe" in summary
    assert "1280x1440" in summary


def test_monitor_layout_preview_rect_shapes():
    assert monitor_layout_preview_rect("full") == (0.0, 0.0, 1.0, 1.0)
    assert monitor_layout_preview_rect("left") == (0.0, 0.0, 0.5, 1.0)
    assert monitor_layout_preview_rect("bottom") == (0.0, 0.5, 1.0, 0.5)


def test_enabled_items_and_next_action_summary():
    items = [
        {"name": "Muted", "enabled": False},
        {"name": "Browser", "enabled": True},
        {"name": "Music"},
    ]
    assert is_routine_item_enabled(items[0]) is False
    assert is_routine_item_enabled(items[2]) is True
    assert summarize_routine_next_action(items) == "Next trigger launches Browser + 1 more."
    assert "No enabled" in summarize_routine_next_action([{"name": "Muted", "enabled": False}])


def test_normalize_routine_timing_validates_ranges():
    assert normalize_routine_timing("0.5", "2", "0.2") == (0.5, 2.0, 0.2)
    with pytest.raises(UIValidationError, match="Delay"):
        normalize_routine_timing("-1", "2", "0.2")
    with pytest.raises(UIValidationError, match="wait timeout"):
        normalize_routine_timing("0", "0.5", "0.2")
    with pytest.raises(UIValidationError, match="poll interval"):
        normalize_routine_timing("0", "2", "0.01")
