import pytest
from unittest.mock import MagicMock, patch
from src.launcher import Launcher

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.routines = {
        "test_routine": {
            "items": [
                {
                    "name": "TestApp",
                    "type": "app",
                    "target": "test.exe",
                    "monitor": "primary",
                    "position": "full",
                    "delay": 0
                }
            ]
        }
    }
    return config

@pytest.fixture
def mock_monitors():
    m1 = MagicMock()
    m1.x, m1.y, m1.width, m1.height = 0, 0, 1920, 1080
    return [m1]

def test_resolve_monitor_index(mock_config, mock_monitors):
    launcher = Launcher(mock_config, dry_run=True, monitors=mock_monitors)
    assert launcher._resolve_monitor_index("primary") == 0
    assert launcher._resolve_monitor_index(0) == 0
    assert launcher._resolve_monitor_index("secondary") == 0 # Only one monitor

    launcher.monitors.append(MagicMock())
    assert launcher._resolve_monitor_index("secondary") == 1

@patch("src.launcher.webbrowser.open")
@patch("src.launcher.Launcher.find_window_robustly")
@patch("src.launcher.Launcher.apply_position")
@patch("src.launcher.Launcher.is_app_running")
def test_launch_url(mock_running, mock_apply, mock_find, mock_web, mock_config, mock_monitors):
    mock_running.return_value = False
    mock_config.routines["test_routine"]["items"][0] = {
        "name": "Google",
        "type": "url",
        "target": "https://google.com",
        "monitor": 0,
        "position": "full"
    }
    mock_find.return_value = 12345 # Mock HWND

    launcher = Launcher(mock_config, dry_run=False, monitors=mock_monitors)
    # Patch time.sleep to speed up tests
    with patch("time.sleep"):
        launcher.launch_routine("test_routine")

    mock_web.assert_called_once_with("https://google.com")
    mock_apply.assert_called_once_with(12345, 0, "full")

@patch("subprocess.Popen")
@patch("src.launcher.Launcher.find_window_robustly")
@patch("src.launcher.Launcher.apply_position")
@patch("src.launcher.Launcher.is_app_running")
def test_launch_app(mock_running, mock_apply, mock_find, mock_popen, mock_config, mock_monitors):
    mock_running.return_value = False
    mock_find.return_value = 12345 # Mock HWND

    launcher = Launcher(mock_config, dry_run=False, monitors=mock_monitors)
    with patch("time.sleep"):
        launcher.launch_routine("test_routine")

    mock_popen.assert_called_once()
    mock_apply.assert_called_once_with(12345, 0, "full")

def test_dry_run_no_launch(mock_config, mock_monitors):
    launcher = Launcher(mock_config, dry_run=True, monitors=mock_monitors)

    with patch("subprocess.Popen") as mock_popen:
        with patch("src.launcher.webbrowser.open") as mock_web:
             launcher.launch_routine("test_routine")
             mock_popen.assert_not_called()
             mock_web.assert_not_called()
