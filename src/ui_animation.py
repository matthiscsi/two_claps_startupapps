from __future__ import annotations

PULSE_COLORS = ("#2e7d32", "#328a3a", "#389846", "#43a35a", "#389846", "#328a3a")
IDLE_COLORS = ("#5E6A71", "#65737b", "#6d7d85", "#65737b")
PREVIEW_ACCENTS = ("#2563eb", "#2f73ee", "#3b82f6", "#60a5fa", "#3b82f6", "#2f73ee")


def next_animation_step(step: int, modulo: int) -> int:
    if modulo <= 0:
        return 0
    return (int(step) + 1) % modulo


def pulse_color(step: int, *, active: bool) -> str:
    colors = PULSE_COLORS if active else IDLE_COLORS
    return colors[int(step) % len(colors)]


def preview_accent(step: int) -> str:
    return PREVIEW_ACCENTS[int(step) % len(PREVIEW_ACCENTS)]
