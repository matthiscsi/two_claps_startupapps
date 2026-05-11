from src.ui import SettingsUI


class _Var:
    def __init__(self, value=None):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class _Config:
    def __init__(self):
        self.routines = {"morning_routine": {"items": []}}
        self.clap_settings = {"threshold": 0.2, "min_interval": 0.3, "max_interval": 2.2}
        self.audio_settings = {
            "enabled": True,
            "mode": "tts",
            "file_path": "",
            "startup_phrase": "Hello",
        }
        self.system_settings = {"startup_delay": 1.0, "active_routine": "morning_routine"}


def test_reset_form_skips_until_routine_controls_ready(monkeypatch):
    monkeypatch.setattr("src.ui.get_startup_state", lambda: {"enabled": False, "command": None})
    ui = SettingsUI(_Config())

    ui.threshold_var = _Var()
    ui.min_interval_var = _Var()
    ui.max_interval_var = _Var()
    ui.audio_enabled_var = _Var()
    ui.audio_mode_var = _Var()
    ui.audio_file_var = _Var()
    ui.startup_phrase_var = _Var()
    ui.startup_delay_var = _Var()
    ui.startup_var = _Var()
    ui._update_audio_visibility = lambda: None
    ui._sync_slider_labels = lambda: None

    # Regression guard: should not crash when routine controls are not built yet.
    ui._reset_form_from_config(mark_status=False)

    assert ui.threshold_var.get() == 0.2
    assert ui.min_interval_var.get() == 0.3
    assert ui.max_interval_var.get() == 2.2
