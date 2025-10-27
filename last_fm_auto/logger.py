import logging
import logging.handlers
import os
import sys
import io

from .config import LOG_DIR, DEBUG_MODE

LOG_FILE = os.path.join(LOG_DIR, 'last_fm_auto.log')

def setup_logging():
    """Sets up a rotating file logger."""
    logger = logging.getLogger("last_fm_auto")
    log_level = logging.DEBUG if DEBUG_MODE else logging.INFO
    logger.setLevel(log_level)

    handler = logging.handlers.TimedRotatingFileHandler(
        LOG_FILE, when="midnight", interval=1, backupCount=7, encoding='utf-8'
    )

    formatter = logging.Formatter(
        "%(asctime)s:%(name)s:%(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Also log to console for development
    # Create a custom stream with UTF-8 encoding to handle special characters
    console_stream = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    console_handler = logging.StreamHandler(console_stream)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

log = setup_logging()
