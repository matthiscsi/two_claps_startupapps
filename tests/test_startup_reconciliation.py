import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from src.main import JarvisApp
from src.config import Config

@pytest.fixture
def mock_args():
    args = MagicMock()
    args.config = "test_config.yaml"
    args.routine = "morning_routine"
    args.dry_run = False
    args.no_audio = True
    args.calibrate = False
    args.no_tray = True
    args.minimized = True
    return args

@pytest.fixture
def clean_config():
    if os.path.exists("test_config.yaml"):
        os.remove("test_config.yaml")
    yield
    if os.path.exists("test_config.yaml"):
        os.remove("test_config.yaml")

def test_startup_migration_missing_key_enabled_registry(mock_args, clean_config):
    """
    Given: config missing system.run_on_startup
    And: registry startup entry exists
    When: app initializes
    Then: registry entry is NOT removed and config is updated to True
    """
    with patch("src.main.sys.platform", "win32"), \
         patch("src.main.get_startup_state", return_value={"enabled": True, "command": "some_cmd"}), \
         patch("src.main.get_startup_command", return_value="some_cmd"), \
         patch("src.main.apply_startup_state") as mock_set_startup:

        # Create a config that is missing the system key or has run_on_startup: null
        with open("test_config.yaml", "w") as f:
            f.write("system: {}\n") # Missing run_on_startup

        app = JarvisApp(mock_args)

        # Verify it inferred True from registry
        assert app.config.data["system"]["run_on_startup"] is True
        # Verify it didn't call set_startup(False)
        # It might call set_startup(True) if command mismatch, but here it shouldn't
        mock_set_startup.assert_not_called()

def test_startup_migration_missing_key_disabled_registry(mock_args, clean_config):
    """
    Given: config missing system.run_on_startup
    And: registry startup entry does NOT exist
    When: app initializes
    Then: registry remains disabled and config is updated to False
    """
    with patch("src.main.sys.platform", "win32"), \
         patch("src.main.get_startup_state", return_value={"enabled": False, "command": None}), \
         patch("src.main.get_startup_command", return_value="some_cmd"), \
         patch("src.main.apply_startup_state") as mock_set_startup:

        with open("test_config.yaml", "w") as f:
            f.write("system: {}\n")

        app = JarvisApp(mock_args)

        # Verify it inferred False from registry
        assert app.config.data["system"]["run_on_startup"] is False
        mock_set_startup.assert_not_called()

def test_startup_explicit_override_true(mock_args, clean_config):
    """
    Given: config system.run_on_startup is True
    And: registry startup entry does NOT exist
    When: app initializes
    Then: registry entry is created
    """
    with patch("src.main.sys.platform", "win32"), \
         patch("src.main.get_startup_state", return_value={"enabled": False, "command": None}), \
         patch("src.main.get_startup_command", return_value="expected_cmd"), \
         patch("src.main.apply_startup_state") as mock_set_startup:

        with open("test_config.yaml", "w") as f:
            f.write("system:\n  run_on_startup: true\n")

        app = JarvisApp(mock_args)

        assert app.config.data["system"]["run_on_startup"] is True
        mock_set_startup.assert_called_once_with(True)

def test_startup_explicit_override_false(mock_args, clean_config):
    """
    Given: config system.run_on_startup is False
    And: registry startup entry exists
    When: app initializes
    Then: registry entry is removed
    """
    with patch("src.main.sys.platform", "win32"), \
         patch("src.main.get_startup_state", return_value={"enabled": True, "command": "some_cmd"}), \
         patch("src.main.get_startup_command", return_value="some_cmd"), \
         patch("src.main.apply_startup_state") as mock_set_startup:

        with open("test_config.yaml", "w") as f:
            f.write("system:\n  run_on_startup: false\n")

        app = JarvisApp(mock_args)

        assert app.config.data["system"]["run_on_startup"] is False
        mock_set_startup.assert_called_once_with(False)
