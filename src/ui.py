import tkinter as tk
from tkinter import ttk, messagebox
import json
import logging
import sys

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
                SettingsUI._instance.lift()
            except:
                SettingsUI._instance = None
            if SettingsUI._instance:
                return

        try:
            logger.info("Initializing Settings UI window...")
            self.root = tk.Tk()
            SettingsUI._instance = self.root
            self.root.title("Jarvis Launcher Settings")
            self.root.geometry("600x500")

            # Ensure instance is cleared when window is closed
            def on_closing():
                self._monitoring = False
                SettingsUI._instance = None
                self.root.destroy()

            self.root.protocol("WM_DELETE_WINDOW", on_closing)

            self.notebook = ttk.Notebook(self.root)
            self.notebook.pack(expand=True, fill='both', padx=10, pady=10)

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

        self.audio_enabled_var = tk.BooleanVar(value=self.config_manager.audio_settings.get('enabled', True))
        ttk.Checkbutton(audio_frame, text="Enable Jarvis Feedback", variable=self.audio_enabled_var).pack(anchor='w', padx=5, pady=5)

        self.startup_phrase_var = tk.StringVar(value=self.config_manager.audio_settings.get('startup_phrase', ''))
        ttk.Label(audio_frame, text="Startup Phrase:").pack(anchor='w', padx=5)
        ttk.Entry(audio_frame, textvariable=self.startup_phrase_var).pack(fill='x', padx=5, pady=5)

    def _create_routines_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Morning Routine")

        self.routine_tree = ttk.Treeview(tab, columns=('Type', 'Path', 'Monitor', 'Position'), show='headings')
        self.routine_tree.heading('Type', text='Type')
        self.routine_tree.heading('Path', text='Path')
        self.routine_tree.heading('Monitor', text='Monitor')
        self.routine_tree.heading('Position', text='Position')
        self.routine_tree.pack(expand=True, fill='both', padx=5, pady=5)

        self._refresh_routine_list()

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill='x', padx=5, pady=5)
        ttk.Button(btn_frame, text="Add Item", command=self._add_routine_item).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Remove Item", command=self._remove_routine_item).pack(side='left', padx=2)

    def _refresh_routine_list(self):
        for item in self.routine_tree.get_children():
            self.routine_tree.delete(item)

        routine_data = self.config_manager.routines.get('morning_routine', {})
        items = routine_data.get('items', [])
        for item in items:
            self.routine_tree.insert('', 'end', values=(
                item.get('type'),
                item.get('target'),
                item.get('monitor'),
                item.get('position')
            ), tags=(item.get('name'),))

    def _add_routine_item(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Routine Item")

        ttk.Label(dialog, text="Name:").grid(row=0, column=0, padx=5, pady=2)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(dialog, text="Type (app/url/shortcut):").grid(row=1, column=0, padx=5, pady=2)
        type_var = tk.StringVar(value="app")
        ttk.Entry(dialog, textvariable=type_var).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(dialog, text="Target (Path/URL):").grid(row=2, column=0, padx=5, pady=2)
        target_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=target_var).grid(row=2, column=1, padx=5, pady=2)

        ttk.Label(dialog, text="Monitor (0, primary...):").grid(row=3, column=0, padx=5, pady=2)
        monitor_var = tk.StringVar(value="0")
        ttk.Entry(dialog, textvariable=monitor_var).grid(row=3, column=1, padx=5, pady=2)

        ttk.Label(dialog, text="Position (full/left/right):").grid(row=4, column=0, padx=5, pady=2)
        pos_var = tk.StringVar(value="full")
        ttk.Entry(dialog, textvariable=pos_var).grid(row=4, column=1, padx=5, pady=2)

        ttk.Label(dialog, text="Delay (s):").grid(row=5, column=0, padx=5, pady=2)
        delay_var = tk.DoubleVar(value=0.0)
        ttk.Entry(dialog, textvariable=delay_var).grid(row=5, column=1, padx=5, pady=2)

        def save_item():
            # Try to convert monitor to int if it looks like one
            monitor_val = monitor_var.get()
            try:
                monitor_val = int(monitor_val)
            except ValueError:
                pass

            new_item = {
                "name": name_var.get(),
                "type": type_var.get(),
                "target": target_var.get(),
                "monitor": monitor_val,
                "position": pos_var.get(),
                "delay": delay_var.get()
            }
            routine_data = self.config_manager.routines.setdefault('morning_routine', {"items": []})
            if "items" not in routine_data:
                routine_data["items"] = []
            routine_data["items"].append(new_item)
            self._refresh_routine_list()
            dialog.destroy()

        ttk.Button(dialog, text="Add", command=save_item).grid(row=6, columnspan=2, pady=10)

    def _remove_routine_item(self):
        selected = self.routine_tree.selection()
        if not selected: return

        routine_data = self.config_manager.routines.get('morning_routine', {})
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

    def _save_settings(self):
        try:
            self.config_manager.data['clap_settings']['threshold'] = self.threshold_var.get()
            self.config_manager.data['clap_settings']['min_interval'] = self.min_interval_var.get()
            self.config_manager.data['audio_settings']['enabled'] = self.audio_enabled_var.get()
            self.config_manager.data['audio_settings']['startup_phrase'] = self.startup_phrase_var.get()

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
