# last_fm_auto/preprocessing.py
"""
Handles all text preprocessing and cleaning tasks.
This includes expanding abbreviations and cleaning YouTube titles.
"""
import re
import json
from thefuzz import process, fuzz
from . import config
from .logger import log

def _load_json_dict(file_path, description):
    """Helper function to load a dictionary from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            log.warning(f"Data in {description} file at {file_path} is not a dictionary.")
            return {}
    except FileNotFoundError:
        log.warning(f"{description} file not found at {file_path}. This feature may not work.")
        return {}
    except json.JSONDecodeError:
        log.warning(f"Could not decode {description} file at {file_path}.")
        return {}

def _load_json_list(file_path, description):
    """Helper function to load a list from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            log.warning(f"Data in {description} file at {file_path} is not a list.")
            return []
    except FileNotFoundError:
        log.warning(f"{description} file not found at {file_path}. This feature may not work.")
        return []
    except json.JSONDecodeError:
        log.warning(f"Could not decode {description} file at {file_path}.")
        return []

# Load data at module level so it's only read from disk once.
ABBREVIATION_MAP = _load_json_dict(config.ABBREVIATIONS_FILE, "Abbreviations")
ARTIST_LIST = _load_json_list(config.DATA_DIR / "artists.json", "Artists")


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
        'official audio', 'official', 'lyric video', 'official lyric video','lyrics', 'audio',
        'visualizer', 'official visualizer', 'hd', '4k', '1080p', '720p', 'live',
        '4k remastered', '8k remastered', '1080p remastered', 'remastered'
    ]
    
    # Remove patterns in brackets or parentheses
    pattern_string = r'\s*[\[(](' + '|'.join(junk_patterns) + r')[\])]\s*'
    cleaned_title = re.sub(pattern_string, '', title, flags=re.IGNORECASE)
    
    return cleaned_title.strip()

def split_artist_track(query: str, artist_list: list, threshold: int = 80):
    """
    Attempts to split a query into artist and track using fuzzy matching against a known artist list.
    Handles "track artist", "artist track", and "track" formats.
    If a split cannot be found, the original query is returned as the track.
    """
    if not artist_list:
        return {"artist": None, "track": query}

    # 1. Handle "artist - track" or "track - artist"
    parts = re.split(r'\s+-\s+', query, maxsplit=1)
    if len(parts) == 2:
        part1, part2 = parts[0].strip(), parts[1].strip()
        
        # Use process.extractOne to find the best match for each part.
        match1, score1, *_ = process.extractOne(part1, artist_list)
        match2, score2, *_ = process.extractOne(part2, artist_list)
        
        # If one part is a significantly better artist match, use that split.
        if score1 > score2 and score1 >= threshold:
            return {"artist": match1, "track": part2}
        if score2 > score1 and score2 >= threshold:
            return {"artist": match2, "track": part1}

    # 2. Handle "artist track" or "track artist" with fuzzy matching
    best_match = {"artist": None, "track": query, "score": 0}
    for artist in artist_list:
        # Check for fuzzy match at the beginning
        if len(query) >= len(artist):
            query_start = query[:len(artist)]
            score = fuzz.ratio(query_start.lower(), artist.lower())

            if score >= threshold and score > best_match["score"]:
                track = query[len(artist):].strip(" -")
                if track: # Make sure we are not left with an empty track
                    best_match = {"artist": artist, "track": track, "score": score}

        # Check for fuzzy match at the end
        if len(query) >= len(artist):
            query_end = query[-len(artist):]
            score = fuzz.ratio(query_end.lower(), artist.lower())

            if score >= threshold and score > best_match["score"]:
                track = query[:-len(artist):].strip(" -")
                if track:
                    best_match = {"artist": artist, "track": track, "score": score}

    if best_match["artist"]:
        return {"artist": best_match["artist"], "track": best_match["track"]}

    # 3. If no clear split, return the original query as the track
    return {"artist": None, "track": query}