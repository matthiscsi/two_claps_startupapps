import yaml

from src.config_backup import create_config_backup, list_config_backups, load_config_backup, restore_config_backup
from src.config import DEFAULT_CONFIG


def _write_config(path, threshold=0.15):
    data = yaml.safe_load(yaml.safe_dump(DEFAULT_CONFIG))
    data["clap_settings"]["threshold"] = threshold
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return data


def test_create_config_backup_and_prune(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_config(config_path)
    backup_dir = tmp_path / "custom-backups"

    first = create_config_backup(str(config_path), backup_dir=str(backup_dir), keep=2, reason="first")
    second = create_config_backup(str(config_path), backup_dir=str(backup_dir), keep=2, reason="second")
    third = create_config_backup(str(config_path), backup_dir=str(backup_dir), keep=2, reason="third")

    assert first
    assert second
    assert third
    backups = list_config_backups(str(config_path), backup_dir=str(backup_dir))
    assert len(backups) == 2
    assert backups[0]["name"].startswith("config-")


def test_restore_config_backup_validates_and_replaces_config(tmp_path):
    config_path = tmp_path / "config.yaml"
    backup_source = tmp_path / "backup.yaml"
    _write_config(config_path, threshold=0.2)
    expected = _write_config(backup_source, threshold=0.4)

    restored = restore_config_backup(str(config_path), str(backup_source))

    assert restored["clap_settings"]["threshold"] == 0.4
    assert load_config_backup(str(config_path))["clap_settings"]["threshold"] == expected["clap_settings"]["threshold"]
    assert list_config_backups(str(config_path))
