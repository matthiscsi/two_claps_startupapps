import argparse
import sys
import os
import signal
import time
import logging

from src.config import Config
from src.detector import ClapDetector
from src.launcher import Launcher
from src.audio import AudioEngine
from src.logger import setup_logger

def parse_args():
    parser = argparse.ArgumentParser(description="Double-clap routine launcher (Jarvis style)")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--routine", default="morning_routine", help="Routine to run on double clap")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually launch apps, just log")
    parser.add_argument("--no-audio", action="store_true", help="Disable audio/TTS")
    return parser.parse_args()

def main():
    args = parse_args()

    # Load config
    config = Config(args.config)

    # Override audio if requested
    if args.no_audio:
        config.data["audio_settings"]["enabled"] = False

    # Setup logging
    log_settings = config.get("logging", {})
    logger = setup_logger(
        level=getattr(logging, log_settings.get("level", "INFO")),
        log_file=log_settings.get("file")
    )

    logger.info("Initializing Jarvis Launcher...")

    audio = AudioEngine(config)
    launcher = Launcher(config, dry_run=args.dry_run)
    detector = ClapDetector(config)

    def on_double_clap():
        logger.info("Triggering routine...")
        audio.play_startup()
        launcher.launch_routine(args.routine)
        audio.play_success()
        return False # Keep listening

    # Handle graceful exit
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(f"System ready. Routine '{args.routine}' will trigger on double clap.")
    if args.dry_run:
        logger.info("RUNNING IN DRY-RUN MODE")

    try:
        detector.listen_for_double_clap(callback=on_double_clap)
    except Exception as e:
        logger.error(f"Fatal error in detector: {e}")
        if args.dry_run:
            logger.info("Dry-run: Simulating clap detection since audio might be unavailable.")
            while True:
                time.sleep(10)
                on_double_clap()
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()
