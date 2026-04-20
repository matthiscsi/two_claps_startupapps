import logging
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from src.audio_lock import PYAUDIO_LOCK
from src.calibration import recommend_clap_settings
from src.config import get_resource_path
from src.logger import get_log_dir
from src.startup_helper import apply_startup_state, get_startup_state
from src.ui_layout import ScrollableFrame, preferred_window_geometry
from src.ui_theme import add_tooltip, apply_theme
from src.ui_logic import (
    UIValidationError,
    apply_form_state_to_config,
    build_routine_item,
    cloned_config_data,
    describe_detector_state,
    detect_duplicate_item_names,
    parse_monitor_value,
    pick_default_monitor_option,
    validate_full_config_data,
    validate_routine_item_inputs,
)
from src.ui_models import AppRuntimeSnapshot, RuntimeStatus, SettingsFormState
from src.ui_routines import RoutineStore

logger = logging.getLogger(__name__)

try:
    import pyaudio
except ImportError:
    pyaudio = None


class SettingsUI:
    _instance = None

    def __init__(
        self,
        config_manager,
        on_save_callback=None,
        detector=None,
        runtime_snapshot_provider=None,
        trigger_routine_callback=None,
        switch_routine_callback=None,
    ):
        self.config_manager = config_manager
        self.on_save_callback = on_save_callback
        self.detector = detector
        self.runtime_snapshot_provider = runtime_snapshot_provider
        self.trigger_routine_callback = trigger_routine_callback
        self.switch_routine_callback = switch_routine_callback
        self.root = None
        self.meter_canvas = None
        self.state_label = None
        self.runtime_status_label = None
        self.quick_state_label = None
        self.status_line = None
        self._monitoring = False
        self._dirty = False
        self._startup_state = {"enabled": False, "command": None}
        self.routine_store = RoutineStore(self.config_manager.routines, routine_name="morning_routine")
        self.empty_state_label = None

    def open(self):
        if SettingsUI._instance:
            try:
                SettingsUI._instance.after(0, lambda: SettingsUI._instance.deiconify())
                SettingsUI._instance.after(10, lambda: SettingsUI._instance.lift())
                SettingsUI._instance.after(20, lambda: SettingsUI._instance.focus_force())
            except Exception:
                SettingsUI._instance = None
            if SettingsUI._instance:
                return

        try:
            logger.info("UI_EVENT: opening_settings_window")
            self.root = tk.Tk()
            SettingsUI._instance = self.root
            self.root.title("Jarvis Launcher Settings")
            icon_path = get_resource_path(os.path.join("assets", "icon.ico"))
            if os.path.exists(icon_path):
                try:
                    self.root.iconbitmap(icon_path)
                except Exception:
                    pass

            self.root.geometry(preferred_window_geometry(self.root))
            self.root.minsize(700, 560)
            self.root.protocol("WM_DELETE_WINDOW", self._close_window)

            style = ttk.Style()
            apply_theme(style)

            self.root.grid_rowconfigure(1, weight=1)
            self.root.grid_columnconfigure(0, weight=1)

            header = ttk.Frame(self.root)
            header.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 0))
            header.grid_columnconfigure(0, weight=1)

            ttk.Label(
                header,
                text="Changes are active after Apply or Save. Save applies and closes.",
                foreground="#444",
            ).grid(row=0, column=0, sticky="w")
            self.quick_state_label = ttk.Label(header, text="", foreground="#555")
            self.quick_state_label.grid(row=0, column=1, sticky="e")

            self.notebook = ttk.Notebook(self.root)
            self.notebook.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)

            self._create_general_tab()
            self._create_routines_tab()
            self._create_advanced_tab()

            footer = ttk.Frame(self.root)
            footer.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
            footer.grid_columnconfigure(0, weight=1)

            self.status_line = ttk.Label(footer, text="Ready", foreground="#666")
            self.status_line.grid(row=0, column=0, sticky="w", padx=5)

            button_box = ttk.Frame(footer)
            button_box.grid(row=0, column=1, sticky="e")
            ttk.Button(
                button_box,
                text="Apply Changes",
                style="Secondary.TButton",
                command=lambda: self._save_settings(close_window=False),
            ).pack(
                side="right", padx=5
            )
            ttk.Button(
                button_box,
                text="Save Settings",
                style="Primary.TButton",
                command=lambda: self._save_settings(close_window=True),
            ).pack(
                side="right", padx=5
            )
            ttk.Button(button_box, text="Reset", style="Secondary.TButton", command=self._reset_form_from_config).pack(side="right", padx=5)
            ttk.Button(button_box, text="Cancel", style="Secondary.TButton", command=self._close_window).pack(side="right", padx=5)

            self._mark_clean("Ready")
            self.root.after(500, self._update_runtime_header)
            self.root.mainloop()
        except Exception as e:
            logger.error("Failed to open Settings UI: %s", e, exc_info=True)
            SettingsUI._instance = None
            if self.root:
                try:
                    self.root.destroy()
                except Exception:
                    pass

    def _create_general_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="General")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        scroller = ScrollableFrame(tab)
        scroller.grid(row=0, column=0, sticky="nsew")
        content = scroller.content

        clap_frame = ttk.LabelFrame(content, text="Clap Detection")
        clap_frame.pack(fill="x", padx=10, pady=8)
        clap_frame.columnconfigure(1, weight=1)

        self.threshold_var = tk.DoubleVar()
        self.min_interval_var = tk.DoubleVar()
        self.threshold_display_var = tk.StringVar(value="0.15")
        self.min_interval_display_var = tk.StringVar(value="0.20 s")

        ttk.Label(clap_frame, text="How easy should a clap trigger?", style="SectionTitle.TLabel").grid(
            row=0, column=0, padx=8, pady=(8, 2), sticky="w"
        )
        threshold_row = ttk.Frame(clap_frame)
        threshold_row.grid(row=0, column=1, padx=8, pady=(8, 2), sticky="ew")
        threshold_row.columnconfigure(0, weight=1)
        self.threshold_scale = ttk.Scale(
            threshold_row,
            orient="horizontal",
            from_=0.05,
            to=0.85,
            variable=self.threshold_var,
            command=lambda _v: self._sync_slider_labels(),
        )
        self.threshold_scale.grid(row=0, column=0, sticky="ew")
        ttk.Label(threshold_row, textvariable=self.threshold_display_var, width=8).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(
            clap_frame,
            text="Lower = more sensitive. Higher = fewer accidental triggers from typing/desk noise.",
            style="Hint.TLabel",
        ).grid(row=1, column=1, padx=8, sticky="w")

        ttk.Label(clap_frame, text="Cooldown after one clap", style="SectionTitle.TLabel").grid(
            row=2, column=0, padx=8, pady=(10, 2), sticky="w"
        )
        cooldown_row = ttk.Frame(clap_frame)
        cooldown_row.grid(row=2, column=1, padx=8, pady=(10, 2), sticky="ew")
        cooldown_row.columnconfigure(0, weight=1)
        self.min_interval_scale = ttk.Scale(
            cooldown_row,
            orient="horizontal",
            from_=0.10,
            to=1.20,
            variable=self.min_interval_var,
            command=lambda _v: self._sync_slider_labels(),
        )
        self.min_interval_scale.grid(row=0, column=0, sticky="ew")
        ttk.Label(cooldown_row, textvariable=self.min_interval_display_var, width=8).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(
            clap_frame,
            text="Longer cooldown prevents one clap echo from being counted twice.",
            style="Hint.TLabel",
        ).grid(row=3, column=1, padx=8, sticky="w")

        button_row = ttk.Frame(clap_frame)
        button_row.grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=(10, 2))
        calibrate_btn = ttk.Button(button_row, text="Calibrate Microphone...", style="Primary.TButton", command=self._open_guided_calibration)
        calibrate_btn.pack(
            side="left", padx=(0, 8)
        )
        ttk.Label(
            button_row,
            text="Measures room noise and your clap strength, then recommends settings.",
            style="Hint.TLabel",
        ).pack(side="left")
        add_tooltip(calibrate_btn, "Guided calibration takes about 10 seconds and is recommended on first run.")

        device_text = self._get_microphone_label()
        device_color = "red" if "not detected" in device_text.lower() else "#444"
        ttk.Label(clap_frame, text=device_text, foreground=device_color, font=("", 8, "italic")).grid(
            row=5, column=0, columnspan=2, padx=8, pady=4, sticky="w"
        )

        meter_frame = ttk.Frame(clap_frame)
        meter_frame.grid(row=6, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        meter_frame.columnconfigure(1, weight=1)
        ttk.Label(meter_frame, text="Mic Input:", style="SectionTitle.TLabel").grid(row=0, column=0, padx=5, sticky="w")
        self.meter_canvas = tk.Canvas(meter_frame, height=22, bg="#1E1E1E", highlightthickness=0)
        self.meter_canvas.grid(row=0, column=1, padx=5, sticky="ew")
        self.state_label = ttk.Label(meter_frame, text="IDLE", width=16)
        self.state_label.grid(row=0, column=2, padx=5)

        self.runtime_status_label = ttk.Label(clap_frame, text="Runtime status: initializing...", style="Status.TLabel")
        self.runtime_status_label.grid(row=7, column=0, columnspan=2, padx=5, pady=(0, 6), sticky="w")

        if self.detector:
            self._monitoring = True
            self.root.after(100, self._update_meter)

        audio_frame = ttk.LabelFrame(content, text="Voice & Sound Feedback")
        audio_frame.pack(fill="x", padx=10, pady=8)

        self.audio_enabled_var = tk.BooleanVar()
        self.audio_mode_var = tk.StringVar()
        self.audio_file_var = tk.StringVar()
        self.startup_phrase_var = tk.StringVar()

        ttk.Checkbutton(audio_frame, text="Enable voice/sound feedback", variable=self.audio_enabled_var).pack(
            anchor="w", padx=5, pady=5
        )

        mode_frame = ttk.Frame(audio_frame)
        mode_frame.pack(fill="x", padx=5, pady=5)
        ttk.Label(mode_frame, text="Feedback Type:").pack(side="left", padx=5)
        ttk.Radiobutton(mode_frame, text="Spoken text (TTS)", variable=self.audio_mode_var, value="tts").pack(side="left", padx=5)
        ttk.Radiobutton(mode_frame, text="Play audio file", variable=self.audio_mode_var, value="file").pack(
            side="left", padx=5
        )

        self.file_frame = ttk.Frame(audio_frame)
        self.file_frame.pack(fill="x", padx=5, pady=5)
        ttk.Label(self.file_frame, text="File:").pack(side="left", padx=5)
        self.audio_file_entry = ttk.Entry(self.file_frame, textvariable=self.audio_file_var)
        self.audio_file_entry.pack(side="left", expand=True, fill="x", padx=5)
        self.audio_browse_btn = ttk.Button(self.file_frame, text="...", width=3, command=self._browse_audio_file)
        self.audio_browse_btn.pack(side="left", padx=2)
        self.audio_test_btn = ttk.Button(self.file_frame, text="Test Audio", style="Secondary.TButton", command=self._test_audio)
        self.audio_test_btn.pack(side="left", padx=2)
        add_tooltip(self.audio_test_btn, "Plays your current feedback mode without saving settings.")

        self.phrase_frame = ttk.Frame(audio_frame)
        self.phrase_frame.pack(fill="x", padx=5, pady=5)
        ttk.Label(self.phrase_frame, text="Spoken Phrase:").pack(anchor="w", padx=5)
        ttk.Entry(self.phrase_frame, textvariable=self.startup_phrase_var).pack(fill="x", padx=5, pady=5)

        self.audio_mode_var.trace_add("write", lambda *_: self._update_audio_visibility())
        self.audio_enabled_var.trace_add("write", lambda *_: self._update_audio_visibility())

        system_frame = ttk.LabelFrame(content, text="Startup & Quick Actions")
        system_frame.pack(fill="x", padx=10, pady=8)

        self.startup_var = tk.BooleanVar(value=False)
        if sys.platform == "win32":
            self._startup_state = get_startup_state()
            self.startup_var.set(self._startup_state["enabled"])
            self.startup_var.trace_add("write", lambda *_: self._mark_dirty("Startup preference changed"))
            startup_check = ttk.Checkbutton(system_frame, text="Launch Jarvis when Windows starts", variable=self.startup_var)
            startup_check.pack(
                anchor="w", padx=5, pady=5
            )
            add_tooltip(startup_check, "Registers Jarvis in your Windows user startup list.")

        self.startup_delay_var = tk.DoubleVar()
        ttk.Label(system_frame, text="Delay before listening starts (seconds):").pack(anchor="w", padx=5, pady=(5, 0))
        self.startup_delay_scale = ttk.Scale(
            system_frame,
            orient="horizontal",
            from_=0,
            to=30,
            variable=self.startup_delay_var,
            command=lambda _v: self._sync_slider_labels(),
        )
        self.startup_delay_scale.pack(fill="x", padx=5, pady=(0, 3))
        self.startup_delay_display_var = tk.StringVar(value="0.0 s")
        ttk.Label(system_frame, textvariable=self.startup_delay_display_var, style="Hint.TLabel").pack(anchor="w", padx=5, pady=(0, 5))

        quick_row = ttk.Frame(system_frame)
        quick_row.pack(fill="x", padx=5, pady=5)
        ttk.Button(quick_row, text="Open Logs Folder", style="Secondary.TButton", command=self._open_logs).pack(side="left")
        ttk.Button(quick_row, text="Run Active Routine Now", style="Secondary.TButton", command=self._test_active_routine).pack(side="left", padx=8)

        self._bind_dirty_tracking()
        self._reset_form_from_config(mark_status=False)

    def _create_routines_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Routines")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        scroller = ScrollableFrame(tab)
        scroller.grid(row=0, column=0, sticky="nsew")
        content = scroller.content

        top_row = ttk.Frame(content)
        top_row.pack(fill="x", padx=10, pady=(10, 4))
        top_row.columnconfigure(1, weight=1)

        ttk.Label(top_row, text="Active Routine:", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.selected_routine_var = tk.StringVar()
        self.routine_selector = ttk.Combobox(top_row, textvariable=self.selected_routine_var, state="readonly")
        self.routine_selector.grid(row=0, column=1, sticky="ew", padx=6)
        self.routine_selector.bind("<<ComboboxSelected>>", self._on_routine_changed)

        ttk.Button(top_row, text="New", style="Secondary.TButton", command=self._create_routine).grid(row=0, column=2, padx=2)
        ttk.Button(top_row, text="Clone", style="Secondary.TButton", command=self._clone_routine).grid(row=0, column=3, padx=2)
        ttk.Button(top_row, text="Delete", style="Secondary.TButton", command=self._delete_routine).grid(row=0, column=4, padx=2)

        helper = ttk.Label(
            content,
            text="Drag items by the handle (☰) to reorder launch sequence.",
            style="Hint.TLabel",
        )
        helper.pack(anchor="w", padx=10, pady=(2, 2))

        tree_frame = ttk.Frame(content)
        tree_frame.pack(expand=True, fill="both", padx=10, pady=5)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.routine_tree = ttk.Treeview(
            tree_frame,
            columns=("Handle", "Type", "Path", "Monitor", "Position", "Delay"),
            show="headings",
            style="Routine.Treeview",
        )
        self.routine_tree.tag_configure("dragging", background="#e1f5fe")
        self.routine_tree.heading("Handle", text="")
        self.routine_tree.column("Handle", width=40, anchor="center", stretch=False)
        self.routine_tree.heading("Type", text="Kind")
        self.routine_tree.column("Type", width=120)
        self.routine_tree.heading("Path", text="What to launch")
        self.routine_tree.column("Path", width=300)
        self.routine_tree.heading("Monitor", text="Monitor")
        self.routine_tree.column("Monitor", width=80)
        self.routine_tree.heading("Position", text="Layout")
        self.routine_tree.column("Position", width=80)
        self.routine_tree.heading("Delay", text="Delay (s)")
        self.routine_tree.column("Delay", width=80)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.routine_tree.yview)
        self.routine_tree.configure(yscrollcommand=scrollbar.set)
        self.routine_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.routine_tree.bind("<ButtonPress-1>", self._on_tree_click)
        self.routine_tree.bind("<B1-Motion>", self._on_tree_drag)
        self.routine_tree.bind("<ButtonRelease-1>", self._on_tree_release)
        self.routine_tree.bind("<Motion>", self._on_tree_motion)
        self.routine_tree.bind("<Leave>", lambda e: self.routine_tree.config(cursor=""))
        self._drag_data = {"item": None, "dragged": False}

        self.empty_state_label = ttk.Label(
            content,
            text="No items yet. Click “Add Item” to build your routine.",
            style="Hint.TLabel",
        )
        self.empty_state_label.pack(anchor="w", padx=12, pady=(0, 8))

        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill="x", padx=10, pady=(6, 15))
        ttk.Button(btn_frame, text="Add Item", style="Secondary.TButton", command=self._add_routine_item).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Edit Item", style="Secondary.TButton", command=self._edit_routine_item).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Duplicate Item", style="Secondary.TButton", command=self._duplicate_routine_item).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Remove Item", style="Secondary.TButton", command=self._remove_routine_item).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Run This Routine", style="Primary.TButton", command=self._trigger_selected_routine).pack(side="right", padx=5)

        self._refresh_routine_selector()
        self._refresh_routine_list()

    def _create_advanced_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Advanced")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        scroller = ScrollableFrame(tab)
        scroller.grid(row=0, column=0, sticky="nsew")
        content = scroller.content

        diag = ttk.LabelFrame(content, text="Diagnostics & Troubleshooting")
        diag.pack(fill="x", padx=10, pady=8)
        ttk.Label(
            diag,
            text="If clap detection fails, check microphone status in General and review logs.",
            style="Hint.TLabel",
        ).pack(anchor="w", padx=8, pady=(8, 4))
        row = ttk.Frame(diag)
        row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(row, text="Open Logs Folder", style="Secondary.TButton", command=self._open_logs).pack(side="left")
        ttk.Button(row, text="Run Active Routine", style="Secondary.TButton", command=self._test_active_routine).pack(
            side="left", padx=8
        )

        tray = ttk.LabelFrame(content, text="Tray Behavior")
        tray.pack(fill="x", padx=10, pady=8)
        ttk.Label(
            tray,
            text=(
                "Jarvis runs in the system tray.\n"
                "- Use tray menu to pause listening.\n"
                "- Switch active routine quickly.\n"
                "- Trigger routine manually."
            ),
            justify="left",
        ).pack(anchor="w", padx=8, pady=8)

        power = ttk.LabelFrame(content, text="Power User Notes")
        power.pack(fill="x", padx=10, pady=8)
        ttk.Label(
            power,
            text=(
                "Use full executable paths for best reliability.\n"
                "Use per-item delay and wait timeout for slow apps.\n"
                "Keep item names close to window titles for smoother positioning."
            ),
            justify="left",
            style="Hint.TLabel",
        ).pack(anchor="w", padx=8, pady=8)

    def _bind_dirty_tracking(self):
        tracked = [
            self.threshold_var,
            self.min_interval_var,
            self.audio_enabled_var,
            self.audio_mode_var,
            self.audio_file_var,
            self.startup_phrase_var,
            self.startup_delay_var,
            self.selected_routine_var,
        ]
        for variable in tracked:
            variable.trace_add("write", lambda *_: self._mark_dirty("Unsaved changes"))

    def _mark_dirty(self, status_text="Unsaved changes"):
        if not self._dirty:
            logger.info("UI_EVENT: state_dirty")
        self._dirty = True
        if self.status_line:
            self.status_line.config(text=status_text, foreground="#8a6d3b")

    def _mark_clean(self, status_text="Saved and applied"):
        self._dirty = False
        if self.status_line:
            self.status_line.config(text=status_text, foreground="#3c763d")

    def _set_status(self, text, level="info"):
        if not self.status_line:
            return
        color = {"info": "#5E6A71", "success": "#3c763d", "warn": "#8a6d3b", "error": "#a94442"}.get(level, "#5E6A71")
        self.status_line.config(text=text, foreground=color)

    def _sync_slider_labels(self):
        if hasattr(self, "threshold_display_var"):
            self.threshold_display_var.set(f"{float(self.threshold_var.get()):.3f}")
        if hasattr(self, "min_interval_display_var"):
            self.min_interval_display_var.set(f"{float(self.min_interval_var.get()):.2f} s")
        if hasattr(self, "startup_delay_display_var"):
            self.startup_delay_display_var.set(f"{float(self.startup_delay_var.get()):.1f} s")

    def _refresh_routine_selector(self):
        routines = sorted(self.config_manager.routines.keys())
        self.routine_selector["values"] = routines
        desired = self.config_manager.system_settings.get("active_routine", "morning_routine")
        if desired not in routines and routines:
            desired = routines[0]
        if desired:
            self.selected_routine_var.set(desired)
            self.routine_store.routine_name = desired

    def _on_routine_changed(self, _event=None):
        selected = self.selected_routine_var.get()
        if selected:
            self.routine_store.routine_name = selected
            self._refresh_routine_list()
            self._mark_dirty("Active routine changed")

    def _refresh_routine_list(self):
        selected_indices = [self.routine_tree.index(item_id) for item_id in self.routine_tree.selection()]
        for item in self.routine_tree.get_children():
            self.routine_tree.delete(item)

        items = self.routine_store.get_items()
        for idx, item in enumerate(items):
            item_type = str(item.get("type", "app")).lower()
            icon = {"app": "□", "url": "◌", "shortcut": "◇"}.get(item_type, "•")
            kind = f"{icon} {item_type.title()}"
            tag = f"{item.get('name')}||{idx}"
            row_id = self.routine_tree.insert(
                "",
                "end",
                values=(
                    "☰",
                    kind,
                    item.get("target"),
                    item.get("monitor"),
                    item.get("position"),
                    f"{float(item.get('delay', 0)):.1f}",
                ),
                tags=(tag,),
            )
            if idx in selected_indices:
                self.routine_tree.selection_add(row_id)
        if self.empty_state_label:
            if items:
                self.empty_state_label.pack_forget()
            else:
                self.empty_state_label.pack(anchor="w", padx=12, pady=(0, 8))

    def _create_routine(self):
        name = simpledialog.askstring("New Routine", "Enter routine name:", parent=self.root)
        if not name:
            return
        clean_name = name.strip()
        if not clean_name:
            messagebox.showerror("Error", "Routine name cannot be empty.")
            return
        if clean_name in self.config_manager.routines:
            messagebox.showerror("Error", f"Routine '{clean_name}' already exists.")
            return
        self.config_manager.routines[clean_name] = {"items": []}
        self.selected_routine_var.set(clean_name)
        self.routine_store.routine_name = clean_name
        self._refresh_routine_selector()
        self._refresh_routine_list()
        self._mark_dirty("Routine created (unsaved)")

    def _clone_routine(self):
        source = self.selected_routine_var.get()
        if not source:
            return
        clone_name = simpledialog.askstring("Clone Routine", f"Enter name for copy of '{source}':", parent=self.root)
        if not clone_name:
            return
        clone_name = clone_name.strip()
        if not clone_name:
            return
        if clone_name in self.config_manager.routines:
            messagebox.showerror("Error", f"Routine '{clone_name}' already exists.")
            return
        import copy

        self.config_manager.routines[clone_name] = copy.deepcopy(self.config_manager.routines[source])
        self.selected_routine_var.set(clone_name)
        self.routine_store.routine_name = clone_name
        self._refresh_routine_selector()
        self._refresh_routine_list()
        self._mark_dirty("Routine cloned (unsaved)")

    def _delete_routine(self):
        name = self.selected_routine_var.get()
        if not name:
            return
        if len(self.config_manager.routines) <= 1:
            messagebox.showwarning("Warning", "At least one routine must remain.")
            return
        if not messagebox.askyesno("Confirm", f"Delete routine '{name}'?"):
            return
        del self.config_manager.routines[name]
        self._refresh_routine_selector()
        self._refresh_routine_list()
        self._mark_dirty("Routine deleted (unsaved)")

    def _edit_routine_item(self):
        selected = self.routine_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an item to edit.")
            return
        item_id = selected[0]
        idx = self._index_from_tree_item(item_id)
        items = self.routine_store.get_items()
        if 0 <= idx < len(items):
            self._add_routine_item(edit_index=idx)

    def _duplicate_routine_item(self):
        selected = self.routine_tree.selection()
        if not selected:
            return
        idx = self._index_from_tree_item(selected[0])
        items = self.routine_store.get_items()
        if 0 <= idx < len(items):
            import copy

            new_item = copy.deepcopy(items[idx])
            new_item["name"] = f"{new_item.get('name', 'Item')} Copy"
            self.routine_store.upsert_item(new_item, None)
            self._refresh_routine_list()
            self._mark_dirty("Routine item duplicated (unsaved)")

    def _add_routine_item(self, edit_index=None):
        dialog = tk.Toplevel(self.root)
        is_edit = edit_index is not None
        dialog.title("Edit Routine Item" if is_edit else "Add Routine Item")
        dialog.geometry("560x520")
        dialog.minsize(520, 500)

        items = self.routine_store.get_items()
        old_item = items[edit_index] if is_edit else {}

        ttk.Label(
            dialog,
            text="Choose what to launch and where to place it.",
            style="Hint.TLabel",
        ).grid(row=0, column=0, columnspan=2, padx=8, pady=(8, 4), sticky="w")

        ttk.Label(dialog, text="Name:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        name_var = tk.StringVar(value=old_item.get("name", ""))
        name_entry = ttk.Entry(dialog, textvariable=name_var)
        name_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        add_tooltip(name_entry, "Friendly display name. Also used to match an existing window.")

        ttk.Label(dialog, text="Type:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        type_var = tk.StringVar(value=old_item.get("type", "app"))
        type_combo = ttk.Combobox(dialog, textvariable=type_var, values=["app", "url", "shortcut"], state="readonly")
        type_combo.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        add_tooltip(type_combo, "App = executable/command, URL = browser link, Shortcut = .lnk file.")

        ttk.Label(dialog, text="Target:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        target_frame = ttk.Frame(dialog)
        target_frame.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        target_var = tk.StringVar(value=old_item.get("target", ""))
        target_entry = ttk.Entry(target_frame, textvariable=target_var)
        target_entry.pack(side="left", expand=True, fill="x")
        add_tooltip(target_entry, "For apps, use full path for reliability. For URLs, include https://")
        browse_btn = ttk.Button(target_frame, text="...", width=3, command=lambda: self._browse_target(name_var, target_var))
        browse_btn.pack(side="right", padx=2)

        ttk.Label(
            dialog,
            text="Use full file path for best reliability. URLs should start with https://",
            foreground="#666",
            font=("", 8),
        ).grid(row=4, column=1, padx=5, sticky="w")

        def on_type_change(_event=None):
            if type_var.get() == "url":
                browse_btn.state(["disabled"])
            else:
                browse_btn.state(["!disabled"])

        type_combo.bind("<<ComboboxSelected>>", on_type_change)
        on_type_change()

        ttk.Label(dialog, text="Monitor:").grid(row=5, column=0, padx=5, pady=5, sticky="e")
        from src.launcher import Launcher

        monitor_options = Launcher.get_monitor_options()
        monitor_var = tk.StringVar(value=pick_default_monitor_option(monitor_options, old_item.get("monitor")))
        monitor_combo = ttk.Combobox(dialog, textvariable=monitor_var, values=monitor_options, state="readonly")
        monitor_combo.grid(row=5, column=1, padx=5, pady=5, sticky="ew")
        add_tooltip(monitor_combo, "Choose where the window should appear.")

        ttk.Label(dialog, text="Position:").grid(row=6, column=0, padx=5, pady=5, sticky="e")
        pos_var = tk.StringVar(value=old_item.get("position", "full"))
        ttk.Combobox(dialog, textvariable=pos_var, values=["full", "left", "right", "top", "bottom"], state="readonly").grid(
            row=6, column=1, padx=5, pady=5, sticky="ew"
        )

        ttk.Label(dialog, text="Delay before launch (s):").grid(row=7, column=0, padx=5, pady=5, sticky="e")
        delay_var = tk.DoubleVar(value=float(old_item.get("delay", 0.0)))
        ttk.Entry(dialog, textvariable=delay_var).grid(row=7, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(dialog, text="Window wait timeout (s):").grid(row=8, column=0, padx=5, pady=5, sticky="e")
        wait_var = tk.DoubleVar(value=float(old_item.get("window_wait_timeout", 15.0)))
        ttk.Entry(dialog, textvariable=wait_var).grid(row=8, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(dialog, text="Window poll interval (s):").grid(row=9, column=0, padx=5, pady=5, sticky="e")
        poll_var = tk.DoubleVar(value=float(old_item.get("window_poll_interval", 1.0)))
        ttk.Entry(dialog, textvariable=poll_var).grid(row=9, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(dialog, text="CLI Arguments (optional):").grid(row=10, column=0, padx=5, pady=5, sticky="e")
        args_var = tk.StringVar(value=old_item.get("args", ""))
        ttk.Entry(dialog, textvariable=args_var).grid(row=10, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(dialog, text="Icon Path (optional):").grid(row=11, column=0, padx=5, pady=5, sticky="e")
        icon_frame = ttk.Frame(dialog)
        icon_frame.grid(row=11, column=1, padx=5, pady=5, sticky="ew")
        icon_var = tk.StringVar(value=old_item.get("icon", ""))
        ttk.Entry(icon_frame, textvariable=icon_var).pack(side="left", expand=True, fill="x")
        ttk.Button(icon_frame, text="...", width=3, command=lambda: self._browse_icon(icon_var)).pack(side="right", padx=2)

        dialog.columnconfigure(1, weight=1)

        def save_item():
            try:
                warning_message = validate_routine_item_inputs(
                    name=name_var.get(), item_type=type_var.get(), target=target_var.get()
                )
            except UIValidationError as e:
                messagebox.showerror("Error", str(e))
                return
            if warning_message and not messagebox.askyesno("Warning", warning_message):
                return

            new_item = build_routine_item(
                name=name_var.get(),
                item_type=type_var.get(),
                target=target_var.get(),
                args=args_var.get(),
                monitor_value=monitor_var.get(),
                position=pos_var.get(),
                delay=delay_var.get(),
                icon=icon_var.get(),
                window_wait_timeout=wait_var.get(),
                window_poll_interval=poll_var.get(),
            )
            self.routine_store.upsert_item(new_item, edit_index if is_edit else None)
            self._refresh_routine_list()
            self._mark_dirty("Routine updated (unsaved)")
            logger.info(
                "UI_EVENT: routine_item_saved action=%s name=%s monitor=%s",
                "edit" if is_edit else "add",
                new_item["name"],
                parse_monitor_value(monitor_var.get()),
            )
            dialog.destroy()

        ttk.Button(dialog, text="Save Item" if is_edit else "Add Item", style="Primary.TButton", command=save_item).grid(row=12, columnspan=2, pady=12)

    def _remove_routine_item(self):
        selected = self.routine_tree.selection()
        if not selected:
            return
        indices = [self.routine_tree.index(item_id) for item_id in selected]
        self.routine_store.remove_by_indices(indices)
        self._refresh_routine_list()
        self._mark_dirty("Routine item removed (unsaved)")
        logger.info("UI_EVENT: routine_item_removed count=%s", len(indices))

    def _update_meter(self):
        if not self._monitoring or not self.root:
            return
        status = self._get_runtime_status()
        self._update_runtime_status_label(status)
        if not self.detector:
            self.state_label.config(text="NO DETECTOR", foreground="red")
            return
        try:
            if not status.detector_active:
                self.state_label.config(text="INACTIVE", foreground="gray")
                self.meter_canvas.delete("all")
                if self._monitoring:
                    self.root.after(500, self._update_meter)
                return

            peak = status.peak
            threshold = self.threshold_var.get()
            clap_count = status.clap_count
            state = status.state
            self.meter_canvas.delete("all")
            width = self.meter_canvas.winfo_width()
            level_width = min(width, int(peak * width))
            color = "#00ff00" if peak < threshold else "#ffff00"
            if peak > 0.8:
                color = "#ff0000"
            self.meter_canvas.create_rectangle(0, 0, level_width, 20, fill=color, outline="")
            thresh_x = int(threshold * width)
            self.meter_canvas.create_line(thresh_x, 0, thresh_x, 20, fill="white", width=2)

            human_state, state_color = describe_detector_state(
                detector_available=status.detector_available,
                detector_active=status.detector_active,
                state=state,
                clap_count=clap_count,
                peak=peak,
                threshold=threshold,
            )
            self.state_label.config(text=human_state, foreground=state_color)
        except Exception as e:
            logger.debug("Meter update failed: %s", e)

        if self._monitoring:
            self.root.after(50, self._update_meter)

    def _update_runtime_header(self):
        if not self.root or not self.root.winfo_exists():
            return
        snapshot = self._get_runtime_snapshot()
        text = f"Active routine: {snapshot.active_routine} | Listening: {'On' if snapshot.listening_enabled else 'Paused'}"
        self.quick_state_label.config(text=text)
        self.root.after(1000, self._update_runtime_header)

    def _on_tree_click(self, event):
        column = self.routine_tree.identify_column(event.x)
        item = self.routine_tree.identify_row(event.y)
        if item and column == "#1":
            self._drag_data["item"] = item
            self._drag_data["dragged"] = False
            self.routine_tree.item(item, tags=self.routine_tree.item(item, "tags") + ("dragging",))

    def _on_tree_drag(self, event):
        if not self._drag_data["item"]:
            return
        self._drag_data["dragged"] = True
        target = self.routine_tree.identify_row(event.y)
        if target and target != self._drag_data["item"]:
            self.routine_tree.move(self._drag_data["item"], "", self.routine_tree.index(target))

    def _on_tree_motion(self, event):
        self.routine_tree.config(cursor="fleur" if self.routine_tree.identify_column(event.x) == "#1" else "")

    def _on_tree_release(self, _event):
        item = self._drag_data.get("item")
        dragged = self._drag_data.get("dragged")
        if item:
            tags = list(self.routine_tree.item(item, "tags"))
            if "dragging" in tags:
                tags.remove("dragging")
            self.routine_tree.item(item, tags=tuple(tags))
        self._drag_data["item"] = None
        self._drag_data["dragged"] = False
        if not dragged:
            return

        previous_indices = []
        for item_id in self.routine_tree.get_children():
            tag = self._identifier_tag(item_id)
            if not tag:
                continue
            try:
                previous_indices.append(int(tag.rsplit("||", 1)[1]))
            except (ValueError, IndexError):
                logger.warning("Could not parse tag during reorder: %s", tag)
        if previous_indices or not self.routine_tree.get_children():
            self.routine_store.reorder_by_previous_indices(previous_indices)
            self._refresh_routine_list()
            self._mark_dirty("Routine order updated (unsaved)")
            logger.info("UI_EVENT: routine_reordered")

    def _save_settings(self, close_window):
        candidate = cloned_config_data(self.config_manager.data)
        try:
            startup_apply_result = None
            if sys.platform == "win32":
                requested = self.startup_var.get()
                logger.info("UI_EVENT: startup_toggle_requested enabled=%s", requested)
                startup_apply_result = apply_startup_state(requested)
                success, actual = startup_apply_result
                self.startup_var.set(actual["enabled"])
                if not success:
                    raise RuntimeError(f"Failed to set startup to {requested}. Actual state is {actual['enabled']}.")

            for routine_name, routine_data in self.config_manager.routines.items():
                duplicates = detect_duplicate_item_names(routine_data.get("items", []))
                if duplicates:
                    raise UIValidationError(
                        f"Routine '{routine_name}' has duplicate item names: {', '.join(duplicates)}."
                    )

            selected_routine = self.selected_routine_var.get() or "morning_routine"
            form_state = SettingsFormState(
                threshold=self.threshold_var.get(),
                min_interval=self.min_interval_var.get(),
                audio_enabled=self.audio_enabled_var.get(),
                audio_mode=self.audio_mode_var.get(),
                audio_file_path=self.audio_file_var.get(),
                startup_phrase=self.startup_phrase_var.get(),
                startup_delay=self.startup_delay_var.get(),
                startup_enabled=self.startup_var.get() if sys.platform == "win32" else None,
                active_routine=selected_routine,
            )

            apply_form_state_to_config(self.config_manager, form_state, startup_apply_result=startup_apply_result)
            validate_full_config_data(self.config_manager.data)
            self.config_manager.save()

            if self.switch_routine_callback:
                self.switch_routine_callback(selected_routine, source="settings")

            if self.on_save_callback:
                self.on_save_callback()

            logger.info(
                "UI_EVENT: settings_applied threshold=%.3f min_interval=%.3f startup_delay=%.2f audio_enabled=%s active_routine=%s",
                form_state.threshold,
                form_state.min_interval,
                form_state.startup_delay,
                form_state.audio_enabled,
                form_state.active_routine,
            )
            self._mark_clean("Saved and applied")
            if close_window:
                self._set_status("Settings saved.", level="success")
                self._close_window()
            else:
                self._set_status("Changes applied.", level="success")
        except Exception as e:
            self.config_manager.data = candidate
            logger.error("Failed to save settings: %s", e, exc_info=True)
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def _reset_form_from_config(self, mark_status=True):
        if sys.platform == "win32":
            self._startup_state = get_startup_state()

        state = SettingsFormState.from_config(
            self.config_manager,
            startup_enabled=self._startup_state["enabled"] if sys.platform == "win32" else None,
        )
        self.threshold_var.set(state.threshold)
        self.min_interval_var.set(state.min_interval)
        self.audio_enabled_var.set(state.audio_enabled)
        self.audio_mode_var.set(state.audio_mode)
        self.audio_file_var.set(state.audio_file_path)
        self.startup_phrase_var.set(state.startup_phrase)
        self.startup_delay_var.set(state.startup_delay)
        self.selected_routine_var.set(state.active_routine)
        self.routine_store.routine_name = state.active_routine
        if sys.platform == "win32":
            self.startup_var.set(bool(state.startup_enabled))

        self._update_audio_visibility()
        self._sync_slider_labels()
        self._refresh_routine_selector()
        self._refresh_routine_list()
        self._mark_clean("Reset to current config")
        if mark_status:
            logger.info("UI_EVENT: form_reset")

    def _update_audio_visibility(self):
        is_enabled = self.audio_enabled_var.get()
        mode = self.audio_mode_var.get()
        if mode == "tts":
            self.phrase_frame.pack(fill="x", padx=5, pady=5)
        else:
            self.phrase_frame.pack_forget()
        if is_enabled and mode == "file":
            self.audio_file_entry.state(["!disabled"])
            self.audio_browse_btn.state(["!disabled"])
        else:
            self.audio_file_entry.state(["disabled"])
            self.audio_browse_btn.state(["disabled"])
        if is_enabled:
            self.audio_test_btn.state(["!disabled"])
        else:
            self.audio_test_btn.state(["disabled"])

    def _browse_audio_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav *.ogg"), ("All files", "*.*")])
        if file_path:
            self.audio_file_var.set(file_path)

    def _test_audio(self):
        from src.audio import AudioEngine

        old_settings = {
            "enabled": self.config_manager.audio_settings.get("enabled"),
            "mode": self.config_manager.audio_settings.get("mode"),
            "file_path": self.config_manager.audio_settings.get("file_path"),
        }
        try:
            self.config_manager.audio_settings["enabled"] = True
            self.config_manager.audio_settings["mode"] = self.audio_mode_var.get()
            self.config_manager.audio_settings["file_path"] = self.audio_file_var.get()
            temp_engine = AudioEngine(self.config_manager)
            temp_engine.enabled = True
            temp_engine.maybe_initialize()
            if self.audio_mode_var.get() == "tts":
                temp_engine.speak(self.startup_phrase_var.get())
            else:
                temp_engine.play_file(self.audio_file_var.get())
            logger.info("UI_EVENT: audio_test_triggered mode=%s", self.audio_mode_var.get())
            self._set_status("Played feedback preview.", level="success")
        finally:
            self.config_manager.audio_settings.update(old_settings)

    def _test_active_routine(self):
        if self.trigger_routine_callback:
            self.trigger_routine_callback(source="settings_test")
            self._set_status("Triggered active routine.", level="success")
        else:
            messagebox.showinfo("Info", "Routine trigger is not available right now.")

    def _trigger_selected_routine(self):
        routine = self.selected_routine_var.get()
        if not routine:
            return
        if self.switch_routine_callback:
            self.switch_routine_callback(routine, source="settings_manual_select")
        if self.trigger_routine_callback:
            self.trigger_routine_callback(source="settings_selected_routine")
            self._set_status(f"Triggered routine '{routine}'.", level="success")

    def _open_guided_calibration(self):
        if not self.detector or not getattr(self.detector, "stream", None):
            messagebox.showwarning(
                "Calibration Unavailable",
                "Microphone stream is not active yet. Wait a moment and try again.",
            )
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Guided Calibration")
        dialog.geometry("520x330")
        dialog.minsize(500, 300)
        dialog.transient(self.root)
        dialog.grab_set()

        title = ttk.Label(dialog, text="Guided Clap Calibration", font=("", 11, "bold"))
        title.pack(anchor="w", padx=12, pady=(12, 6))
        info_var = tk.StringVar(value="Step 1/2: Stay quiet for 3 seconds to measure ambient noise.")
        ttk.Label(dialog, textvariable=info_var, wraplength=480).pack(anchor="w", padx=12, pady=4)
        progress = ttk.Progressbar(dialog, mode="determinate", maximum=100)
        progress.pack(fill="x", padx=12, pady=8)
        result_box = tk.Text(dialog, height=8, wrap="word")
        result_box.pack(fill="both", expand=True, padx=12, pady=6)
        result_box.insert("1.0", "Press Start to begin.")
        result_box.config(state="disabled")

        buttons = ttk.Frame(dialog)
        buttons.pack(fill="x", padx=12, pady=(0, 12))
        start_btn = ttk.Button(buttons, text="Start", width=12)
        start_btn.pack(side="left")
        apply_btn = ttk.Button(buttons, text="Apply Recommended", width=18, state="disabled")
        apply_btn.pack(side="right")
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="right", padx=8)

        ambient_samples = []
        clap_peaks = []
        clap_intervals = []
        last_clap_ts = None
        recommendation = {"value": None}

        def write_result(text):
            result_box.config(state="normal")
            result_box.delete("1.0", "end")
            result_box.insert("1.0", text)
            result_box.config(state="disabled")

        def sample_for(duration_s, on_sample, on_done, started=None):
            start_t = started if started is not None else time.monotonic()
            elapsed = time.monotonic() - start_t
            pct = min(100, int((elapsed / duration_s) * 100))
            progress["value"] = pct
            on_sample()
            if elapsed >= duration_s:
                on_done()
                return
            dialog.after(60, lambda: sample_for(duration_s, on_sample, on_done, start_t))

        def do_ambient_phase():
            info_var.set("Step 1/2: Measuring ambient noise...")
            progress["value"] = 0

            def on_sample():
                ambient_samples.append(float(getattr(self.detector, "last_peak", 0.0)))

            def done():
                do_clap_phase()

            sample_for(3.0, on_sample, done)

        def do_clap_phase():
            info_var.set("Step 2/2: Clap naturally 4 to 6 times in front of your microphone.")
            progress["value"] = 0

            baseline = max(ambient_samples) if ambient_samples else 0.01
            dynamic_gate = max(self.threshold_var.get() * 0.9, baseline * 2.2, 0.04)

            def on_sample():
                nonlocal last_clap_ts
                peak = float(getattr(self.detector, "last_peak", 0.0))
                now = time.monotonic()
                if peak >= dynamic_gate:
                    if last_clap_ts is None or (now - last_clap_ts) > 0.18:
                        clap_peaks.append(peak)
                        if last_clap_ts is not None:
                            clap_intervals.append(now - last_clap_ts)
                        last_clap_ts = now

            def done():
                rec = recommend_clap_settings(
                    ambient_samples,
                    clap_peaks,
                    clap_intervals,
                    current_threshold=self.threshold_var.get(),
                    current_min_interval=self.min_interval_var.get(),
                )
                recommendation["value"] = rec
                info_var.set("Calibration complete.")
                write_result(
                    f"{rec.summary}\n\nDetected clap samples: {len(clap_peaks)}\n"
                    f"Recommended threshold: {rec.threshold}\n"
                    f"Recommended cooldown: {rec.min_interval}s"
                )
                apply_btn.state(["!disabled"])
                logger.info(
                    "UI_EVENT: calibration_completed threshold=%.3f min_interval=%.3f confidence=%s claps=%s",
                    rec.threshold,
                    rec.min_interval,
                    rec.confidence,
                    len(clap_peaks),
                )

            sample_for(7.0, on_sample, done)

        def start():
            start_btn.state(["disabled"])
            write_result("Collecting ambient and clap samples...")
            do_ambient_phase()

        def apply_recommendation():
            rec = recommendation["value"]
            if not rec:
                return
            self.threshold_var.set(rec.threshold)
            self.min_interval_var.set(rec.min_interval)
            self._mark_dirty("Calibration applied (unsaved)")
            messagebox.showinfo(
                "Calibration Applied",
                "Recommended sensitivity values were applied. Click Apply or Save to persist them.",
                parent=dialog,
            )

        start_btn.config(command=start)
        apply_btn.config(command=apply_recommendation)

    def _open_logs(self):
        log_dir = get_log_dir()
        if not os.path.exists(log_dir):
            messagebox.showinfo("Information", f"Log directory does not exist yet: {log_dir}")
            return
        if sys.platform == "win32":
            os.startfile(log_dir)
        else:
            subprocess.Popen(["xdg-open", log_dir])

    def _get_runtime_status(self):
        if not self.detector:
            return RuntimeStatus(False, False, "NO DETECTOR", 0, 0.0)
        return RuntimeStatus(
            detector_available=True,
            detector_active=bool(getattr(self.detector, "stream", None)),
            state=str(getattr(self.detector, "state", "IDLE")),
            clap_count=int(getattr(self.detector, "clap_count", 0)),
            peak=float(getattr(self.detector, "last_peak", 0.0)),
        )

    def _get_runtime_snapshot(self):
        if self.runtime_snapshot_provider:
            return self.runtime_snapshot_provider()
        return AppRuntimeSnapshot(
            listening_enabled=True,
            active_routine=self.selected_routine_var.get() or "morning_routine",
            runtime_ready=bool(self.detector),
        )

    def _update_runtime_status_label(self, status):
        if not self.runtime_status_label:
            return
        human_state, color = describe_detector_state(
            detector_available=status.detector_available,
            detector_active=status.detector_active,
            state=status.state,
            clap_count=status.clap_count,
            peak=status.peak,
            threshold=self.threshold_var.get(),
        )
        self.runtime_status_label.config(
            text=f"Runtime status: {human_state} | peak={status.peak:.3f} | claps={status.clap_count}",
            foreground=color,
        )

    def _get_microphone_label(self):
        if not pyaudio:
            return "Note: PyAudio not detected. Clap detection may be unavailable."
        try:
            with PYAUDIO_LOCK:
                p = pyaudio.PyAudio()
                dev = p.get_default_input_device_info()
                name = dev.get("name", "Default")
                p.terminate()
            return f"Mic: {name}"
        except Exception:
            return "Mic: Default system microphone"

    def _browse_target(self, name_var, target_var):
        file_path = filedialog.askopenfilename()
        if file_path:
            target_var.set(file_path)
            if not name_var.get():
                name_var.set(os.path.basename(file_path).split(".")[0])

    def _browse_icon(self, icon_var):
        icon_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.ico"), ("All files", "*.*")]
        )
        if icon_path:
            icon_var.set(icon_path)

    def _identifier_tag(self, item_id):
        for tag in self.routine_tree.item(item_id, "tags"):
            if "||" in tag:
                return tag
        return None

    def _index_from_tree_item(self, item_id):
        tag = self._identifier_tag(item_id)
        if not tag:
            return self.routine_tree.index(item_id)
        try:
            return int(tag.rsplit("||", 1)[1])
        except (ValueError, IndexError):
            return self.routine_tree.index(item_id)

    def _close_window(self):
        self._monitoring = False
        SettingsUI._instance = None
        if self.root:
            self.root.destroy()
        logger.info("UI_EVENT: settings_window_closed")
