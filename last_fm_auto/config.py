# last_fm_auto/config.py
"""
Centralized configuration management for the Last.fm Auto Scrobbler.
Loads environment variables and defines application-wide constants and paths.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# --- Project Paths ---
PROJECT_ROOT = Path(__file__).parent.parent

# --- Logging Configuration ---
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# --- Database Configuration ---
DB_FILE = os.getenv('DATABASE_PATH')
DB_TIMEOUT = 20.0

# --- Data File Paths ---
DATA_DIR = PROJECT_ROOT / "data"
ABBREVIATIONS_FILE = DATA_DIR / "abbreviations.json"
LOCAL_TRACKS_FILE = DATA_DIR / "local_tracks.json"

# --- API Configuration ---
LAST_FM_API_KEY = os.getenv('LAST_FM_API_KEY')
LAST_FM_API_SECRET = os.getenv('LAST_FM_API_SECRET')
LAST_FM_SESSION_KEY = os.getenv('LAST_FM_SESSION_KEY')

LAST_FM_API_URL = "http://ws.audioscrobbler.com/2.0/"
LAST_FM_SEARCH_LIMIT = 10

# --- Application Logic ---
GUILD_ID = os.getenv('GUILD_ID')
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'

def validate_config(require_session_key=False):
    """
    Validates that all required configuration values are set in the environment.
    Raises ValueError with a descriptive message listing any missing configurations.
    """
    missing_vars = []
    if not DB_FILE:
        missing_vars.append("DATABASE_PATH")
    if not LAST_FM_API_KEY:
        missing_vars.append("LAST_FM_API_KEY")
    if not LAST_FM_API_SECRET:
        missing_vars.append("LAST_FM_API_SECRET")
    if not GUILD_ID:
        missing_vars.append("GUILD_ID")
    if require_session_key and not LAST_FM_SESSION_KEY:
        missing_vars.append("LAST_FM_SESSION_KEY")

    if missing_vars:
        msg = f"Missing required configuration variables in .env file: {', '.join(missing_vars)}."
        if "LAST_FM_SESSION_KEY" in missing_vars:
            msg += " Run authentication using `python -m last_fm_auto.main --authenticate` first."
        raise ValueError(msg)

# --- Scoring Model Weights ---
WEIGHT_SIMILARITY = 0.6
WEIGHT_POPULARITY = 0.4
POPULARITY_THRESHOLD = 300
LOCAL_SIMILARITY_THRESHOLD = 80
YOUTUBE_CHANNEL_ARTIST_THRESHOLD = 95
YOUTUBE_CHANNEL_ARTIST_MARGIN = 8
