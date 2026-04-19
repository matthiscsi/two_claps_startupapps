from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    """
    Vertical scroll container for settings pages.
    Keeps controls reachable on smaller windows and high DPI scaling.
    """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.v_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set)

        self.v_scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.content = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_content_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.window_id, width=event.width)

    def _on_mousewheel(self, event):
        # Windows reports deltas in 120 increments.
        delta = int(-1 * (event.delta / 120))
        if delta:
            self.canvas.yview_scroll(delta, "units")


def preferred_window_geometry(root):
    """Return sensible default geometry for high-DPI Windows desktops."""
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    width = min(max(int(screen_w * 0.52), 760), 1024)
    height = min(max(int(screen_h * 0.78), 680), 920)
    return f"{width}x{height}"
