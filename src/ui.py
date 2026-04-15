import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import logging
import sys
import os
import re
from screeninfo import get_monitors
from src.config import get_resource_path

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

        self.threshold_var = tk.DoubleVar(value=self.config_manager.clap_settings.get('threshold', 0.2))
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
        ttk.Entry(self.file_frame, textvariable=self.audio_file_var).pack(side='left', expand=True, fill='x', padx=5)

        def browse_audio():
            f = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav *.ogg"), ("All files", "*.*")])
            if f:
                self.audio_file_var.set(f)

        ttk.Button(self.file_frame, text="...", width=3, command=browse_audio).pack(side='left', padx=2)

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

        ttk.Button(self.file_frame, text="Test", command=test_audio).pack(side='left', padx=2)

        # Startup Phrase frame
        self.phrase_frame = ttk.Frame(audio_frame)
        self.phrase_frame.pack(fill='x', padx=5, pady=5)
        self.startup_phrase_var = tk.StringVar(value=self.config_manager.audio_settings.get('startup_phrase', ''))
        ttk.Label(self.phrase_frame, text="Startup Phrase:").pack(anchor='w', padx=5)
        ttk.Entry(self.phrase_frame, textvariable=self.startup_phrase_var).pack(fill='x', padx=5, pady=5)

        def update_visibility(*args):
            if self.audio_mode_var.get() == "tts":
                self.phrase_frame.pack(fill='x', padx=5, pady=5)
                # Keep file frame for "Test" but maybe hide or grey out?
                # Better show file frame only for "file" mode, or both.
            else:
                self.phrase_frame.pack_forget()

        self.audio_mode_var.trace_add("write", update_visibility)
        update_visibility()

    def _create_routines_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Morning Routine")

        self.routine_tree = ttk.Treeview(tab, columns=('Type', 'Path', 'Monitor', 'Position'), show='headings')
        self.routine_tree.heading('Type', text='Type')
        self.routine_tree.heading('Path', text='Path')
        self.routine_tree.heading('Monitor', text='Monitor')
        self.routine_tree.heading('Position', text='Position')
        self.routine_tree.pack(expand=True, fill='both', padx=5, pady=5)

        # Drag and Drop support
        self.routine_tree.bind("<ButtonPress-1>", self._on_tree_click)
        self.routine_tree.bind("<B1-Motion>", self._on_tree_drag)
        self.routine_tree.bind("<ButtonRelease-1>", self._on_tree_release)
        self._drag_data = {"item": None}

        # Track which routine is currently selected for editing
        self.current_routine_name = "morning_routine"

        self._refresh_routine_list()

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(btn_frame, text="Add Shortcut", command=self._add_routine_item).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Edit Item", command=self._edit_routine_item).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Remove Item", command=self._remove_routine_item).pack(side='left', padx=2)

    def _refresh_routine_list(self):
        for item in self.routine_tree.get_children():
            self.routine_tree.delete(item)

        routine_data = self.config_manager.routines.get(self.current_routine_name, {})
        items = routine_data.get('items', [])
        for i, item in enumerate(items):
            # Use name and index as a unique tag to avoid issues with duplicate names
            tag = f"{item.get('name')}||{i}"
            self.routine_tree.insert('', 'end', values=(
                item.get('type'),
                item.get('target'),
                item.get('monitor'),
                item.get('position')
            ), tags=(tag,))

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
        if not self._monitoring or not self.root or not self.detector:
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
        item = self.routine_tree.identify_row(event.y)
        if item:
            self._drag_data["item"] = item

    def _on_tree_drag(self, event):
        if not self._drag_data["item"]:
            return

        target = self.routine_tree.identify_row(event.y)
        if target and target != self._drag_data["item"]:
            self.routine_tree.move(self._drag_data["item"], '', self.routine_tree.index(target))

    def _on_tree_release(self, event):
        self._drag_data["item"] = None

    def _save_settings(self):
        try:
            self.config_manager.data['clap_settings']['threshold'] = self.threshold_var.get()
            self.config_manager.data['clap_settings']['min_interval'] = self.min_interval_var.get()
            self.config_manager.data['audio_settings']['enabled'] = self.audio_enabled_var.get()
            self.config_manager.data['audio_settings']['mode'] = self.audio_mode_var.get()
            self.config_manager.data['audio_settings']['file_path'] = self.audio_file_var.get()
            self.config_manager.data['audio_settings']['startup_phrase'] = self.startup_phrase_var.get()

            # Persist routine order from Treeview
            new_items = []
            routine_data = self.config_manager.routines.get(self.current_routine_name, {})
            old_items = routine_data.get('items', [])

            for item_id in self.routine_tree.get_children():
                tags = self.routine_tree.item(item_id, 'tags')
                if not tags: continue
                # format: name||index
                tag = tags[0]
                try:
                    name, idx_str = tag.rsplit("||", 1)
                    idx = int(idx_str)
                    if idx < len(old_items):
                        new_items.append(old_items[idx])
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse tag for reordering: {tag}")

            if new_items or not self.routine_tree.get_children():
                self.config_manager.routines[self.current_routine_name]['items'] = new_items

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
