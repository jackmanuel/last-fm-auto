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
DASH_SEPARATOR_PATTERN = r'\s+[-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\uFE58\uFE63\uFF0D]\s+'
DASH_TOPIC_SUFFIX_PATTERN = re.compile(r'\s*[-\u2010-\u2015\u2212]\s*topic$', re.IGNORECASE)
CHANNEL_WORD_SUFFIXES = (
    "official artist channel",
    "official youtube channel",
    "official channel",
    "official youtube",
    "official",
    "topic",
)
CHANNEL_WORD_PREFIXES = ("official",)
COMPACT_CHANNEL_SUFFIXES = ("official", "vevo")
NOISY_CHANNEL_WORDS = {
    "archive",
    "archives",
    "channel",
    "collection",
    "collections",
    "label",
    "labels",
    "music",
    "playlist",
    "playlists",
    "production",
    "productions",
    "promo",
    "promotion",
    "promotions",
    "radio",
    "records",
    "recordings",
    "soundtrack",
    "soundtracks",
}


def expand_abbreviations(query: str) -> str:
    """
    Expands known abbreviations in the query string only if they appear
    at the beginning or end of the query.
    """
    for abbr, full_name in ABBREVIATION_MAP.items():
        pattern = r'^\s*' + re.escape(abbr) + r'\b|\b' + re.escape(abbr) + r'\s*$'
        query = re.sub(pattern, full_name, query, flags=re.IGNORECASE)
    return query

def clean_youtube_title(title: str) -> str:
    """
    Removes common, non-musical junk from YouTube titles to create a better
    search query for the Last.fm API.
    """
    junk_patterns = [
        'official music video', 'official video', 'official hd video', 'official live video', 'music video',
        'official audio', 'official', 'lyric video', 'official lyric video','lyrics', 'audio',
        'visualizer', 'official visualizer', 'hd', '4k', '1080p', '720p', 'live',
        '4k remastered', '8k remastered', '1080p remastered', 'remastered'
    ]
    
    # Remove patterns in brackets or parentheses
    pattern_string = r'\s*[\[(](' + '|'.join(junk_patterns) + r')[\])]\s*'
    cleaned_title = re.sub(pattern_string, ' ', title, flags=re.IGNORECASE)
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title)
    
    return cleaned_title.strip()

def _remove_word_suffix(value: str, suffix: str) -> str:
    """Removes a case-insensitive trailing word suffix from a channel name."""
    suffix_with_space = f" {suffix}"
    if value.casefold().endswith(suffix_with_space):
        return value[:-len(suffix_with_space)].strip()

    return value

def _remove_word_prefix(value: str, prefix: str) -> str:
    """Removes a case-insensitive leading word prefix from a channel name."""
    prefix_with_space = f"{prefix} "
    if value.casefold().startswith(prefix_with_space):
        return value[len(prefix_with_space):].strip()

    return value

def _remove_compact_suffix(value: str, suffix: str) -> str:
    """Removes compact suffixes such as VEVO from names like AdeleVEVO."""
    if value.casefold().endswith(suffix) and len(value) > len(suffix):
        return value[:-len(suffix)].strip()

    return value

def _contains_noisy_channel_word(value: str) -> bool:
    """Returns True when a channel name contains a word that often means uploader/label noise."""
    words = set(re.findall(r"[a-z0-9']+", value.casefold()))
    return bool(words & NOISY_CHANNEL_WORDS)

def normalize_youtube_channel_name(channel_name: str) -> str:
    """
    Normalizes a YouTube channel name before trying to treat it as an artist hint.
    """
    if not channel_name:
        return ""

    normalized = str(channel_name).strip()
    normalized = re.sub(r'^@+', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)

    previous = None
    while previous != normalized:
        previous = normalized
        normalized = DASH_TOPIC_SUFFIX_PATTERN.sub('', normalized).strip()

        for prefix in CHANNEL_WORD_PREFIXES:
            normalized = _remove_word_prefix(normalized, prefix)

        for suffix in CHANNEL_WORD_SUFFIXES:
            normalized = _remove_word_suffix(normalized, suffix)

        for suffix in COMPACT_CHANNEL_SUFFIXES:
            normalized = _remove_compact_suffix(normalized, suffix)

    return normalized

def _normalized_artist_text(value: str | None) -> str:
    """Returns a simple normalized string for artist equality checks."""
    if not value:
        return ""

    return re.sub(r'\s+', ' ', str(value).strip().lower())

def is_same_artist(artist_a: str | None, artist_b: str | None) -> bool:
    """Returns True if two artist strings normalize to the same value."""
    return _normalized_artist_text(artist_a) == _normalized_artist_text(artist_b)

def match_youtube_channel_artist(
    channel_name: str,
    artist_list: list,
    threshold: int = config.YOUTUBE_CHANNEL_ARTIST_THRESHOLD,
    margin: int = config.YOUTUBE_CHANNEL_ARTIST_MARGIN,
) -> dict:
    """
    Strictly matches a YouTube channel name to a known artist.

    Returns a dictionary with ``artist``, ``score``, and ``normalized_channel``.
    If the match is not strong enough, ``artist`` is None.
    """
    normalized_channel = normalize_youtube_channel_name(channel_name)
    no_match = {
        "artist": None,
        "score": 0,
        "runner_up_score": 0,
        "normalized_channel": normalized_channel,
    }

    if not normalized_channel or not artist_list:
        return no_match

    matches = process.extract(
        normalized_channel,
        artist_list,
        scorer=fuzz.token_sort_ratio,
        limit=2,
    )
    if not matches:
        return no_match

    best_artist, best_score, *_ = matches[0]
    runner_up_score = matches[1][1] if len(matches) > 1 else 0
    result = {
        "artist": None,
        "score": best_score,
        "runner_up_score": runner_up_score,
        "normalized_channel": normalized_channel,
    }

    normalized_channel_key = _normalized_artist_text(normalized_channel)
    normalized_best_key = _normalized_artist_text(best_artist)
    exact_match = normalized_channel_key == normalized_best_key

    # Short/common names are too easy to hit accidentally in a large artist list.
    if (len(normalized_channel_key) <= 4 or _contains_noisy_channel_word(normalized_channel)) and not exact_match:
        return result

    if best_score < threshold:
        return result

    if best_score < 100 and best_score - runner_up_score < margin:
        return result

    result["artist"] = best_artist
    return result

def split_artist_track(query: str, artist_list: list, threshold: int = 80):
    """
    Attempts to split a query into artist and track using fuzzy matching against a known artist list.
    Handles "track artist" and "track" formats.
    If a split cannot be found, the original query is returned as the track.
    """
    if not artist_list:
        return {"artist": None, "track": query}

    # 1. Handle "artist - track" or "track - artist"
    parts = re.split(DASH_SEPARATOR_PATTERN, query, maxsplit=1)
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

    # 2. Handle "track artist" with fuzzy matching on word combinations
    words = query.split()
    best_match = {"artist": None, "track": query, "score": 0}

    # Check for "track artist" format by trying all split points
    for i in range(1, len(words)):
        track_candidate = " ".join(words[:i])
        artist_candidate = " ".join(words[i:])
        result = process.extractOne(artist_candidate, artist_list)
        if result:
            match, score, *_= result

            shorter_len = min(len(artist_candidate), len(match))
            longer_len = max(len(artist_candidate), len(match))

            if longer_len > 0:
                length_ratio = shorter_len / longer_len
                score *= (length_ratio) # Punish matches with length differences

            if score > best_match["score"]:
                best_match = {"artist": match, "track": track_candidate, "score": score}

    if best_match["score"] >= threshold and best_match["track"]:
        return {"artist": best_match["artist"], "track": best_match["track"]}

    # 3. If no clear split, return the original query as the track
    return {"artist": None, "track": query}
