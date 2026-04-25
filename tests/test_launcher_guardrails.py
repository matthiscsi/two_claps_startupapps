from unittest.mock import MagicMock, patch

from src.launcher import Launcher


def _config_with_item(item):
    config = MagicMock()
    config.routines = {"test": {"items": [item]}}
    return config


def _single_monitor():
    m = MagicMock()
    m.x, m.y, m.width, m.height = 0, 0, 1920, 1080
    return [m]


def test_app_with_missing_absolute_path_is_skipped():
    item = {
        "name": "Broken App",
        "type": "app",
        "target": "C:/definitely/missing/app.exe",
        "monitor": 0,
        "position": "full",
    }
    launcher = Launcher(_config_with_item(item), dry_run=False, monitors=_single_monitor())

    with patch("subprocess.Popen") as popen:
        results = launcher.launch_routine("test")
        popen.assert_not_called()
    assert results[0]["status"] == "failure"
    assert "invalid" in results[0]["message"].lower()


def test_shortcut_missing_path_is_skipped():
    item = {
        "name": "Broken Shortcut",
        "type": "shortcut",
        "target": "C:/definitely/missing/file.lnk",
        "monitor": 0,
        "position": "full",
    }
    launcher = Launcher(_config_with_item(item), dry_run=False, monitors=_single_monitor())

    with patch("os.startfile", create=True) as startfile:
        results = launcher.launch_routine("test")
        startfile.assert_not_called()
    assert results[0]["status"] == "failure"


def test_disabled_item_is_skipped():
    item = {
        "name": "Muted App",
        "enabled": False,
        "type": "app",
        "target": "calc.exe",
        "monitor": 0,
        "position": "full",
    }
    launcher = Launcher(_config_with_item(item), dry_run=False, monitors=_single_monitor())

    with patch("subprocess.Popen") as popen:
        results = launcher.launch_routine("test")
        popen.assert_not_called()
    assert results[0]["status"] == "skipped"
    assert "disabled" in results[0]["message"].lower()
