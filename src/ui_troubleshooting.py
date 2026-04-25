from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from src.config_backup import create_config_backup, list_config_backups, restore_config_backup
from src.launch_history import (
    clear_launch_history,
    format_launch_history,
    get_launch_history_path,
    read_launch_history,
)
from src.logger import get_log_dir
from src.ui_diagnostics import build_routine_launch_plan, build_troubleshooting_summary, resolve_log_file_path, tail_text_file


class TroubleshootingMixin:
    def _create_troubleshooting_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Troubleshooting")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        from src.ui_layout import ScrollableFrame

        scroller = ScrollableFrame(tab)
        scroller.grid(row=0, column=0, sticky="nsew")
        content = scroller.content

        diag = ttk.LabelFrame(content, text="Diagnostics & Recovery")
        diag.pack(fill="x", padx=10, pady=8)
        ttk.Label(
            diag,
            text="Runtime status, launch evidence, logs, and config recovery live here.",
            style="Hint.TLabel",
        ).pack(anchor="w", padx=8, pady=(8, 4))
        row = ttk.Frame(diag)
        row.pack(fill="x", padx=8, pady=(0, 8))
        self._icon_button(row, icon="logs", text="Open Logs Folder", command=self._open_logs).pack(side="left")
        self._icon_button(row, icon="config", text="Open Config File", command=self._open_config_file).pack(side="left", padx=8)
        self._icon_button(row, icon="copy", text="Copy Summary", command=self._copy_diagnostics).pack(side="left")
        self._icon_button(row, icon="copy", text="Copy Launch Plan", command=self._copy_routine_plan).pack(side="left", padx=8)
        self._icon_button(row, icon="run", text="Run Active Routine", command=self._test_active_routine).pack(side="left", padx=8)
        ttk.Label(diag, text=f"Logs: {get_log_dir()}", style="Hint.TLabel").pack(anchor="w", padx=8, pady=(0, 2))
        ttk.Label(diag, text=f"Config: {self.config_manager.config_path}", style="Hint.TLabel").pack(anchor="w", padx=8, pady=(0, 8))

        self._create_launch_history_section(content)
        self._create_backup_restore_section(content)
        self._create_log_preview_section(content)
        self._create_recovery_hints_section(content)

    def _create_launch_history_section(self, parent):
        history = ttk.LabelFrame(parent, text="Launch History")
        history.pack(fill="both", expand=True, padx=10, pady=8)
        controls = ttk.Frame(history)
        controls.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(controls, text="Status:", style="Hint.TLabel").pack(side="left")
        self.history_status_var = tk.StringVar(value="All")
        status_filter = ttk.Combobox(
            controls,
            textvariable=self.history_status_var,
            values=["All", "success", "skipped", "failure"],
            state="readonly",
            width=12,
        )
        status_filter.pack(side="left", padx=(4, 8))
        status_filter.bind("<<ComboboxSelected>>", lambda _e: self._refresh_launch_history())
        ttk.Button(controls, text="Refresh", style="Secondary.TButton", command=self._refresh_launch_history).pack(side="left")
        ttk.Button(controls, text="Copy", style="Secondary.TButton", command=self._copy_launch_history).pack(side="left", padx=6)
        ttk.Button(controls, text="Clear", style="Secondary.TButton", command=self._clear_launch_history).pack(side="left")
        ttk.Button(controls, text="Open History File", style="Secondary.TButton", command=self._open_history_file).pack(side="right")

        columns = ("time", "status", "routine", "item", "source", "message")
        self.history_tree = ttk.Treeview(history, columns=columns, show="headings", height=7)
        widths = {"time": 145, "status": 80, "routine": 130, "item": 140, "source": 120, "message": 360}
        for col in columns:
            self.history_tree.heading(col, text=col.title())
            self.history_tree.column(col, width=widths[col], anchor="w")
        self.history_tree.tag_configure("success", foreground="#2e7d32")
        self.history_tree.tag_configure("skipped", foreground="#8a6d3b")
        self.history_tree.tag_configure("failure", foreground="#a94442")
        self.history_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._refresh_launch_history()

    def _create_backup_restore_section(self, parent):
        backup = ttk.LabelFrame(parent, text="Config Backups")
        backup.pack(fill="both", expand=True, padx=10, pady=8)
        controls = ttk.Frame(backup)
        controls.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(controls, text="Create Backup Now", style="Secondary.TButton", command=self._create_config_backup_now).pack(side="left")
        ttk.Button(controls, text="Restore Selected", style="Secondary.TButton", command=self._restore_selected_backup).pack(side="left", padx=6)
        ttk.Button(controls, text="Open Backups Folder", style="Secondary.TButton", command=self._open_backups_folder).pack(side="right")

        columns = ("name", "modified", "size")
        self.backup_tree = ttk.Treeview(backup, columns=columns, show="headings", height=5)
        self.backup_tree.heading("name", text="Backup")
        self.backup_tree.heading("modified", text="Modified")
        self.backup_tree.heading("size", text="Size")
        self.backup_tree.column("name", width=340)
        self.backup_tree.column("modified", width=160)
        self.backup_tree.column("size", width=80, anchor="e")
        self.backup_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._refresh_backup_list()

    def _create_log_preview_section(self, parent):
        diag = ttk.LabelFrame(parent, text="Recent Logs")
        diag.pack(fill="both", expand=True, padx=10, pady=8)
        logs_box = ttk.Frame(diag)
        logs_box.pack(fill="both", expand=True, padx=8, pady=(8, 8))
        self.logs_preview = tk.Text(logs_box, height=8, wrap="none", background="#111827", foreground="#e5e7eb")
        self.logs_preview.pack(fill="both", expand=True, pady=(0, 4))
        logs_actions = ttk.Frame(logs_box)
        logs_actions.pack(fill="x")
        ttk.Button(logs_actions, text="Refresh Log Preview", style="Secondary.TButton", command=self._refresh_log_preview).pack(side="left")
        ttk.Button(logs_actions, text="Copy Log Preview", style="Secondary.TButton", command=self._copy_log_preview).pack(side="left", padx=8)
        self._refresh_log_preview()

    def _create_recovery_hints_section(self, parent):
        hints = ttk.LabelFrame(parent, text="Targeted Recovery Hints")
        hints.pack(fill="x", padx=10, pady=8)
        ttk.Label(
            hints,
            text=(
                "Use full executable paths for reliable app launches.\n"
                "Increase wait timeout for slow apps that open but do not position.\n"
                "Use Launch History first, then Recent Logs when a routine behaves unexpectedly.\n"
                "Restore a backup if a config edit makes the Control Center unhappy."
            ),
            justify="left",
            style="Hint.TLabel",
        ).pack(anchor="w", padx=8, pady=8)

    def _resolve_log_file_path(self):
        return resolve_log_file_path(self.config_manager.data)

    def _refresh_log_preview(self):
        if not self.logs_preview:
            return
        log_path = self._resolve_log_file_path()
        contents = tail_text_file(log_path, line_count=80)
        self.logs_preview.config(state="normal")
        self.logs_preview.delete("1.0", "end")
        self.logs_preview.insert("1.0", contents)
        self.logs_preview.config(state="disabled")

    def _copy_log_preview(self):
        if not self.logs_preview:
            return
        text = self.logs_preview.get("1.0", "end").strip()
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._set_status("Log preview copied to clipboard.", level="success")

    def _refresh_launch_history(self):
        if not getattr(self, "history_tree", None):
            return
        for item_id in self.history_tree.get_children():
            self.history_tree.delete(item_id)
        status = self.history_status_var.get() if getattr(self, "history_status_var", None) else "All"
        status_filter = None if status == "All" else status
        entries = read_launch_history(limit=120, status=status_filter)
        for entry in reversed(entries):
            status_value = str(entry.get("status", ""))
            self.history_tree.insert(
                "",
                "end",
                values=(
                    entry.get("timestamp", ""),
                    status_value,
                    entry.get("routine", ""),
                    entry.get("item", ""),
                    entry.get("source", ""),
                    entry.get("message", ""),
                ),
                tags=(status_value,),
            )

    def _copy_launch_history(self):
        status = self.history_status_var.get() if getattr(self, "history_status_var", None) else "All"
        status_filter = None if status == "All" else status
        entries = read_launch_history(limit=120, status=status_filter)
        self.root.clipboard_clear()
        self.root.clipboard_append(format_launch_history(entries))
        self._set_status("Launch history copied to clipboard.", level="success")

    def _clear_launch_history(self):
        if not messagebox.askyesno("Clear Launch History", "Clear local launch history?"):
            return
        clear_launch_history()
        self._refresh_launch_history()
        self._set_status("Launch history cleared.", level="success")

    def _open_history_file(self):
        path = get_launch_history_path()
        if not os.path.exists(path):
            messagebox.showinfo("Launch History", f"Launch history has not been created yet:\n{path}")
            return
        self._open_path(path)

    def _refresh_backup_list(self):
        if not getattr(self, "backup_tree", None):
            return
        for item_id in self.backup_tree.get_children():
            self.backup_tree.delete(item_id)
        for backup in list_config_backups(self.config_manager.config_path):
            self.backup_tree.insert(
                "",
                "end",
                values=(backup["name"], backup["modified"], f"{backup['size']:,} B"),
                tags=(backup["path"],),
            )

    def _selected_backup_path(self):
        selected = self.backup_tree.selection() if getattr(self, "backup_tree", None) else ()
        if len(selected) != 1:
            return None
        tags = self.backup_tree.item(selected[0], "tags")
        return tags[0] if tags else None

    def _create_config_backup_now(self):
        backup_path = create_config_backup(self.config_manager.config_path, reason="manual-ui")
        self._refresh_backup_list()
        if backup_path:
            self._set_status(f"Created backup: {os.path.basename(backup_path)}", level="success")
        else:
            self._set_status("No config file exists yet to back up.", level="warn")

    def _restore_selected_backup(self):
        backup_path = self._selected_backup_path()
        if not backup_path:
            messagebox.showinfo("Restore Backup", "Select one backup to restore.")
            return
        if not messagebox.askyesno("Restore Backup", f"Restore this config backup?\n\n{os.path.basename(backup_path)}"):
            return
        try:
            data = restore_config_backup(self.config_manager.config_path, backup_path)
            self.config_manager.data = data
            self._reset_form_from_config(mark_status=False)
            self._refresh_backup_list()
            self._set_status("Config backup restored.", level="success")
        except Exception as exc:
            messagebox.showerror("Restore Failed", f"Could not restore backup:\n{exc}")

    def _open_logs(self):
        log_dir = get_log_dir()
        if not os.path.exists(log_dir):
            messagebox.showinfo("Information", f"Log directory does not exist yet: {log_dir}")
            return
        self._open_path(log_dir)

    def _open_backups_folder(self):
        from src.config_backup import get_backup_dir

        backup_dir = get_backup_dir(self.config_manager.config_path)
        os.makedirs(backup_dir, exist_ok=True)
        self._open_path(backup_dir)

    def _open_config_file(self):
        config_path = os.path.abspath(self.config_manager.config_path)
        if not os.path.exists(config_path):
            messagebox.showwarning("Config not found", f"Config file does not exist yet:\n{config_path}")
            return
        self._open_path(config_path)

    def _open_path(self, path):
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])

    def _copy_diagnostics(self):
        status = self._get_runtime_status()
        snapshot = self._get_runtime_snapshot()
        startup_enabled = self.startup_var.get() if hasattr(self, "startup_var") else None
        summary = build_troubleshooting_summary(
            snapshot=snapshot,
            status=status,
            threshold=float(self.threshold_var.get()),
            min_interval=float(self.min_interval_var.get()),
            log_dir=get_log_dir(),
            config_path=self.config_manager.config_path,
            startup_enabled=startup_enabled,
        )
        self.root.clipboard_clear()
        self.root.clipboard_append(summary)
        self._set_status("Troubleshooting summary copied to clipboard.", level="success")

    def _copy_routine_plan(self):
        routine_name = self.selected_routine_var.get() or self._get_runtime_snapshot().active_routine
        items = self.config_manager.routines.get(routine_name, {}).get("items", [])
        plan = build_routine_launch_plan(routine_name, items)
        self.root.clipboard_clear()
        self.root.clipboard_append(plan)
        self._set_status("Routine launch plan copied to clipboard.", level="success")
