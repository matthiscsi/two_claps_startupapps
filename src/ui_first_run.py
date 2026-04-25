from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from src.first_run import mark_first_run_completed, should_show_first_run

logger = logging.getLogger(__name__)


class FirstRunMixin:
    def _maybe_show_first_run(self):
        if self._first_run_prompted:
            return
        if not should_show_first_run(self.config_manager.data):
            return
        self._first_run_prompted = True
        self._open_first_run_setup(auto=True)

    def _open_first_run_setup(self, auto=False):
        dialog = tk.Toplevel(self.root)
        dialog.title("Jarvis First-Run Setup")
        dialog.geometry("640x430")
        dialog.minsize(600, 390)
        dialog.transient(self.root)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        header = ttk.Frame(dialog, padding=(12, 12, 12, 4))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        image = self.icons.get("setup_welcome") if self.icons else None
        if image:
            ttk.Label(header, image=image).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
        ttk.Label(header, text="First-Run Setup", style="HeroTitle.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(
            header,
            text="Check the microphone, shape your first routine, and decide whether Jarvis starts with Windows.",
            style="Hint.TLabel",
            wraplength=430,
        ).grid(row=1, column=1, sticky="w")

        body = ttk.Frame(dialog, padding=(12, 6))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        footer = ttk.Frame(dialog, padding=(12, 6, 12, 12))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)

        step_index = tk.IntVar(value=0)
        step_title = tk.StringVar()
        step_body = tk.StringVar()
        action_frame = ttk.Frame(body)
        content = ttk.LabelFrame(body, textvariable=step_title)
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)
        ttk.Label(content, textvariable=step_body, wraplength=560, justify="left").grid(
            row=0, column=0, sticky="nw", padx=12, pady=(12, 8)
        )
        action_frame.grid(row=1, column=0, sticky="ew", padx=12, pady=8)

        progress = ttk.Progressbar(footer, maximum=4, mode="determinate")
        progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        back_btn = ttk.Button(footer, text="Back")
        back_btn.grid(row=0, column=1, padx=4)
        next_btn = ttk.Button(footer, text="Next", style="Primary.TButton")
        next_btn.grid(row=0, column=2, padx=4)
        skip_btn = ttk.Button(footer, text="Skip Setup")
        skip_btn.grid(row=0, column=3, padx=4)

        steps = [
            (
                "1. Microphone Readiness",
                "Jarvis can run from the tray before the detector is ready. This step checks the current runtime state and gives you the calibration path.",
            ),
            (
                "2. Starter Routine",
                "Create or review the routine that should run on a double clap. You can add a first item, then test the active routine from here.",
            ),
            (
                "3. Startup Preference",
                "Choose whether Jarvis should register itself in your Windows user startup list and how long it should wait before accepting triggers.",
            ),
            (
                "4. Finish",
                "Save the setup marker and keep working in the Control Center. You can reopen this setup from Dashboard any time.",
            ),
        ]

        def clear_actions():
            for child in action_frame.winfo_children():
                child.destroy()

        def render():
            idx = step_index.get()
            title, text = steps[idx]
            step_title.set(title)
            progress["value"] = idx + 1
            back_btn.state(["disabled"] if idx == 0 else ["!disabled"])
            next_btn.config(text="Finish Setup" if idx == len(steps) - 1 else "Next")
            clear_actions()
            if idx == 0:
                status = self._get_runtime_status()
                mic_state = "ready" if status.detector_active else "not active yet"
                step_body.set(f"{text}\n\nCurrent microphone stream: {mic_state}.")
                self._icon_button(action_frame, icon="calibrate", text="Start Guided Calibration", command=self._open_guided_calibration).pack(side="left")
            elif idx == 1:
                routine = self.selected_routine_var.get() or "morning_routine"
                item_count = len(self.routine_store.get_items())
                step_body.set(f"{text}\n\nActive routine: {routine} ({item_count} item{'s' if item_count != 1 else ''}).")
                self._icon_button(action_frame, icon="add", text="Add Routine Item", command=self._add_routine_item).pack(side="left")
                self._icon_button(action_frame, icon="run", text="Run Active Routine", command=self._trigger_selected_routine).pack(side="left", padx=8)
            elif idx == 2:
                step_body.set(text)
                if hasattr(self, "startup_var"):
                    ttk.Checkbutton(action_frame, text="Launch Jarvis when Windows starts", variable=self.startup_var).pack(anchor="w")
                ttk.Label(action_frame, textvariable=self.startup_delay_display_var, style="Hint.TLabel").pack(anchor="w", pady=(6, 0))
            else:
                snapshot = self._get_runtime_snapshot()
                step_body.set(
                    f"{text}\n\nRoutine: {snapshot.active_routine}\nRuntime ready: {snapshot.runtime_ready}\nListening enabled: {snapshot.listening_enabled}"
                )

        def finish():
            mark_first_run_completed(self.config_manager.data)
            self._save_settings(close_window=False)
            logger.info("UI_EVENT: first_run_completed auto=%s", auto)
            dialog.destroy()

        def next_step():
            if step_index.get() >= len(steps) - 1:
                finish()
                return
            step_index.set(step_index.get() + 1)
            render()

        def previous_step():
            if step_index.get() <= 0:
                return
            step_index.set(step_index.get() - 1)
            render()

        def skip():
            mark_first_run_completed(self.config_manager.data)
            try:
                self.config_manager.save(create_backup=True, backup_reason="first-run-skip")
                self._mark_clean("First-run setup skipped")
            except Exception:
                logger.warning("UI_EVENT: first_run_skip_save_failed", exc_info=True)
                self._mark_dirty("First-run setup skipped (unsaved)")
            dialog.destroy()

        back_btn.config(command=previous_step)
        next_btn.config(command=next_step)
        skip_btn.config(command=skip)
        render()
