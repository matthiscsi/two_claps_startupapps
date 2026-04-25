from __future__ import annotations

from src.ui_animation import preview_accent
from src.ui_logic import monitor_layout_preview_rect


def draw_layout_preview(canvas, position, *, phase: int = 0) -> None:
    canvas.delete("all")
    monitor_x, monitor_y, monitor_w, monitor_h = 15, 10, 190, 105
    taskbar_h = 14
    canvas.create_rectangle(monitor_x, monitor_y, monitor_x + monitor_w, monitor_y + monitor_h, fill="#1f2937", outline="#94a3b8")
    canvas.create_rectangle(
        monitor_x + 2,
        monitor_y + monitor_h - taskbar_h,
        monitor_x + monitor_w - 2,
        monitor_y + monitor_h - 2,
        fill="#374151",
        outline="",
    )
    work_x = monitor_x + 2
    work_y = monitor_y + 2
    work_w = monitor_w - 4
    work_h = monitor_h - taskbar_h - 4
    px, py, pw, ph = monitor_layout_preview_rect(position)
    accent = preview_accent(phase)
    canvas.create_rectangle(
        work_x + int(work_w * px),
        work_y + int(work_h * py),
        work_x + int(work_w * (px + pw)),
        work_y + int(work_h * (py + ph)),
        fill=accent,
        outline="#bfdbfe",
        width=2,
    )
    canvas.create_text(monitor_x + 6, monitor_y + 8, text="Taskbar-safe area", anchor="w", fill="#e5e7eb", font=("", 8))
    canvas.create_text(monitor_x + 6, monitor_y + monitor_h - 7, text="Taskbar", anchor="w", fill="#d1d5db", font=("", 7))
