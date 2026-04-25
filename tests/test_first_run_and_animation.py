from src.first_run import config_has_usable_routine, ensure_first_run_metadata, mark_first_run_completed, should_show_first_run
from src.ui_animation import next_animation_step, preview_accent, pulse_color


def test_first_run_detection_and_metadata():
    data = {"routines": {"morning": {"items": [{"name": "A"}]}}, "system": {}}
    ensure_first_run_metadata(data)

    assert should_show_first_run(data) is True
    assert config_has_usable_routine(data) is True

    mark_first_run_completed(data)
    assert data["system"]["first_run_completed"] is True
    assert should_show_first_run(data) is False


def test_first_run_shows_when_no_routine_items_even_after_completion():
    data = {"routines": {"empty": {"items": []}}, "system": {"first_run_completed": True}}
    assert should_show_first_run(data) is True


def test_animation_helpers_are_stable():
    assert next_animation_step(5, 6) == 0
    assert next_animation_step(5, 0) == 0
    assert pulse_color(0, active=True).startswith("#")
    assert pulse_color(0, active=False).startswith("#")
    assert preview_accent(12).startswith("#")
