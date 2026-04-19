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
        launcher.launch_routine("test")
        popen.assert_not_called()


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
        launcher.launch_routine("test")
        startfile.assert_not_called()
