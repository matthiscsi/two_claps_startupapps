import logging
import threading
from unittest.mock import MagicMock, patch

from src.main import JarvisApp


class ImmediateThread:
    def __init__(self, target, daemon=None):
        self.target = target
        self.daemon = daemon

    def start(self):
        self.target()


def test_on_trigger_item_launches_single_item():
    app = JarvisApp.__new__(JarvisApp)
    app.logger = logging.getLogger("test")
    app.routine_lock = threading.Lock()
    app.launcher = MagicMock()
    app._record_launch_result = MagicMock()

    item = {"name": "Only", "type": "app", "target": "calc.exe"}
    with patch("threading.Thread", ImmediateThread):
        app.on_trigger_item(item, source="test")

    app.launcher.launch_item.assert_called_once_with(item)
    app._record_launch_result.assert_called_once()
