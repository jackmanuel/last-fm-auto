# last_fm_auto/preprocessing.py
"""
Handles all text preprocessing and cleaning tasks.
This includes expanding abbreviations and cleaning YouTube titles.
"""
import re
import json
from . import config

def _load_json_data(file_path, description):
    """Helper function to load data from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {description} file not found at {file_path}. This feature may not work.")
        return {}
    except json.JSONDecodeError:
        print(f"Warning: Could not decode {description} file at {file_path}.")
        return {}

# Load data at module level so it's only read from disk once.
ABBREVIATION_MAP = _load_json_data(config.ABBREVIATIONS_FILE, "Abbreviations")

def expand_abbreviations(query: str) -> str:
    """Expands known abbreviations in the query string."""
    for abbr, full_name in ABBREVIATION_MAP.items():
        query = re.sub(r'\b' + re.escape(abbr) + r'\b', full_name, query, flags=re.IGNORECASE)
    return query

def clean_youtube_title(title: str) -> str:
    """
    Removes common, non-musical junk from YouTube titles to create a better
    search query for the Last.fm API.
    """
    junk_patterns = [
        'official music video', 'official video', 'official live video', 'music video',
        'official audio', 'official', 'lyric video', 'lyrics', 'audio',
        'visualizer', 'official visualizer', 'hd', '4k', '1080p', '720p', 'live'
    ]
    
    # Remove patterns in brackets or parentheses
    pattern_string = r'\s*[\[(](' + '|'.join(junk_patterns) + r')[\])]\s*'
    cleaned_title = re.sub(pattern_string, '', title, flags=re.IGNORECASE)
    
    # Remove anything after a pipe symbol (|)
    cleaned_title = cleaned_title.split('|')[0]
    
    return cleaned_title.strip()