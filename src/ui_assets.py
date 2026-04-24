from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from src.config import get_resource_path


class IconRegistry:
    """Small PNG icon loader with graceful text fallback for PyInstaller builds."""

    def __init__(self, root: tk.Misc):
        self.root = root
        self._cache: dict[str, tk.PhotoImage] = {}

    def get(self, name: str) -> tk.PhotoImage | None:
        if name in self._cache:
            return self._cache[name]

        path = get_resource_path(os.path.join("assets", "ui", f"{name}.png"))
        if not os.path.exists(path):
            return None
        try:
            image = tk.PhotoImage(master=self.root, file=path)
        except tk.TclError:
            return None
        self._cache[name] = image
        return image

    def button(self, parent, *, icon: str, text: str, command, style: str = "Secondary.TButton", **kwargs):
        image = self.get(icon)
        if image:
            return ttk.Button(parent, text=text, image=image, compound="left", style=style, command=command, **kwargs)
        return ttk.Button(parent, text=text, style=style, command=command, **kwargs)
