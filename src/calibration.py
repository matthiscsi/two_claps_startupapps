from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass
class CalibrationRecommendation:
    threshold: float
    min_interval: float
    ambient_peak: float
    clap_peak: float
    confidence: str
    summary: str


def recommend_clap_settings(ambient_peaks, clap_peaks, clap_intervals, current_threshold, current_min_interval):
    ambient = [float(v) for v in ambient_peaks if v is not None]
    claps = [float(v) for v in clap_peaks if v is not None and v > 0.0]
    intervals = [float(v) for v in clap_intervals if v is not None and v > 0.0]

    ambient_peak = max(ambient) if ambient else 0.01
    clap_peak = max(claps) if claps else max(current_threshold, ambient_peak * 2.0)

    # Place threshold between ambient and clap peaks with extra safety margin.
    raw_threshold = ambient_peak + ((clap_peak - ambient_peak) * 0.45)
    threshold = _clamp(raw_threshold, 0.05, 0.85)

    if intervals:
        interval_median = median(intervals)
        min_interval = _clamp(interval_median * 0.55, 0.15, 0.75)
    else:
        min_interval = _clamp(float(current_min_interval), 0.15, 0.75)

    confidence = "high" if len(claps) >= 4 else "medium" if len(claps) >= 2 else "low"
    summary = _build_summary(ambient_peak, clap_peak, threshold, min_interval, confidence)

    return CalibrationRecommendation(
        threshold=round(threshold, 3),
        min_interval=round(min_interval, 3),
        ambient_peak=round(ambient_peak, 3),
        clap_peak=round(clap_peak, 3),
        confidence=confidence,
        summary=summary,
    )


def _clamp(value, low, high):
    return max(low, min(high, float(value)))


def _build_summary(ambient_peak, clap_peak, threshold, min_interval, confidence):
    return (
        f"Ambient peak {ambient_peak:.3f}, clap peak {clap_peak:.3f}. "
        f"Recommended threshold {threshold:.3f} and cooldown {min_interval:.3f}s "
        f"(confidence: {confidence})."
    )
