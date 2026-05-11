from unittest.mock import MagicMock
import numpy as np
from src.detector import ClapDetector


def _make_detector():
    cfg = MagicMock()
    cfg.clap_settings = {
        "sampling_rate": 44100,
        "frame_duration": 0.02,
        "threshold": 0.15,
        "min_interval": 0.2,
        "max_interval": 2.0,
        "order": 2,
        "filter_low": 1400,
        "filter_high": 1800,
    }
    return ClapDetector(cfg)


def test_transient_clap_is_accepted():
    det = _make_detector()
    frame = np.zeros(det.frame_size, dtype=np.float32)
    frame[10] = 0.7
    ok, _ = det._is_transient_clap(frame)
    assert ok is True


def test_damped_clap_like_transient_is_accepted():
    det = _make_detector()
    t = np.arange(det.frame_size, dtype=np.float32)
    frame = np.sin(2 * np.pi * 1600 * t / det.sampling_rate) * np.exp(-t / 250.0) * 0.7
    ok, reason = det._is_transient_clap(frame.astype(np.float32))
    assert ok is True, reason


def test_sustained_signal_is_rejected():
    det = _make_detector()
    frame = np.ones(det.frame_size, dtype=np.float32) * 0.2
    ok, reason = det._is_transient_clap(frame)
    assert ok is False
    assert "crest_factor" in reason or "too_long" in reason
