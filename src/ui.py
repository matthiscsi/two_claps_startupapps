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

    def __init__(self, config_manager, on_save_callback=None):
        self.config_manager = config_manager
        self.on_save_callback = on_save_callback
        self.root = None

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
            ttk.Label(clap_frame, text="Note: Uses default system microphone.").grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        else:
            ttk.Label(clap_frame, text="Note: PyAudio not detected. Detection may be limited.", foreground="red").grid(row=2, column=0, columnspan=2, padx=5, pady=5)

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

        routine = self.config_manager.routines.get('morning_routine', [])
        for item in routine:
            self.routine_tree.insert('', 'end', values=(
                item.get('type'),
                item.get('path'),
                item.get('monitor'),
                item.get('position')
            ), tags=(item.get('name'),))

    def _add_routine_item(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Routine Item")

        ttk.Label(dialog, text="Name:").grid(row=0, column=0, padx=5, pady=2)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(dialog, text="Type (app/url):").grid(row=1, column=0, padx=5, pady=2)
        type_var = tk.StringVar(value="app")
        ttk.Entry(dialog, textvariable=type_var).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(dialog, text="Path:").grid(row=2, column=0, padx=5, pady=2)
        path_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=path_var).grid(row=2, column=1, padx=5, pady=2)

        ttk.Label(dialog, text="Monitor (0, 1...):").grid(row=3, column=0, padx=5, pady=2)
        monitor_var = tk.IntVar(value=0)
        ttk.Entry(dialog, textvariable=monitor_var).grid(row=3, column=1, padx=5, pady=2)

        ttk.Label(dialog, text="Position (full/left/right):").grid(row=4, column=0, padx=5, pady=2)
        pos_var = tk.StringVar(value="full")
        ttk.Entry(dialog, textvariable=pos_var).grid(row=4, column=1, padx=5, pady=2)

        ttk.Label(dialog, text="Delay (s):").grid(row=5, column=0, padx=5, pady=2)
        delay_var = tk.IntVar(value=0)
        ttk.Entry(dialog, textvariable=delay_var).grid(row=5, column=1, padx=5, pady=2)

        def save_item():
            new_item = {
                "name": name_var.get(),
                "type": type_var.get(),
                "path": path_var.get(),
                "monitor": monitor_var.get(),
                "position": pos_var.get(),
                "delay": delay_var.get()
            }
            self.config_manager.routines.setdefault('morning_routine', []).append(new_item)
            self._refresh_routine_list()
            dialog.destroy()

        ttk.Button(dialog, text="Add", command=save_item).grid(row=6, columnspan=2, pady=10)

    def _remove_routine_item(self):
        selected = self.routine_tree.selection()
        if not selected: return

        for item_id in selected:
            idx = self.routine_tree.index(item_id)
            del self.config_manager.routines['morning_routine'][idx]

        self._refresh_routine_list()

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
