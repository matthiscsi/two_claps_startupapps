import pytest
import os
import sys
from src.config import get_resource_path

def test_get_resource_path_dev():
    # In dev mode (not frozen), it should return absolute path from current dir
    rel_path = "config.yaml"
    abs_path = get_resource_path(rel_path)
    assert os.path.isabs(abs_path)
    assert abs_path.endswith(rel_path)

def test_get_resource_path_frozen():
    # Simulate PyInstaller frozen state
    sys.frozen = True
    sys._MEIPASS = "/tmp/_MEI12345"
    try:
        rel_path = "config.yaml"
        abs_path = get_resource_path(rel_path)
        assert abs_path == os.path.join(sys._MEIPASS, rel_path)
    finally:
        del sys.frozen
        del sys._MEIPASS
