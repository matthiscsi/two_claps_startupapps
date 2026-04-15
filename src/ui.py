import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import logging
import sys
import os
import re
from screeninfo import get_monitors
from src.config import get_resource_path
from src.startup_helper import is_startup_enabled, set_startup
from src.logger import get_log_dir

logger = logging.getLogger(__name__)

try:
    import pyaudio
except ImportError:
    pyaudio = None

class SettingsUI:
    _instance = None

    def __init__(self, config_manager, on_save_callback=None, detector=None):
        self.config_manager = config_manager
        self.on_save_callback = on_save_callback
        self.detector = detector
        self.root = None
        self.meter_canvas = None
        self._monitoring = False

    def open(self):
        if SettingsUI._instance:
            try:
                SettingsUI._instance.deiconify()
                SettingsUI._instance.lift()
                SettingsUI._instance.focus_force()
            except:
                SettingsUI._instance = None
            if SettingsUI._instance:
                return

        try:
            logger.info("Initializing Settings UI window...")
            self.root = tk.Tk()
            SettingsUI._instance = self.root
            self.root.title("Jarvis Launcher Settings")
            icon_path = get_resource_path(os.path.join("assets", "icon.ico"))
            if os.path.exists(icon_path):
                try:
                    self.root.iconbitmap(icon_path)
                except:
                    pass
            self.root.geometry("600x500")

            # Ensure instance is cleared when window is closed
            def on_closing():
                self._monitoring = False
                SettingsUI._instance = None
                self.root.destroy()

            self.root.protocol("WM_DELETE_WINDOW", on_closing)

            self.style = ttk.Style()
            # Use a custom style to avoid affecting all Treeview widgets
            self.style.configure("Routine.Treeview", rowheight=30)

            self.notebook = ttk.Notebook(self.root)
            self.notebook.pack(expand=True, fill='both', padx=15, pady=15)

            self._create_general_tab()
            self._create_routines_tab()

            btn_frame = ttk.Frame(self.root)
            btn_frame.pack(fill='x', padx=10, pady=10)

            ttk.Button(btn_frame, text="Save", command=self._save_settings).pack(side='right', padx=5)
            ttk.Button(btn_frame, text="Cancel", command=on_closing).pack(side='right', padx=5)

            logger.info("Starting Tkinter mainloop...")
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Failed to open Settings UI: {e}", exc_info=True)
            SettingsUI._instance = None
            if self.root:
                try: self.root.destroy()
                except: pass

    def _create_general_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="General")

        # Clap Settings
        clap_frame = ttk.LabelFrame(tab, text="Clap Detection")
        clap_frame.pack(fill='x', padx=10, pady=5)

        self.threshold_var = tk.DoubleVar(value=self.config_manager.clap_settings.get('threshold', 0.15))
        ttk.Label(clap_frame, text="Threshold:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ttk.Entry(clap_frame, textvariable=self.threshold_var).grid(row=0, column=1, padx=5, pady=5)

        self.min_interval_var = tk.DoubleVar(value=self.config_manager.clap_settings.get('min_interval', 0.2))
        ttk.Label(clap_frame, text="Min Interval (s):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        ttk.Entry(clap_frame, textvariable=self.min_interval_var).grid(row=1, column=1, padx=5, pady=5)

        # Device Selection (Simplified)
        if pyaudio:
            try:
                p = pyaudio.PyAudio()
                dev = p.get_default_input_device_info()
                dev_name = dev.get('name', 'Default')
                p.terminate()
                device_text = f"Mic: {dev_name}"
            except:
                device_text = "Mic: Default system microphone"
            ttk.Label(clap_frame, text=device_text, font=('', 8, 'italic')).grid(row=2, column=0, columnspan=2, padx=5, pady=2)
        else:
            ttk.Label(clap_frame, text="Note: PyAudio not detected. Detection may be limited.", foreground="red").grid(row=2, column=0, columnspan=2, padx=5, pady=5)

        # Microphone Level Meter
        meter_frame = ttk.Frame(clap_frame)
        meter_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=10, sticky='ew')

        ttk.Label(meter_frame, text="Mic Level:").pack(side='left', padx=5)
        self.meter_canvas = tk.Canvas(meter_frame, width=200, height=20, bg='#222')
        self.meter_canvas.pack(side='left', expand=True, fill='x', padx=5)

        self.state_label = ttk.Label(meter_frame, text="IDLE", width=10)
        self.state_label.pack(side='left', padx=5)

        if self.detector:
            self._monitoring = True
            self.root.after(100, self._update_meter)

        # Audio Settings
        audio_frame = ttk.LabelFrame(tab, text="Audio / TTS")
        audio_frame.pack(fill='x', padx=10, pady=5)

        self.audio_enabled_var = tk.BooleanVar(value=self.config_manager.audio_settings.get('enabled', False))
        ttk.Checkbutton(audio_frame, text="Enable Jarvis Feedback", variable=self.audio_enabled_var).pack(anchor='w', padx=5, pady=5)

        mode_frame = ttk.Frame(audio_frame)
        mode_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(mode_frame, text="Mode:").pack(side='left', padx=5)
        self.audio_mode_var = tk.StringVar(value=self.config_manager.audio_settings.get('mode', 'tts'))
        ttk.Radiobutton(mode_frame, text="TTS", variable=self.audio_mode_var, value="tts").pack(side='left', padx=5)
        ttk.Radiobutton(mode_frame, text="Audio File", variable=self.audio_mode_var, value="file").pack(side='left', padx=5)

        # File selection frame
        self.file_frame = ttk.Frame(audio_frame)
        self.file_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(self.file_frame, text="File:").pack(side='left', padx=5)
        self.audio_file_var = tk.StringVar(value=self.config_manager.audio_settings.get('file_path', ''))
        self.audio_file_entry = ttk.Entry(self.file_frame, textvariable=self.audio_file_var)
        self.audio_file_entry.pack(side='left', expand=True, fill='x', padx=5)

        def browse_audio():
            f = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav *.ogg"), ("All files", "*.*")])
            if f:
                self.audio_file_var.set(f)

        self.audio_browse_btn = ttk.Button(self.file_frame, text="...", width=3, command=browse_audio)
        self.audio_browse_btn.pack(side='left', padx=2)

        def test_audio():
            # Temporarily enable if disabled for testing
            old_enabled = self.config_manager.audio_settings.get('enabled')
            old_mode = self.config_manager.audio_settings.get('mode')
            old_file = self.config_manager.audio_settings.get('file_path')

            self.config_manager.audio_settings['enabled'] = True
            self.config_manager.audio_settings['mode'] = self.audio_mode_var.get()
            self.config_manager.audio_settings['file_path'] = self.audio_file_var.get()

            # Use a dummy detector if needed or just initialize engine
            from src.audio import AudioEngine
            temp_engine = AudioEngine(self.config_manager)
            temp_engine.enabled = True
            temp_engine.maybe_initialize()

            if self.audio_mode_var.get() == "tts":
                temp_engine.speak(self.startup_phrase_var.get())
            else:
                temp_engine.play_file(self.audio_file_var.get())

            # Restore
            self.config_manager.audio_settings['enabled'] = old_enabled
            self.config_manager.audio_settings['mode'] = old_mode
            self.config_manager.audio_settings['file_path'] = old_file

        self.audio_test_btn = ttk.Button(self.file_frame, text="Test", command=test_audio)
        self.audio_test_btn.pack(side='left', padx=2)

        # Startup Phrase frame
        self.phrase_frame = ttk.Frame(audio_frame)
        self.phrase_frame.pack(fill='x', padx=5, pady=5)
        self.startup_phrase_var = tk.StringVar(value=self.config_manager.audio_settings.get('startup_phrase', ''))
        ttk.Label(self.phrase_frame, text="Startup Phrase:").pack(anchor='w', padx=5)
        ttk.Entry(self.phrase_frame, textvariable=self.startup_phrase_var).pack(fill='x', padx=5, pady=5)

        def update_visibility(*args):
            is_enabled = self.audio_enabled_var.get()
            mode = self.audio_mode_var.get()

            if mode == "tts":
                self.phrase_frame.pack(fill='x', padx=5, pady=5)
            else:
                self.phrase_frame.pack_forget()

            # Enable/disable file controls based on mode and overall enabled state
            if is_enabled and mode == "file":
                self.audio_file_entry.state(['!disabled'])
                self.audio_browse_btn.state(['!disabled'])
                # Test button should probably work if enabled, but specifically for file mode here
            else:
                self.audio_file_entry.state(['disabled'])
                self.audio_browse_btn.state(['disabled'])

            # Test button and phrase field also depend on enabled state
            if is_enabled:
                self.audio_test_btn.state(['!disabled'])
                # Phrase field only if TTS
                # We don't have a ref to the phrase entry, but it's okay for now
            else:
                self.audio_test_btn.state(['disabled'])

        self.audio_mode_var.trace_add("write", update_visibility)
        self.audio_enabled_var.trace_add("write", update_visibility)
        update_visibility()

        # System Settings
        system_frame = ttk.LabelFrame(tab, text="System")
        system_frame.pack(fill='x', padx=10, pady=5)

        if sys.platform == "win32":
            self.startup_var = tk.BooleanVar(value=is_startup_enabled())
            ttk.Checkbutton(system_frame, text="Run on Windows startup", variable=self.startup_var).pack(anchor='w', padx=5, pady=5)

        # Logs Folder
        def open_logs():
            log_dir = get_log_dir()
            if os.path.exists(log_dir):
                if sys.platform == "win32":
                    os.startfile(log_dir)
                else:
                    import subprocess
                    subprocess.Popen(['xdg-open', log_dir])
            else:
                messagebox.showinfo("Information", f"Log directory does not exist yet: {log_dir}")

        ttk.Button(system_frame, text="Open Logs Folder", command=open_logs).pack(anchor='w', padx=5, pady=5)

    def _create_routines_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Morning Routine")

        helper_label = ttk.Label(tab, text="Drag items using the ☰ handle to reorder startup sequence", font=('', 9, 'italic'), foreground='#666')
        helper_label.pack(anchor='w', padx=10, pady=(10, 2))

        tree_frame = ttk.Frame(tab)
        tree_frame.pack(expand=True, fill='both', padx=10, pady=5)

        self.routine_tree = ttk.Treeview(tree_frame, columns=('Handle', 'Type', 'Path', 'Monitor', 'Position'), show='headings', style="Routine.Treeview")
        self.routine_tree.tag_configure('dragging', background='#e1f5fe')

        self.routine_tree.heading('Handle', text='')
        self.routine_tree.column('Handle', width=40, anchor='center', stretch=False)

        self.routine_tree.heading('Type', text='Type')
        self.routine_tree.column('Type', width=80)

        self.routine_tree.heading('Path', text='Path')

        self.routine_tree.heading('Monitor', text='Monitor')
        self.routine_tree.column('Monitor', width=80)

        self.routine_tree.heading('Position', text='Position')
        self.routine_tree.column('Position', width=80)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.routine_tree.yview)
        self.routine_tree.configure(yscrollcommand=scrollbar.set)

        self.routine_tree.pack(side='left', expand=True, fill='both')
        scrollbar.pack(side='right', fill='y')

        # Drag and Drop support
        self.routine_tree.bind("<ButtonPress-1>", self._on_tree_click)
        self.routine_tree.bind("<B1-Motion>", self._on_tree_drag)
        self.routine_tree.bind("<ButtonRelease-1>", self._on_tree_release)
        self.routine_tree.bind("<Motion>", self._on_tree_motion)
        self.routine_tree.bind("<Leave>", lambda e: self.routine_tree.config(cursor=""))
        self._drag_data = {"item": None, "dragged": False}

        # Track which routine is currently selected for editing
        self.current_routine_name = "morning_routine"

        self._refresh_routine_list()

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill='x', padx=10, pady=(5, 15))
        ttk.Button(btn_frame, text="Add Shortcut", command=self._add_routine_item).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Edit Item", command=self._edit_routine_item).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Remove Item", command=self._remove_routine_item).pack(side='left', padx=5)

    def _refresh_routine_list(self):
        # Store current selection to restore it after refresh
        selected_indices = []
        for item_id in self.routine_tree.selection():
            selected_indices.append(self.routine_tree.index(item_id))

        for item in self.routine_tree.get_children():
            self.routine_tree.delete(item)

        routine_data = self.config_manager.routines.get(self.current_routine_name, {})
        items = routine_data.get('items', [])
        for i, item in enumerate(items):
            # Use name and index as a unique tag to avoid issues with duplicate names
            tag = f"{item.get('name')}||{i}"
            item_id = self.routine_tree.insert('', 'end', values=(
                "☰",
                item.get('type'),
                item.get('target'),
                item.get('monitor'),
                item.get('position')
            ), tags=(tag,))

            if i in selected_indices:
                self.routine_tree.selection_add(item_id)

    def _edit_routine_item(self):
        selected = self.routine_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an item to edit.")
            return

        item_id = selected[0]
        tags = self.routine_tree.item(item_id, 'tags')
        if not tags: return

        try:
            # Extract the original index from the tag (name||index)
            _, idx_str = tags[0].rsplit("||", 1)
            idx = int(idx_str)
        except (ValueError, IndexError):
            # Fallback to visual index if tag is broken
            idx = self.routine_tree.index(item_id)

        routine_data = self.config_manager.routines.get(self.current_routine_name, {})
        items = routine_data.get('items', [])

        if 0 <= idx < len(items):
            self._add_routine_item(edit_index=idx)

    def _add_routine_item(self, edit_index=None):
        dialog = tk.Toplevel(self.root)
        is_edit = edit_index is not None
        dialog.title("Edit Shortcut" if is_edit else "Add Shortcut")
        dialog.geometry("400x350")

        routine_data = self.config_manager.routines.get(self.current_routine_name, {"items": []})
        old_item = routine_data['items'][edit_index] if is_edit else {}

        ttk.Label(dialog, text="Name:").grid(row=0, column=0, padx=5, pady=5, sticky='e')
        name_var = tk.StringVar(value=old_item.get('name', ''))
        ttk.Entry(dialog, textvariable=name_var).grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(dialog, text="Type:").grid(row=1, column=0, padx=5, pady=5, sticky='e')
        type_var = tk.StringVar(value=old_item.get('type', 'app'))
        type_combo = ttk.Combobox(dialog, textvariable=type_var, values=["app", "url", "shortcut"], state="readonly")
        type_combo.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(dialog, text="Target:").grid(row=2, column=0, padx=5, pady=5, sticky='e')
        target_frame = ttk.Frame(dialog)
        target_frame.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        target_var = tk.StringVar(value=old_item.get('target', ''))
        ttk.Entry(target_frame, textvariable=target_var).pack(side='left', expand=True, fill='x')

        def browse_target():
            file_path = filedialog.askopenfilename()
            if file_path:
                target_var.set(file_path)
                if not name_var.get():
                    name_var.set(os.path.basename(file_path).split('.')[0])

        browse_btn = ttk.Button(target_frame, text="...", width=3, command=browse_target)
        browse_btn.pack(side='right', padx=2)

        # Update browse button visibility based on type
        def on_type_change(event):
            if type_var.get() == "url":
                browse_btn.state(['disabled'])
            else:
                browse_btn.state(['!disabled'])
        type_combo.bind("<<ComboboxSelected>>", on_type_change)

        ttk.Label(dialog, text="Monitor:").grid(row=3, column=0, padx=5, pady=5, sticky='e')

        from src.launcher import Launcher
        monitor_options = Launcher.get_monitor_options()

        monitor_var = tk.StringVar()
        # Find default selection
        selected_option = monitor_options[0]

        current_monitor = old_item.get('monitor')
        if current_monitor is not None:
             # Try to find the matching option
             for opt in monitor_options:
                 if opt.startswith(f"Monitor {current_monitor}:"):
                     selected_option = opt
                     break
        else:
            for opt in monitor_options:
                if "(Primary)" in opt:
                    selected_option = opt
                    break

        monitor_var.set(selected_option)
        monitor_combo = ttk.Combobox(dialog, textvariable=monitor_var, values=monitor_options, state="readonly")
        monitor_combo.grid(row=3, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(dialog, text="Position:").grid(row=4, column=0, padx=5, pady=5, sticky='e')
        pos_var = tk.StringVar(value=old_item.get('position', 'full'))
        ttk.Combobox(dialog, textvariable=pos_var, values=["full", "left", "right", "top", "bottom"], state="readonly").grid(row=4, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(dialog, text="Icon Path:").grid(row=5, column=0, padx=5, pady=5, sticky='e')
        icon_frame = ttk.Frame(dialog)
        icon_frame.grid(row=5, column=1, padx=5, pady=5, sticky='ew')
        icon_var = tk.StringVar(value=old_item.get('icon', ''))
        ttk.Entry(icon_frame, textvariable=icon_var).pack(side='left', expand=True, fill='x')

        def browse_icon():
            icon_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.ico"), ("All files", "*.*")])
            if icon_path:
                icon_var.set(icon_path)

        ttk.Button(icon_frame, text="...", width=3, command=browse_icon).pack(side='right', padx=2)

        ttk.Label(dialog, text="Delay before launch (s):").grid(row=6, column=0, padx=5, pady=5, sticky='e')
        delay_var = tk.DoubleVar(value=old_item.get('delay', 0.0))
        ttk.Entry(dialog, textvariable=delay_var).grid(row=6, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(dialog, text="CLI Arguments (optional):").grid(row=7, column=0, padx=5, pady=5, sticky='e')
        args_var = tk.StringVar(value=old_item.get('args', ''))
        ttk.Entry(dialog, textvariable=args_var).grid(row=7, column=1, padx=5, pady=5, sticky='ew')

        dialog.columnconfigure(1, weight=1)

        def save_item():
            # Validate
            name = name_var.get().strip()
            target = target_var.get().strip()
            item_type = type_var.get()

            if not name:
                messagebox.showerror("Error", "Name is required.")
                return
            if not target:
                messagebox.showerror("Error", "Target is required.")
                return

            if item_type == "url" and not re.match(r'^https?://', target):
                 if not messagebox.askyesno("Warning", "URL does not start with http:// or https://. Save anyway?"):
                     return
            elif item_type in ["app", "shortcut"] and not os.path.exists(target):
                 # Some special cases like 'discord' might not be full paths
                 if target.lower() not in ["discord", "spotify"] and not os.path.exists(target):
                    if not messagebox.askyesno("Warning", f"Path '{target}' does not seem to exist. Save anyway?"):
                        return

            # Extract monitor index from label (e.g. "Monitor 0: ...")
            monitor_val = monitor_var.get()
            if monitor_val.startswith("Monitor "):
                try:
                    # Extracts '0' from 'Monitor 0: ...'
                    monitor_val = int(monitor_val.split(":")[0].split(" ")[1])
                except (IndexError, ValueError):
                    monitor_val = 0
            else:
                # Fallback for primary/secondary strings if they somehow remain
                try:
                    monitor_val = int(monitor_val)
                except ValueError:
                    pass

            new_item = {
                "name": name,
                "type": item_type,
                "target": target,
                "args": args_var.get().strip(),
                "monitor": monitor_val,
                "position": pos_var.get(),
                "delay": delay_var.get(),
                "icon": icon_var.get().strip()
            }
            routine_data = self.config_manager.routines.setdefault(self.current_routine_name, {"items": []})
            if "items" not in routine_data:
                routine_data["items"] = []

            if is_edit:
                logger.info(f"Updating routine item {edit_index}: {new_item['name']}")
                routine_data["items"][edit_index] = new_item
            else:
                logger.info(f"Adding new routine item: {new_item['name']}")
                routine_data["items"].append(new_item)

            self._refresh_routine_list()
            dialog.destroy()

        ttk.Button(dialog, text="Save" if is_edit else "Add", command=save_item).grid(row=8, columnspan=2, pady=10)

    def _remove_routine_item(self):
        selected = self.routine_tree.selection()
        if not selected: return

        routine_data = self.config_manager.routines.get(self.current_routine_name, {})
        items = routine_data.get('items', [])

        for item_id in selected:
            idx = self.routine_tree.index(item_id)
            if idx < len(items):
                del items[idx]

        self._refresh_routine_list()

    def _update_meter(self):
        if not self._monitoring or not self.root:
            return

        if not self.detector:
            self.state_label.config(text="NO DETECTOR", foreground="red")
            return

        try:
            peak = getattr(self.detector, 'last_peak', 0.0)
            threshold = self.threshold_var.get()
            state = getattr(self.detector, 'state', 'IDLE')
            clap_count = getattr(self.detector, 'clap_count', 0)

            # Clear and redraw
            self.meter_canvas.delete("all")

            # Draw background level
            width = self.meter_canvas.winfo_width()
            level_width = min(width, int(peak * width))
            color = "#00ff00" if peak < threshold else "#ffff00"
            if peak > 0.8: color = "#ff0000"

            self.meter_canvas.create_rectangle(0, 0, level_width, 20, fill=color, outline="")

            # Draw threshold line
            thresh_x = int(threshold * width)
            self.meter_canvas.create_line(thresh_x, 0, thresh_x, 20, fill="white", width=2)

            # Update state label
            status_text = f"{state}"
            if clap_count > 0:
                status_text += f" ({clap_count})"
            self.state_label.config(text=status_text)

            # Flash if clap detected
            if clap_count > 0:
                 self.state_label.config(foreground="orange")
            else:
                 self.state_label.config(foreground="")

        except Exception as e:
            logger.debug(f"Meter update failed: {e}")

        if self._monitoring:
            self.root.after(50, self._update_meter)

    def _on_tree_click(self, event):
        column = self.routine_tree.identify_column(event.x)
        item = self.routine_tree.identify_row(event.y)

        # Only allow dragging from the 'Handle' column (#1)
        if item and column == '#1':
            self._drag_data["item"] = item
            self._drag_data["dragged"] = False
            # Add visual feedback
            self.routine_tree.item(item, tags=self.routine_tree.item(item, "tags") + ("dragging",))

    def _on_tree_drag(self, event):
        if not self._drag_data["item"]:
            return

        self._drag_data["dragged"] = True
        target = self.routine_tree.identify_row(event.y)
        if target and target != self._drag_data["item"]:
            self.routine_tree.move(self._drag_data["item"], '', self.routine_tree.index(target))

    def _on_tree_motion(self, event):
        column = self.routine_tree.identify_column(event.x)
        if column == '#1':
            self.routine_tree.config(cursor="fleur")
        else:
            self.routine_tree.config(cursor="")

    def _on_tree_release(self, event):
        item = self._drag_data.get("item")
        dragged = self._drag_data.get("dragged")

        if item:
            # Remove visual feedback
            tags = list(self.routine_tree.item(item, "tags"))
            if "dragging" in tags:
                tags.remove("dragging")
            self.routine_tree.item(item, tags=tuple(tags))

        self._drag_data["item"] = None
        self._drag_data["dragged"] = False

        if not dragged:
            return

        # Persist the new order to the config manager immediately
        new_items = []
        routine_data = self.config_manager.routines.get(self.current_routine_name, {})
        old_items = routine_data.get('items', [])

        for item_id in self.routine_tree.get_children():
            tags = self.routine_tree.item(item_id, 'tags')
            if not tags: continue

            # Find the identifier tag (contains '||')
            id_tag = None
            for t in tags:
                if "||" in t:
                    id_tag = t
                    break

            if not id_tag:
                continue

            try:
                # name||index
                _, idx_str = id_tag.rsplit("||", 1)
                idx = int(idx_str)
                if idx < len(old_items):
                    new_items.append(old_items[idx])
            except (ValueError, IndexError):
                logger.warning(f"Could not parse tag during reorder: {id_tag}")

        if new_items or not self.routine_tree.get_children():
            logger.info(f"Updating routine '{self.current_routine_name}' order.")
            self.config_manager.routines[self.current_routine_name]['items'] = new_items
            # Refresh to update the tags (indices) to match the new order
            self._refresh_routine_list()

    def _save_settings(self):
        try:
            self.config_manager.data['clap_settings']['threshold'] = self.threshold_var.get()
            self.config_manager.data['clap_settings']['min_interval'] = self.min_interval_var.get()
            self.config_manager.data['audio_settings']['enabled'] = self.audio_enabled_var.get()
            self.config_manager.data['audio_settings']['mode'] = self.audio_mode_var.get()
            self.config_manager.data['audio_settings']['file_path'] = self.audio_file_var.get()
            self.config_manager.data['audio_settings']['startup_phrase'] = self.startup_phrase_var.get()

            # Update startup setting
            if sys.platform == "win32" and hasattr(self, 'startup_var'):
                set_startup(self.startup_var.get())

            self.config_manager.save()
            logger.info("Settings saved to config file.")
            if self.on_save_callback:
                self.on_save_callback()
            messagebox.showinfo("Success", "Settings saved successfully!")
            SettingsUI._instance = None
            self.root.destroy()
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")
