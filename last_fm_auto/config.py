# last_fm_auto/config.py
"""
Centralized configuration management for the Last.fm Auto Scrobbler.
Loads environment variables and defines application-wide constants and paths.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# --- Project Paths ---
# Defines the absolute path to the project's root directory
PROJECT_ROOT = Path(__file__).parent.parent

# --- Logging Configuration ---
# Define the logs directory relative to the project root.
LOG_DIR = PROJECT_ROOT / "logs"

# Create the logs directory if it doesn't exist.
# The `exist_ok=True` argument prevents an error from being raised if the directory already exists.
LOG_DIR.mkdir(exist_ok=True)

# Load environment variables from a .env file
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# --- Database Configuration ---
db_path_from_env = os.getenv('DATABASE_PATH')
if not db_path_from_env:
    raise ValueError("DATABASE_PATH not found in .env file.")

DB_FILE: str = db_path_from_env

DB_TIMEOUT = 20.0

# --- Data File Paths ---
DATA_DIR = PROJECT_ROOT / "data"
ABBREVIATIONS_FILE = DATA_DIR / "abbreviations.json"
LOCAL_TRACKS_FILE = DATA_DIR / "local_tracks.json"

# --- API Configuration ---
LAST_FM_API_KEY = os.getenv('LAST_FM_API_KEY')
LAST_FM_API_SECRET = os.getenv('LAST_FM_API_SECRET')
LAST_FM_SESSION_KEY = os.getenv('LAST_FM_SESSION_KEY')

if not all([LAST_FM_API_KEY, LAST_FM_API_SECRET]):
    raise ValueError("API Key or Secret not found in .env file.")
# Session key is optional at startup, required for scrobbling.

LAST_FM_API_URL = "http://ws.audioscrobbler.com/2.0/"
LAST_FM_SEARCH_LIMIT = 10

# --- Application Logic ---
GUILD_ID = os.getenv('GUILD_ID')
if not GUILD_ID:
    raise ValueError("GUILD_ID not found in .env file.")

DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'

# --- Scoring Model Weights ---
# Centralize weights here so they can be easily tuned.
WEIGHT_SIMILARITY = 0.6
WEIGHT_POPULARITY = 0.4
POPULARITY_THRESHOLD = 300
LOCAL_SIMILARITY_THRESHOLD = 80
