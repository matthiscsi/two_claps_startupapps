# 👏 Jarvis Double-Clap Launcher

A polished Windows background utility that triggers a "morning routine" upon detecting two claps. Inspired by Tony Stark's Jarvis, it opens your essential apps, positions them across your monitors, and greets you with a wake-up message.

## Features

- **Reliable Clap Detection**: Optimized frequency-based detection.
- **Configurable Routines**: Define apps, URLs, and target monitors in a simple YAML file.
- **Window Management**: Best-effort positioning of Discord, Spotify, and browser windows.
- **Jarvis Feedback**: Optional TTS (Text-to-Speech) for a premium feel.
- **Background Mode**: Low resource usage, runs quietly in the system tray (or as a background process).
- **Portable**: Can be bundled into a single `.exe` for easy use.

## Quick Start (Bundled Version)

1. Download the latest `JarvisLauncher.exe` from releases.
2. Run it once to generate the default `config.yaml`.
3. Edit `config.yaml` to match your monitor setup and app paths.
4. Restart the app. Clap twice. Enjoy.

## Configuration (`config.yaml`)

```yaml
routines:
  morning_routine:
    - name: "HLN News"
      type: "url"
      path: "https://www.hln.be/"
      monitor: 0  # 0 is main, 1 is secondary
    - name: "Discord"
      type: "app"
      path: "discord"
      monitor: 1
      delay: 2
```

## Setup (Development Mode)

1. **Install Python 3.10+**
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run**:
   ```bash
   python -m src.main
   ```
   Use `--dry-run` to test your routine without actually opening anything.

## Background Usage & Startup on Boot

### Manual Background Run
Use `pythonw.exe` on Windows to run without a console window:
```bash
start /b pythonw -m src.main
```

### Run on Boot
1. Press `Win + R`, type `shell:startup`, and hit Enter.
2. Create a shortcut to `JarvisLauncher.exe` (or a `.bat` file for the Python version) in this folder.
3. Windows will now start the launcher automatically when you log in.

## Troubleshooting

- **Sensitivity**: Adjust `threshold` and `min_interval` in `config.yaml` if claps aren't detected or there are false positives.
- **Window Positioning**: Some apps (like Discord) take time to load. Increase the `delay` in `config.yaml` to ensure the window is ready before the launcher tries to move it.
- **Audio**: Ensure your default playback device is set correctly for TTS feedback.

## Limitations

- Precise window placement for browsers can be tricky if multiple windows are open.
- App "names" in config should match the window title (or a part of it) for reliable positioning.
