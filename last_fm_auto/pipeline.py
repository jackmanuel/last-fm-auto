# last_fm_auto/pipeline.py
"""
The core search-and-select pipeline.
Takes a query and finds the best matching track using a multi-step process.
"""
import json
from thefuzz import fuzz
from . import config
from . import preprocessing
from . import lastfm_client

# Load the local track data once when the module is imported
SEARCHABLE_TRACKS = preprocessing._load_json_data(config.SEARCHABLE_TRACKS_FILE, "Searchable Tracks")

def _find_match_in_local_db(query: str) -> dict | None:
    """Searches for a matching track in the local searchable_tracks.json."""
    for track_info in SEARCHABLE_TRACKS:
        local_track_title = track_info.get("track")
        if not local_track_title:
            continue

        similarity = fuzz.ratio(query.lower(), local_track_title.lower())
        if similarity >= config.LOCAL_SIMILARITY_THRESHOLD:
            print(f"Found suitable track in local DB: '{local_track_title}' (Similarity: {similarity}%)")
            return {"name": local_track_title, "artist": track_info.get("artist")}
    return None

def _find_best_match_from_api(search_query: str) -> dict | None:
    """Searches API for a query and returns the best match using a weighted model."""
    print(f"Searching Last.fm with query: \"{search_query}\"")
    tracks = lastfm_client.search_track(search_query)

    if not tracks:
        return None

    listeners = [int(track.get('listeners', 0)) for track in tracks]
    max_listeners = max(listeners) if listeners else 0

    best_track = None
    max_score = -1

    for i, track in enumerate(tracks):
        similarity_score = fuzz.ratio(search_query.lower(), track.get('name', '').lower())
        norm_sim = similarity_score / 100.0
        
        norm_listeners = (listeners[i] / max_listeners) if max_listeners > 0 else 0
        
        score = (config.WEIGHT_SIMILARITY * norm_sim) + (config.WEIGHT_POPULARITY * norm_listeners)

        if score > max_score:
            max_score = score
            best_track = track
    
    if max_score >= config.REJECTION_THRESHOLD:
        final_sim = fuzz.ratio(search_query.lower(), best_track['name'].lower())
        print(f"Found best match: '{best_track['name']}' with a score of {max_score:.3f} and similarity {final_sim}%.")
        return best_track
    else:
        # The best score was not good enough, so we reject it.
        print(f"Found best match '{best_track['name']}', but score {max_score:.3f} is below threshold {config.REJECTION_THRESHOLD}. Rejecting.")
        return None

def find_best_track(original_query: str, resolved_title: str) -> dict | None:
    """
    Main pipeline entry point. Cleans inputs and tries multiple strategies
    to find the best possible track match.
    """
    # Step 1: Pre-process inputs
    expanded_query = preprocessing.expand_abbreviations(original_query)
    cleaned_query = preprocessing.clean_youtube_title(expanded_query)

    cleaned_resolved_title = preprocessing.clean_youtube_title(resolved_title)

    # Step 2: Check local database first
    local_match = _find_match_in_local_db(cleaned_query)
    if local_match:
        return local_match

    # Step 3: Determine API search terms
    is_youtube_url = 'youtube.com' in original_query or 'youtu.be' in original_query
    search_terms = [cleaned_resolved_title] if is_youtube_url else [cleaned_query]
    
    # Add resolved_title as a fallback if different
    if not is_youtube_url and cleaned_resolved_title.lower() != cleaned_query.lower():
        search_terms.append(cleaned_resolved_title)

    # Step 4: Execute search against API
    for term in search_terms:
        best_track = _find_best_match_from_api(term)
        if best_track:
            return best_track
        print(f"Search for '{term}' failed. Trying next fallback if available.")

    print(f"No suitable track found after trying all search terms.")
    return None