import logging
import sys
import os
from logging.handlers import RotatingFileHandler

def get_log_dir():
    """Returns the directory where logs are stored."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return os.path.join(appdata, "JarvisLauncher", "logs")

    # Fallback to current directory logs/
    return os.path.abspath("logs")

def setup_logger(level=logging.INFO, log_file=None):
    logger = logging.getLogger()
    logger.setLevel(level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Guard against duplicate console handlers
    # Note: logging.FileHandler is a subclass of StreamHandler, so we exclude it
    has_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in logger.handlers
    )

    if not has_console:
        try:
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        except Exception:
            pass

    # File handler
    if log_file:
        # Resolve log file path
        if not os.path.isabs(log_file):
            log_dir = get_log_dir()
            try:
                os.makedirs(log_dir, exist_ok=True)
                log_file = os.path.join(log_dir, log_file)
            except Exception:
                # If we can't create the directory, we might fail to log to file
                return logger

        abs_log_file = os.path.abspath(log_file)

        # Guard against duplicate file handlers for the same file
        has_file_handler = any(
            isinstance(h, logging.FileHandler) and h.baseFilename == abs_log_file
            for h in logger.handlers
        )

        if not has_file_handler:
            try:
                # Use RotatingFileHandler: 5MB max, 5 backups
                fh = RotatingFileHandler(abs_log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
                fh.setFormatter(formatter)
                logger.addHandler(fh)
            except Exception:
                # Requirement 5: fail silently but do not interrupt execution
                pass

    return logger
