from src.calibration import recommend_clap_settings


def test_recommend_clap_settings_uses_ambient_and_clap_peaks():
    rec = recommend_clap_settings(
        ambient_peaks=[0.01, 0.02, 0.03],
        clap_peaks=[0.22, 0.30, 0.28, 0.25],
        clap_intervals=[0.4, 0.5, 0.45],
        current_threshold=0.15,
        current_min_interval=0.2,
        current_max_interval=2.0,
    )
    assert 0.05 <= rec.threshold <= 0.85
    assert rec.threshold > 0.03
    assert 0.15 <= rec.min_interval <= 0.75
    assert rec.max_interval > rec.min_interval
    assert rec.confidence in {"high", "medium", "low"}


def test_recommend_clap_settings_handles_sparse_data():
    rec = recommend_clap_settings(
        ambient_peaks=[],
        clap_peaks=[],
        clap_intervals=[],
        current_threshold=0.2,
        current_min_interval=0.25,
        current_max_interval=2.5,
    )
    assert rec.threshold >= 0.05
    assert rec.min_interval == 0.25
    assert rec.max_interval == 2.5
