from src.ui_diagnostics import build_troubleshooting_summary, resolve_log_file_path, tail_text_file
from src.ui_models import AppRuntimeSnapshot, RuntimeStatus


def test_resolve_log_file_path_uses_log_dir_for_relative_file():
    data = {"logging": {"file": "launcher.log"}}
    assert resolve_log_file_path(data, log_dir="C:/logs").replace("\\", "/") == "C:/logs/launcher.log"


def test_tail_text_file_handles_missing_and_limits_lines(tmp_path):
    missing = tmp_path / "missing.log"
    assert "not found" in tail_text_file(str(missing))

    log = tmp_path / "launcher.log"
    log.write_text("\n".join(str(i) for i in range(10)), encoding="utf-8")
    assert tail_text_file(str(log), line_count=3) == "7\n8\n9"


def test_build_troubleshooting_summary_includes_runtime_and_paths():
    summary = build_troubleshooting_summary(
        snapshot=AppRuntimeSnapshot(listening_enabled=True, active_routine="morning", runtime_ready=False),
        status=RuntimeStatus(detector_available=True, detector_active=False, state="IDLE", clap_count=0, peak=0.12),
        threshold=0.2,
        min_interval=0.4,
        log_dir="C:/logs",
        config_path="config.yaml",
        startup_enabled=True,
    )
    assert "Active routine: morning" in summary
    assert "Startup enabled: True" in summary
    assert "Threshold: 0.200" in summary
