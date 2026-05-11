from unittest.mock import MagicMock

from src.main import JarvisApp


def _make_app():
    app = JarvisApp.__new__(JarvisApp)
    app.args = MagicMock()
    app.args.routine = "morning_routine"
    app.config = MagicMock()
    app.config.routines = {"morning_routine": {}, "work_routine": {}}
    app.config.data = {"system": {"active_routine": "morning_routine"}}
    app.config.save = MagicMock()
    app.logger = MagicMock()
    app.tray_icon = None
    return app


def test_set_active_routine_persists_when_requested():
    app = _make_app()

    result = app.set_active_routine("work_routine", source="tray_switch", persist=True)

    assert result is True
    assert app.args.routine == "work_routine"
    assert app.config.data["system"]["active_routine"] == "work_routine"
    app.config.save.assert_called_once()


def test_set_active_routine_does_not_persist_by_default():
    app = _make_app()

    result = app.set_active_routine("work_routine", source="settings")

    assert result is True
    app.config.save.assert_not_called()

