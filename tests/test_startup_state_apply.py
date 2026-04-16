from unittest.mock import patch
from src.startup_helper import apply_startup_state


def test_apply_startup_state_success():
    with patch("src.startup_helper.set_startup", return_value=True), \
         patch("src.startup_helper.get_startup_state", return_value={"enabled": True, "command": "x"}):
        ok, state = apply_startup_state(True)
        assert ok is True
        assert state["enabled"] is True


def test_apply_startup_state_detects_verification_failure():
    with patch("src.startup_helper.set_startup", return_value=True), \
         patch("src.startup_helper.get_startup_state", return_value={"enabled": False, "command": None}):
        ok, state = apply_startup_state(True)
        assert ok is False
        assert state["enabled"] is False
