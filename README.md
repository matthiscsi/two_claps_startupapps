# Jarvis Double-Clap Launcher

A polished Windows background utility that triggers a configurable startup routine upon detecting two claps. Optimized for productivity, it launches your essential apps, websites, and shortcuts, and positions them across your monitors exactly how you like them.

## Key Features

- **Reliable Clap Detection**: Optimized frequency-based detection (1.4kHz-1.8kHz) to minimize false positives.
- **Configurable Startup Routines**: Define multiple routines (e.g., "morning", "work", "gaming") with apps, URLs, and shortcuts.
- **Visual Routine Management**: Easily add, edit, or reorder routine items using a drag-and-drop interface in the Settings UI.
- **Multi-Monitor Support**: Target specific monitors by index or using friendly aliases like `primary` and `secondary`.
- **Flexible Positioning**: Best-effort window placement with support for `full` screen, `left`, `right`, `top`, or `bottom` splitting.
- **Smart Launching**: Detects if an app is already running and repositions it instead of launching a new instance.
- **Robust Validation**: Fail-fast configuration loading with clear, actionable error messages.
- **System Tray Integration**: Runs quietly in the background with manual trigger and settings access.
- **Jarvis Feedback**: Optional Text-to-Speech (TTS) greetings and status updates.

## 🛠️ Configuration (`config.yaml`)

The launcher is powered by a `config.yaml` file. You can manage your routines and settings via the **Settings** menu in the system tray, which provides a visual interface for all options including drag-and-drop reordering of startup items.

### Example Configuration

```yaml
routines:
  morning_routine:
    items:
      - name: "Browser"
        type: "url"
        target: "https://news.google.com"
        monitor: "primary"
        position: "full"
      - name: "Slack"
        type: "app"
        target: "C:/Users/User/AppData/Local/slack/slack.exe"
        monitor: "secondary"
        position: "left"
      - name: "Spotify"
        type: "app"
        target: "spotify"
        monitor: "secondary"
        position: "right"
        delay: 2
```

### Routine Item Options

| Field | Description | Required |
|-------|-------------|----------|
| `name` | Friendly name of the item. Used for window matching. | Yes |
| `type` | `app`, `url`, or `shortcut`. | Yes |
| `target`| Path to executable, URL, or .lnk file. | Yes |
| `monitor`| Monitor index (0, 1) or `primary`/`secondary`. Default: 0 | No |
| `position`| `full`, `left`, or `right`. Default: `full` | No |
| `delay` | Seconds to wait before launching/positioning. Default: 0 | No |
| `window_title_match` | Optional substring to match the window title if `name` is insufficient. | No |

## 💻 Setup & Usage

### Prerequisites
- Windows OS (recommended for window management features)
- Python 3.10+ (if running from source)

### Installation
1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python -m src.main
   ```

### Command Line Arguments
- `--dry-run`: Log actions without actually launching or moving windows.
- `--calibrate`: Enter calibration mode to tune microphone sensitivity.
- `--no-audio`: Disable TTS feedback.
- `--routine <name>`: Specify which routine to run on claps (default: `morning_routine`).

## 📦 Building the Executable

To bundle Jarvis Launcher into a standalone Windows `.exe`:
```bash
python build_exe.py
```
The output will be in the `dist/` directory.

## 🤖 CI / Build Pipeline

This repository uses GitHub Actions for continuous integration and automated builds:

- **CI (`ci.yml`)**: Runs automatically on every push or pull request to `main`. It installs dependencies and runs the automated test suite to ensure code quality.
- **Build Windows Executable (`build-windows.yml`)**: Runs on every push to `main` and can be triggered manually via the **Actions** tab. It produces a standalone `JarvisLauncher.exe`.

### How to download the latest build:
1. Go to the **Actions** tab in this repository.
2. Select the **Build Windows Executable** workflow.
3. Click on the most recent successful run.
4. Scroll down to **Artifacts** and download `JarvisLauncher-Windows`.

## ⚠️ Troubleshooting & Limitations

- **Window Matching**: Some apps take a few seconds to initialize their windows. Use the `delay` field if an app launches but fails to reposition.
- **Permissions**: Some apps may require Administrator privileges to be repositioned if they were launched as Admin.
- **Browsers**: URLs are opened in your default browser. Matching specific browser tabs can be hit-or-miss depending on how the browser handles window titles.

## 🧪 Experimental Features

Legacy features like the AI voice assistant have been moved to the `experimental/` directory and are not part of the core product.
