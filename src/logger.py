import logging
import sys
import os

def setup_logger(level=logging.INFO, log_file=None):
    logger = logging.getLogger()
    logger.setLevel(level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler
    if log_file:
        # On Windows, put logs in APPDATA if they are just a filename
        if not os.path.isabs(log_file) and sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            if appdata:
                log_dir = os.path.join(appdata, "JarvisLauncher")
                os.makedirs(log_dir, exist_ok=True)
                log_file = os.path.join(log_dir, log_file)

        try:
            fh = logging.FileHandler(log_file)
            fh.setFormatter(formatter)
            logger.addHandler(fh)
            print(f"Logging to: {log_file}")
        except Exception as e:
            print(f"Failed to setup file logging: {e}")

    return logger
