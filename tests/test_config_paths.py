import os

from src.config import Config, get_default_config_path


def test_default_config_path_uses_appdata(monkeypatch, tmp_path):
    appdata_root = tmp_path / "appdata"
    monkeypatch.setenv("APPDATA", str(appdata_root))
    expected = appdata_root / "JarvisLauncher" / "config.yaml"
    assert os.path.abspath(get_default_config_path()) == os.path.abspath(str(expected))


def test_default_path_migrates_legacy_local_config(monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    appdata_root = tmp_path / "appdata"
    monkeypatch.setenv("APPDATA", str(appdata_root))
    monkeypatch.chdir(project_dir)

    legacy = project_dir / "config.yaml"
    legacy.write_text("system:\n  active_routine: morning_routine\n", encoding="utf-8")

    cfg = Config("config.yaml")
    assert os.path.exists(cfg.config_path)
    assert os.path.abspath(cfg.config_path) == os.path.abspath(get_default_config_path())
