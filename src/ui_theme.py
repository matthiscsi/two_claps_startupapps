from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def apply_theme(style: ttk.Style) -> None:
    style.configure("HeroTitle.TLabel", font=("Segoe UI Semibold", 14))
    style.configure("Header.TLabel", font=("Segoe UI", 10))
    style.configure("SectionTitle.TLabel", font=("Segoe UI Semibold", 10))
    style.configure("Hint.TLabel", foreground="#5E6A71", font=("Segoe UI", 8))
    style.configure("Status.TLabel", foreground="#5E6A71", font=("Segoe UI", 9))
    style.configure("Metric.TLabel", foreground="#17202A", font=("Segoe UI Semibold", 10))
    style.configure("Card.TFrame", relief="solid", borderwidth=1)
    style.configure("Primary.TButton", padding=(12, 6))
    style.configure("Secondary.TButton", padding=(10, 6))
    style.configure("Routine.Treeview", rowheight=34)
    style.configure("Routine.Treeview.Heading", font=("Segoe UI Semibold", 9))


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            justify="left",
            bg="#ffffe0",
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=4,
            font=("Segoe UI", 8),
        )
        label.pack()

    def _hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


def add_tooltip(widget, text):
    return Tooltip(widget, text)
