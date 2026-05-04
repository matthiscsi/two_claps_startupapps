import logging
import os
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from src.audio_lock import PYAUDIO_LOCK
from src.calibration import recommend_clap_settings
from src.config import get_resource_path
from src.startup_helper import apply_startup_state, get_startup_state
from src.ui_assets import IconRegistry
from src.ui_first_run import FirstRunMixin
from src.ui_layout import ScrollableFrame, preferred_window_geometry
from src.ui_monitor_preview import draw_layout_preview
from src.ui_theme import add_tooltip, apply_theme
from src.ui_troubleshooting import TroubleshootingMixin
from src.ui_animation import next_animation_step, pulse_color
from src.ui_logic import (
    UIValidationError,
    apply_form_state_to_config,
    build_routine_item,
    choose_routine_selection,
    cloned_config_data,
    describe_monitor_placement,
    describe_detector_state,
    detect_duplicate_item_names,
    is_routine_item_enabled,
    normalize_routine_timing,
    parse_monitor_value,
    pick_default_monitor_option,
    summarize_routine_next_action,
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


class SettingsUI(FirstRunMixin, TroubleshootingMixin):
    _instance = None

    def __init__(
        self,
        config_manager,
        on_save_callback=None,
        detector=None,
        runtime_snapshot_provider=None,
        trigger_routine_callback=None,
        switch_routine_callback=None,
        trigger_item_callback=None,
    ):
        self.config_manager = config_manager
        self.on_save_callback = on_save_callback
        self.detector = detector
        self.runtime_snapshot_provider = runtime_snapshot_provider
        self.trigger_routine_callback = trigger_routine_callback
        self.switch_routine_callback = switch_routine_callback
        self.trigger_item_callback = trigger_item_callback
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
        self.logs_preview = None
        self.icons = None
        self.dashboard_status_var = None
        self.dashboard_next_action_var = None
        self.dashboard_startup_var = None
        self.calibration_summary_var = None
        self.item_editor_vars = {}
        self.item_editor_widgets = []
        self.item_editor_canvas = None
        self._preview_phase = 0
        self._pulse_step = 0
        self._first_run_prompted = False

    def open(self):
        if SettingsUI._instance:
            logger.info("UI_EVENT: settings_window_reuse_requested")
            try:
                SettingsUI._instance.after(0, lambda: SettingsUI._instance.deiconify())
                SettingsUI._instance.after(10, lambda: SettingsUI._instance.lift())
                SettingsUI._instance.after(20, lambda: SettingsUI._instance.focus_force())
            except Exception:
                logger.warning("UI_EVENT: existing_settings_window_invalid_resetting_singleton", exc_info=True)
                SettingsUI._instance = None
            if SettingsUI._instance:
                logger.info("UI_EVENT: settings_window_reused")
                return

        try:
            logger.info("UI_EVENT: opening_settings_window")
            self.root = tk.Tk()
            SettingsUI._instance = self.root
            self.root.title("Jarvis Control Center")
            self.icons = IconRegistry(self.root)
            icon_path = get_resource_path(os.path.join("assets", "icon.ico"))
            if os.path.exists(icon_path):
                try:
                    self.root.iconbitmap(icon_path)
                except Exception:
                    pass

            self.root.geometry(preferred_window_geometry(self.root))
            self.root.minsize(860, 620)
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
                text="Jarvis Control Center",
                style="HeroTitle.TLabel",
            ).grid(row=0, column=0, sticky="w")
            ttk.Label(
                header,
                text="Tune clap detection, shape startup routines, and diagnose launch behavior from one place.",
                foreground="#444",
            ).grid(row=1, column=0, sticky="w")
            self.quick_state_label = ttk.Label(header, text="", foreground="#555")
            self.quick_state_label.grid(row=0, column=1, rowspan=2, sticky="e")

            self.notebook = ttk.Notebook(self.root)
            self.notebook.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)

            logger.info("UI_EVENT: building_dashboard_tab")
            self._create_dashboard_tab()
            logger.info("UI_EVENT: building_routines_tab")
            self._create_routines_tab()
            logger.info("UI_EVENT: building_calibration_tab")
            self._create_calibration_tab()
            logger.info("UI_EVENT: building_troubleshooting_tab")
            self._create_troubleshooting_tab()
            logger.info("UI_EVENT: tabs_built")

            # Important: bind/reset only after all tabs/widgets exist.
            self._bind_dirty_tracking()
            self._reset_form_from_config(mark_status=False)
            logger.info("UI_EVENT: initial_form_state_loaded")

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

            self._bind_keyboard_shortcuts()
            self._mark_clean("Ready")
            self.root.after(500, self._update_runtime_header)
            self.root.after(700, self._animate_control_center)
            self.root.after(900, self._maybe_show_first_run)
            logger.info("UI_EVENT: settings_window_mainloop_start")
            self.root.mainloop()
            logger.info("UI_EVENT: settings_window_mainloop_end")
        except Exception as e:
            logger.error("Failed to open Settings UI: %s", e, exc_info=True)
            SettingsUI._instance = None
            if self.root:
                try:
                    self.root.destroy()
                except Exception:
                    pass

    def _create_dashboard_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Dashboard")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        scroller = ScrollableFrame(tab)
        scroller.grid(row=0, column=0, sticky="nsew")
        content = scroller.content

        overview = ttk.LabelFrame(content, text="At a Glance")
        overview.pack(fill="x", padx=10, pady=8)
        overview.columnconfigure((0, 1, 2), weight=1)
        self.dashboard_status_var = tk.StringVar(value="Runtime status: starting...")
        self.dashboard_next_action_var = tk.StringVar(value="Next trigger: loading routine...")
        self.dashboard_startup_var = tk.StringVar(value="Startup: unknown")
        self._create_dashboard_metric(overview, 0, "Runtime", self.dashboard_status_var)
        self._create_dashboard_metric(overview, 1, "Next Action", self.dashboard_next_action_var)
        self._create_dashboard_metric(overview, 2, "Startup", self.dashboard_startup_var)

        setup_frame = ttk.LabelFrame(content, text="Setup Path")
        setup_frame.pack(fill="x", padx=10, pady=8)
        setup_frame.columnconfigure(1, weight=1)
        setup_image = self.icons.get("setup_welcome") if self.icons else None
        if setup_image:
            ttk.Label(setup_frame, image=setup_image).grid(row=0, column=0, rowspan=2, sticky="w", padx=10, pady=10)
        ttk.Label(
            setup_frame,
            text="First-run setup guides microphone readiness, routine creation, startup, and a final test.",
            style="Hint.TLabel",
            wraplength=560,
        ).grid(row=0, column=1, sticky="w", padx=10, pady=(10, 4))
        self._icon_button(
            setup_frame,
            icon="config",
            text="Open First-Run Setup",
            command=lambda: self._open_first_run_setup(auto=False),
        ).grid(row=1, column=1, sticky="w", padx=10, pady=(0, 10))

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
        calibrate_btn = self._icon_button(
            button_row,
            icon="calibrate",
            text="Open Calibration",
            style="Primary.TButton",
            command=lambda: self.notebook.select(self.calibration_tab),
        )
        calibrate_btn.pack(side="left", padx=(0, 8))
        ttk.Label(
            button_row,
            text="Use the guided wizard when the room changes or triggers feel unreliable.",
            style="Hint.TLabel",
        ).pack(side="left")
        add_tooltip(calibrate_btn, "Guided calibration takes about 10 seconds.")

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
            text="Drag items by the handle (::) to reorder launch sequence.",
            style="Hint.TLabel",
        )
        helper.pack(anchor="w", padx=10, pady=(2, 2))

        paned = ttk.Panedwindow(content, orient="horizontal")
        paned.pack(expand=True, fill="both", padx=10, pady=5)

        tree_frame = ttk.Frame(paned)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        paned.add(tree_frame, weight=3)

        detail_frame = ttk.LabelFrame(paned, text="Selected Item")
        detail_frame.columnconfigure(1, weight=1)
        paned.add(detail_frame, weight=2)

        self.routine_tree = ttk.Treeview(
            tree_frame,
            columns=("Handle", "Enabled", "Name", "Type", "Path", "Monitor", "Position", "Delay"),
            show="headings",
            style="Routine.Treeview",
        )
        self.routine_tree.tag_configure("dragging", background="#e1f5fe")
        self.routine_tree.tag_configure("disabled", foreground="#8a8f98")
        self.routine_tree.heading("Handle", text="")
        self.routine_tree.column("Handle", width=40, anchor="center", stretch=False)
        self.routine_tree.heading("Enabled", text="On")
        self.routine_tree.column("Enabled", width=46, anchor="center", stretch=False)
        self.routine_tree.heading("Name", text="Name")
        self.routine_tree.column("Name", width=150)
        self.routine_tree.heading("Type", text="Kind")
        self.routine_tree.column("Type", width=95)
        self.routine_tree.heading("Path", text="What to launch")
        self.routine_tree.column("Path", width=250)
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
        self.routine_tree.bind("<Double-1>", lambda _e: self._edit_routine_item())
        self.routine_tree.bind("<Delete>", lambda _e: self._remove_routine_item())
        self.routine_tree.bind("<<TreeviewSelect>>", lambda _e: self._load_selected_item_into_editor())
        self._drag_data = {"item": None, "dragged": False}

        self._create_item_detail_editor(detail_frame)

        self.empty_state_label = ttk.Label(
            content,
            text="No items yet. Click Add Item to build your routine.",
            style="Hint.TLabel",
        )
        self.empty_state_label.pack(anchor="w", padx=12, pady=(0, 8))

        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill="x", padx=10, pady=(6, 15))
        self._icon_button(btn_frame, icon="add", text="Add Item", command=self._add_routine_item).pack(side="left", padx=4)
        self._icon_button(btn_frame, icon="edit", text="Edit Modal", command=self._edit_routine_item).pack(side="left", padx=4)
        self._icon_button(btn_frame, icon="duplicate", text="Duplicate", command=self._duplicate_routine_item).pack(side="left", padx=4)
        self._icon_button(btn_frame, icon="success", text="Toggle On/Off", command=self._toggle_selected_item_enabled).pack(side="left", padx=4)
        self._icon_button(btn_frame, icon="delete", text="Remove", command=self._remove_routine_item).pack(side="left", padx=4)
        self._icon_button(btn_frame, icon="up", text="Move Up", command=lambda: self._move_selected_item(-1)).pack(side="left", padx=4)
        self._icon_button(btn_frame, icon="down", text="Move Down", command=lambda: self._move_selected_item(1)).pack(side="left", padx=4)
        self._icon_button(btn_frame, icon="test", text="Test Item", command=self._test_selected_item).pack(side="left", padx=4)
        self._icon_button(btn_frame, icon="run", text="Run Routine", style="Primary.TButton", command=self._trigger_selected_routine).pack(side="right", padx=4)

        self._refresh_routine_selector()
        self._refresh_routine_list()

    def _create_calibration_tab(self):
        tab = ttk.Frame(self.notebook)
        self.calibration_tab = tab
        self.notebook.add(tab, text="Calibration")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        scroller = ScrollableFrame(tab)
        scroller.grid(row=0, column=0, sticky="nsew")
        content = scroller.content

        wizard = ttk.LabelFrame(content, text="Guided Microphone Calibration")
        wizard.pack(fill="x", padx=10, pady=8)
        ttk.Label(
            wizard,
            text="Use this when Jarvis misses claps, hears desk noise, or you move to a different room.",
            style="Hint.TLabel",
            wraplength=740,
        ).pack(anchor="w", padx=10, pady=(10, 6))
        self.calibration_summary_var = tk.StringVar(value="Current recommendation: run the wizard to measure this room.")
        ttk.Label(wizard, textvariable=self.calibration_summary_var, style="Status.TLabel", wraplength=740).pack(
            anchor="w", padx=10, pady=(0, 8)
        )
        self._icon_button(
            wizard,
            icon="calibrate",
            text="Start Guided Calibration",
            style="Primary.TButton",
            command=self._open_guided_calibration,
        ).pack(anchor="w", padx=10, pady=(0, 10))

        steps = ttk.LabelFrame(content, text="What Jarvis Measures")
        steps.pack(fill="x", padx=10, pady=8)
        ttk.Label(
            steps,
            text=(
                "1. Ambient noise: stay quiet so Jarvis learns the room floor.\n"
                "2. Clap samples: clap naturally four to six times.\n"
                "3. Recommendation: apply threshold and cooldown, then Apply or Save."
            ),
            justify="left",
        ).pack(anchor="w", padx=10, pady=10)

    def _create_troubleshooting_tab(self):
        return TroubleshootingMixin._create_troubleshooting_tab(self)

    def _icon_button(self, parent, *, icon, text, command, style="Secondary.TButton", **kwargs):
        if self.icons:
            return self.icons.button(parent, icon=icon, text=text, command=command, style=style, **kwargs)
        return ttk.Button(parent, text=text, style=style, command=command, **kwargs)

    def _create_dashboard_metric(self, parent, column, title, textvariable):
        box = ttk.Frame(parent, style="Card.TFrame", padding=(10, 8))
        box.grid(row=0, column=column, sticky="nsew", padx=6, pady=8)
        ttk.Label(box, text=title, style="Hint.TLabel").pack(anchor="w")
        ttk.Label(box, textvariable=textvariable, style="Metric.TLabel", wraplength=230).pack(anchor="w", pady=(4, 0))

    def _create_item_detail_editor(self, parent):
        vars_ = {
            "enabled": tk.BooleanVar(value=True),
            "name": tk.StringVar(),
            "type": tk.StringVar(value="app"),
            "target": tk.StringVar(),
            "monitor": tk.StringVar(),
            "position": tk.StringVar(value="full"),
            "delay": tk.StringVar(value="0.0"),
            "args": tk.StringVar(),
            "window_title_match": tk.StringVar(),
            "window_wait_timeout": tk.StringVar(value="15.0"),
            "window_poll_interval": tk.StringVar(value="1.0"),
            "icon": tk.StringVar(),
        }
        self.item_editor_vars = vars_
        self.item_editor_widgets = []
        self.item_editor_canvas = tk.Canvas(parent, width=220, height=130, bg="#0f172a", highlightthickness=0)

        enabled_check = ttk.Checkbutton(parent, text="Enabled in routine", variable=vars_["enabled"])
        enabled_check.grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))
        self.item_editor_widgets.append(enabled_check)
        fields = [
            ("Name", "name", "entry"),
            ("Type", "type", "combo"),
            ("Target", "target", "target"),
            ("Monitor", "monitor", "monitor"),
            ("Position", "position", "position"),
            ("Delay (s)", "delay", "entry"),
            ("Arguments", "args", "entry"),
            ("Window title match", "window_title_match", "entry"),
            ("Wait timeout (s)", "window_wait_timeout", "entry"),
            ("Poll interval (s)", "window_poll_interval", "entry"),
            ("Icon path", "icon", "icon"),
        ]
        monitor_options = self._monitor_options()
        for row, (label, key, kind) in enumerate(fields, start=1):
            ttk.Label(parent, text=f"{label}:").grid(row=row, column=0, sticky="e", padx=8, pady=3)
            if kind == "combo":
                widget = ttk.Combobox(parent, textvariable=vars_[key], values=["app", "url", "shortcut"], state="readonly")
            elif kind == "monitor":
                widget = ttk.Combobox(parent, textvariable=vars_[key], values=monitor_options, state="readonly")
            elif kind == "position":
                widget = ttk.Combobox(parent, textvariable=vars_[key], values=["full", "left", "right", "top", "bottom"], state="readonly")
            elif kind in {"target", "icon"}:
                frame = ttk.Frame(parent)
                widget = frame
                entry = ttk.Entry(frame, textvariable=vars_[key])
                entry.pack(side="left", fill="x", expand=True)
                browse_cmd = (lambda v=vars_[key]: self._browse_icon(v)) if kind == "icon" else (
                    lambda n=vars_["name"], t=vars_[key]: self._browse_target(n, t)
                )
                ttk.Button(frame, text="...", width=3, command=browse_cmd).pack(side="right", padx=(4, 0))
            else:
                widget = ttk.Entry(parent, textvariable=vars_[key])
            widget.grid(row=row, column=1, sticky="ew", padx=8, pady=3)
            self.item_editor_widgets.append(widget)

        preview_row = len(fields) + 1
        self.item_editor_canvas.grid(row=preview_row, column=0, columnspan=2, pady=(8, 4))
        self.item_preview_var = tk.StringVar(value="Select an item to edit placement.")
        ttk.Label(parent, textvariable=self.item_preview_var, style="Hint.TLabel", wraplength=320).grid(
            row=preview_row + 1, column=0, columnspan=2, sticky="w", padx=8
        )
        self._icon_button(parent, icon="success", text="Apply Item Changes", style="Primary.TButton", command=self._apply_item_detail_changes).grid(
            row=preview_row + 2, column=0, columnspan=2, sticky="ew", padx=8, pady=8
        )
        vars_["monitor"].trace_add("write", lambda *_: self._refresh_item_editor_preview())
        vars_["position"].trace_add("write", lambda *_: self._refresh_item_editor_preview())
        self._set_item_editor_enabled(False)

    def _monitor_options(self):
        from src.launcher import Launcher

        return Launcher.get_monitor_options()

    def _set_item_editor_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for widget in self.item_editor_widgets:
            try:
                widget.configure(state=state)
            except tk.TclError:
                for child in widget.winfo_children():
                    try:
                        child.configure(state=state)
                    except tk.TclError:
                        pass

    def _selected_item_index(self):
        selected = self.routine_tree.selection()
        if len(selected) != 1:
            return None
        idx = self._index_from_tree_item(selected[0])
        items = self.routine_store.get_items()
        if not (0 <= idx < len(items)):
            return None
        return idx

    def _load_selected_item_into_editor(self):
        idx = self._selected_item_index()
        if idx is None:
            self._set_item_editor_enabled(False)
            return
        item = self.routine_store.get_items()[idx]
        vars_ = self.item_editor_vars
        vars_["enabled"].set(is_routine_item_enabled(item))
        vars_["name"].set(item.get("name", ""))
        vars_["type"].set(item.get("type", "app"))
        vars_["target"].set(item.get("target", ""))
        vars_["monitor"].set(pick_default_monitor_option(self._monitor_options(), item.get("monitor")))
        vars_["position"].set(item.get("position", "full"))
        vars_["delay"].set(str(item.get("delay", 0.0)))
        vars_["args"].set(item.get("args", ""))
        vars_["window_title_match"].set(item.get("window_title_match", ""))
        vars_["window_wait_timeout"].set(str(item.get("window_wait_timeout", 15.0)))
        vars_["window_poll_interval"].set(str(item.get("window_poll_interval", 1.0)))
        vars_["icon"].set(item.get("icon", ""))
        self._set_item_editor_enabled(True)
        self._refresh_item_editor_preview()

    def _refresh_item_editor_preview(self):
        if not self.item_editor_vars or not self.item_editor_canvas:
            return
        monitor = self.item_editor_vars["monitor"].get()
        position = self.item_editor_vars["position"].get()
        self.item_preview_var.set(describe_monitor_placement(monitor, position))
        self._draw_layout_preview(self.item_editor_canvas, position)

    def _apply_item_detail_changes(self):
        idx = self._selected_item_index()
        if idx is None:
            messagebox.showinfo("Edit item", "Select exactly one item to edit.")
            return
        vars_ = self.item_editor_vars
        try:
            warning_message = validate_routine_item_inputs(
                name=vars_["name"].get(), item_type=vars_["type"].get(), target=vars_["target"].get()
            )
            delay, wait_timeout, poll_interval = normalize_routine_timing(
                vars_["delay"].get(),
                vars_["window_wait_timeout"].get(),
                vars_["window_poll_interval"].get(),
            )
        except UIValidationError as exc:
            messagebox.showerror("Invalid item", str(exc))
            return
        if warning_message and not messagebox.askyesno("Warning", warning_message):
            return
        item = build_routine_item(
            name=vars_["name"].get(),
            enabled=vars_["enabled"].get(),
            item_type=vars_["type"].get(),
            target=vars_["target"].get(),
            args=vars_["args"].get(),
            monitor_value=vars_["monitor"].get(),
            position=vars_["position"].get(),
            delay=delay,
            icon=vars_["icon"].get(),
            window_title_match=vars_["window_title_match"].get(),
            window_wait_timeout=wait_timeout,
            window_poll_interval=poll_interval,
        )
        self.routine_store.upsert_item(item, idx)
        self._refresh_routine_list()
        rows = self.routine_tree.get_children()
        if idx < len(rows):
            self.routine_tree.selection_set(rows[idx])
            self.routine_tree.focus(rows[idx])
        self._mark_dirty("Routine item updated (unsaved)")

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

    def _bind_keyboard_shortcuts(self):
        def bind(sequence, callback):
            self.root.bind_all(sequence, lambda event: (callback(), "break")[1])

        bind("<Control-s>", lambda: self._save_settings(close_window=False))
        bind("<Control-Return>", lambda: self._save_settings(close_window=False))
        bind("<Control-Shift-S>", lambda: self._save_settings(close_window=True))
        bind("<F5>", self._trigger_selected_routine)
        bind("<Control-n>", self._add_routine_item)
        bind("<Control-d>", self._duplicate_routine_item)
        bind("<Control-e>", self._toggle_selected_item_enabled)
        bind("<Escape>", self._close_window)

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
        self._update_dashboard_cards()

    def _update_dashboard_cards(self):
        if not self.dashboard_status_var:
            return
        status = self._get_runtime_status()
        snapshot = self._get_runtime_snapshot()
        human_state, _color = describe_detector_state(
            detector_available=status.detector_available,
            detector_active=status.detector_active,
            state=status.state,
            clap_count=status.clap_count,
            peak=status.peak,
            threshold=float(self.threshold_var.get()) if hasattr(self, "threshold_var") else 0.15,
        )
        active_items = self.config_manager.routines.get(snapshot.active_routine, {}).get("items", [])
        startup_enabled = self.startup_var.get() if hasattr(self, "startup_var") else None
        startup_text = "Startup: unknown" if startup_enabled is None else f"Startup: {'on' if startup_enabled else 'off'}"
        self.dashboard_status_var.set(f"{human_state} | peak {status.peak:.3f}")
        self.dashboard_next_action_var.set(summarize_routine_next_action(active_items))
        self.dashboard_startup_var.set(startup_text)
        if self.calibration_summary_var:
            self.calibration_summary_var.set(
                f"Current threshold {float(self.threshold_var.get()):.3f}, cooldown {float(self.min_interval_var.get()):.2f}s."
            )

    def _refresh_routine_selector(self):
        routines = sorted(self.config_manager.routines.keys())
        self.routine_selector["values"] = routines
        current = self.selected_routine_var.get() if hasattr(self, "selected_routine_var") else ""
        configured = self.config_manager.system_settings.get("active_routine", "morning_routine")
        desired = choose_routine_selection(routines, current_selection=current, configured_selection=configured)
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
            icon = {"app": "[app]", "url": "[url]", "shortcut": "[lnk]"}.get(item_type, "[item]")
            enabled = is_routine_item_enabled(item)
            tag = f"{item.get('name')}||{idx}"
            row_id = self.routine_tree.insert(
                "",
                "end",
                values=(
                    "::",
                    "Yes" if enabled else "No",
                    item.get("name"),
                    f"{icon} {item_type.title()}",
                    item.get("target"),
                    item.get("monitor"),
                    item.get("position"),
                    f"{float(item.get('delay', 0)):.1f}",
                ),
                tags=(tag,) if enabled else (tag, "disabled"),
            )
            if idx in selected_indices:
                self.routine_tree.selection_add(row_id)
        if self.empty_state_label:
            if items:
                self.empty_state_label.pack_forget()
            else:
                self.empty_state_label.pack(anchor="w", padx=12, pady=(0, 8))
        self._update_dashboard_cards()

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

    def _toggle_selected_item_enabled(self):
        idx = self._selected_item_index()
        if idx is None:
            messagebox.showinfo("Toggle item", "Select exactly one item to enable or disable.")
            return
        enabled = self.routine_store.toggle_item_enabled(idx)
        if enabled is None:
            return
        self._refresh_routine_list()
        rows = self.routine_tree.get_children()
        if idx < len(rows):
            self.routine_tree.selection_set(rows[idx])
            self.routine_tree.focus(rows[idx])
        state = "enabled" if enabled else "disabled"
        self._mark_dirty(f"Routine item {state} (unsaved)")
        self._set_status(f"Selected item {state}.", level="success")

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
        position_combo = ttk.Combobox(dialog, textvariable=pos_var, values=["full", "left", "right", "top", "bottom"], state="readonly")
        position_combo.grid(
            row=6, column=1, padx=5, pady=5, sticky="ew"
        )
        preview_var = tk.StringVar(value=describe_monitor_placement(monitor_var.get(), pos_var.get()))
        ttk.Label(dialog, textvariable=preview_var, style="Hint.TLabel", wraplength=420).grid(
            row=7, column=1, padx=5, pady=(0, 6), sticky="w"
        )
        layout_canvas = tk.Canvas(dialog, width=220, height=130, bg="#0f172a", highlightthickness=0)
        layout_canvas.grid(row=7, column=0, rowspan=2, padx=8, pady=(0, 6), sticky="n")

        ttk.Label(dialog, text="Delay before launch (s):").grid(row=8, column=0, padx=5, pady=5, sticky="e")
        delay_var = tk.DoubleVar(value=float(old_item.get("delay", 0.0)))
        ttk.Entry(dialog, textvariable=delay_var).grid(row=8, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(dialog, text="Window wait timeout (s):").grid(row=9, column=0, padx=5, pady=5, sticky="e")
        wait_var = tk.DoubleVar(value=float(old_item.get("window_wait_timeout", 15.0)))
        ttk.Entry(dialog, textvariable=wait_var).grid(row=9, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(dialog, text="Window poll interval (s):").grid(row=10, column=0, padx=5, pady=5, sticky="e")
        poll_var = tk.DoubleVar(value=float(old_item.get("window_poll_interval", 1.0)))
        ttk.Entry(dialog, textvariable=poll_var).grid(row=10, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(dialog, text="CLI Arguments (optional):").grid(row=11, column=0, padx=5, pady=5, sticky="e")
        args_var = tk.StringVar(value=old_item.get("args", ""))
        ttk.Entry(dialog, textvariable=args_var).grid(row=11, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(dialog, text="Icon Path (optional):").grid(row=12, column=0, padx=5, pady=5, sticky="e")
        icon_frame = ttk.Frame(dialog)
        icon_frame.grid(row=12, column=1, padx=5, pady=5, sticky="ew")
        icon_var = tk.StringVar(value=old_item.get("icon", ""))
        ttk.Entry(icon_frame, textvariable=icon_var).pack(side="left", expand=True, fill="x")
        ttk.Button(icon_frame, text="...", width=3, command=lambda: self._browse_icon(icon_var)).pack(side="right", padx=2)

        dialog.columnconfigure(1, weight=1)

        def refresh_preview(*_args):
            preview_var.set(describe_monitor_placement(monitor_var.get(), pos_var.get()))
            self._draw_layout_preview(layout_canvas, pos_var.get())

        monitor_combo.bind("<<ComboboxSelected>>", refresh_preview)
        position_combo.bind("<<ComboboxSelected>>", refresh_preview)
        self._draw_layout_preview(layout_canvas, pos_var.get())

        def save_item():
            try:
                warning_message = validate_routine_item_inputs(
                    name=name_var.get(), item_type=type_var.get(), target=target_var.get()
                )
                delay, wait_timeout, poll_interval = normalize_routine_timing(
                    delay_var.get(),
                    wait_var.get(),
                    poll_var.get(),
                )
            except UIValidationError as e:
                messagebox.showerror("Error", str(e))
                return
            if warning_message and not messagebox.askyesno("Warning", warning_message):
                return

            new_item = build_routine_item(
                name=name_var.get(),
                enabled=old_item.get("enabled", True),
                item_type=type_var.get(),
                target=target_var.get(),
                args=args_var.get(),
                monitor_value=monitor_var.get(),
                position=pos_var.get(),
                delay=delay,
                icon=icon_var.get(),
                window_title_match=old_item.get("window_title_match", ""),
                window_wait_timeout=wait_timeout,
                window_poll_interval=poll_interval,
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

        ttk.Button(dialog, text="Save Item" if is_edit else "Add Item", style="Primary.TButton", command=save_item).grid(row=13, columnspan=2, pady=12)

    def _remove_routine_item(self):
        selected = self.routine_tree.selection()
        if not selected:
            return
        indices = [self.routine_tree.index(item_id) for item_id in selected]
        self.routine_store.remove_by_indices(indices)
        self._refresh_routine_list()
        self._mark_dirty("Routine item removed (unsaved)")
        logger.info("UI_EVENT: routine_item_removed count=%s", len(indices))

    def _move_selected_item(self, direction):
        selected = self.routine_tree.selection()
        if len(selected) != 1:
            messagebox.showinfo("Reorder item", "Select exactly one item to move.")
            return
        old_index = self.routine_tree.index(selected[0])
        new_index = self.routine_store.move_item(old_index, direction)
        if new_index == old_index:
            return
        self._refresh_routine_list()
        rows = self.routine_tree.get_children()
        if 0 <= new_index < len(rows):
            self.routine_tree.selection_set(rows[new_index])
            self.routine_tree.focus(rows[new_index])
        self._mark_dirty("Routine order updated (unsaved)")
        logger.info("UI_EVENT: routine_reordered direction=%s index=%s->%s", direction, old_index, new_index)

    def _test_selected_item(self):
        selected = self.routine_tree.selection()
        if len(selected) != 1:
            messagebox.showinfo("Test routine item", "Select exactly one item to test.")
            return
        idx = self._index_from_tree_item(selected[0])
        items = self.routine_store.get_items()
        if not (0 <= idx < len(items)):
            return
        item = items[idx]
        if not is_routine_item_enabled(item):
            messagebox.showinfo("Test routine item", "This item is disabled. Enable it before testing.")
            return
        if self.trigger_item_callback:
            self.trigger_item_callback(item, source="settings_test_item")
            self._set_status(f"Tested item '{item.get('name', 'Unnamed')}'.", level="success")
            if self.root and hasattr(self, "_refresh_launch_history"):
                self.root.after(1200, self._refresh_launch_history)
        else:
            messagebox.showinfo("Info", "Single-item test is not available right now.")

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
        self._update_dashboard_cards()
        self.root.after(1000, self._update_runtime_header)

    def _animate_control_center(self):
        if not self.root or not self.root.winfo_exists():
            return
        snapshot = self._get_runtime_snapshot()
        self._pulse_step = next_animation_step(self._pulse_step, 12)
        self._preview_phase = next_animation_step(self._preview_phase, 12)
        if self.quick_state_label:
            self.quick_state_label.config(foreground=pulse_color(self._pulse_step, active=snapshot.listening_enabled))
        if self.item_editor_canvas and self.item_editor_vars:
            self._refresh_item_editor_preview()
        self.root.after(650, self._animate_control_center)

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

            apply_form_state_to_config(self.config_manager, form_state)
            if sys.platform == "win32":
                self.config_manager.data["system"]["run_on_startup"] = bool(form_state.startup_enabled)
            validate_full_config_data(self.config_manager.data)

            if sys.platform == "win32":
                requested = self.startup_var.get()
                logger.info("UI_EVENT: startup_toggle_requested enabled=%s", requested)
                success, actual = apply_startup_state(requested)
                self.startup_var.set(actual["enabled"])
                self.config_manager.data["system"]["run_on_startup"] = actual["enabled"]
                if not success:
                    raise RuntimeError(f"Failed to set startup to {requested}. Actual state is {actual['enabled']}.")
                validate_full_config_data(self.config_manager.data)

            self.config_manager.save(create_backup=True, backup_reason="ui-save")

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
            if hasattr(self, "_refresh_backup_list"):
                self._refresh_backup_list()
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
        if not hasattr(self, "selected_routine_var"):
            # Guard against partial initialization; caller should retry once routine tab is ready.
            logger.warning("UI_EVENT: reset_form_skipped reason=routine_controls_not_ready")
            self._update_audio_visibility()
            self._sync_slider_labels()
            return

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
            if self.root and hasattr(self, "_refresh_launch_history"):
                self.root.after(1200, self._refresh_launch_history)
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
            if self.root and hasattr(self, "_refresh_launch_history"):
                self.root.after(1200, self._refresh_launch_history)

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

    def _draw_layout_preview(self, canvas, position):
        draw_layout_preview(canvas, position, phase=self._preview_phase)

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
        requested_index = self.config_manager.clap_settings.get("input_device_index")
        try:
            with PYAUDIO_LOCK:
                p = pyaudio.PyAudio()
                if isinstance(requested_index, int):
                    dev = p.get_device_info_by_index(requested_index)
                else:
                    dev = p.get_default_input_device_info()
                name = dev.get("name", "Default")
                idx = dev.get("index")
                p.terminate()
            suffix = f" (index {idx})" if isinstance(idx, int) else ""
            return f"Mic: {name}{suffix}"
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
        if self._dirty:
            should_close = messagebox.askyesno(
                "Discard unsaved changes?",
                "You have unsaved changes. Close the Control Center without applying them?",
                parent=self.root,
            )
            if not should_close:
                self._set_status("Close canceled. Apply or Save to keep changes.", level="warn")
                return
        self._monitoring = False
        SettingsUI._instance = None
        if self.root:
            self.root.destroy()
        logger.info("UI_EVENT: settings_window_closed")
