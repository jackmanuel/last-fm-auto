import logging
import logging.handlers
import os

from .config import LOG_DIR, DEBUG_MODE

LOG_FILE = os.path.join(LOG_DIR, 'last_fm_auto.log')

def setup_logging():
    """Sets up a rotating file logger."""
    logger = logging.getLogger("last_fm_auto")
    log_level = logging.DEBUG if DEBUG_MODE else logging.INFO
    logger.setLevel(log_level)

    handler = logging.handlers.TimedRotatingFileHandler(
        LOG_FILE, when="midnight", interval=1, backupCount=7
    )

    formatter = logging.Formatter(
        "%(asctime)s:%(name)s:%(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Also log to console for development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

log = setup_logging()
