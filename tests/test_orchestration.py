import pytest
from unittest.mock import MagicMock, patch
from src.config import Config
from src.launcher import Launcher

@pytest.fixture
def mock_config():
    config = MagicMock(spec=Config)
    config.routines = {
        "test_routine": [
            {"name": "App1", "type": "app", "path": "path1", "monitor": 0, "delay": 0},
            {"name": "URL1", "type": "url", "path": "http://test.com", "monitor": 1, "delay": 0}
        ]
    }
    return config

def test_launcher_dry_run(mock_config):
    with patch('src.launcher.get_monitors') as mock_monitors:
        mock_monitors.return_value = [MagicMock(), MagicMock()]
        launcher = Launcher(mock_config, dry_run=True)

        # This should not raise any errors and just log
        launcher.launch_routine("test_routine")

def test_launcher_invalid_routine(mock_config):
    with patch('src.launcher.get_monitors') as mock_monitors:
        mock_monitors.return_value = [MagicMock()]
        launcher = Launcher(mock_config, dry_run=True)
        launcher.launch_routine("non_existent")
        # Should log error and return gracefully
