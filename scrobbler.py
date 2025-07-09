import sqlite3
import time
import os
import sys
import re
import requests
import json
import argparse
from dotenv import load_dotenv
from lastfm_auth import get_last_fm_api_key, get_last_fm_api_secret, get_last_fm_session_key, sign_request, get_auth_token, get_session_key
from datetime import datetime, timezone
from thefuzz import fuzz

LAST_FM_API_URL = "http://ws.audioscrobbler.com/2.0/"
LAST_FM_SEARCH_LIMIT = 10

load_dotenv()

DB_FILE = os.getenv('DATABASE_PATH')
if not DB_FILE:
    raise ValueError("DB_PATH not found in .env file. Please check your configuration.")

GUILD_ID = os.getenv('GUILD_ID')
if not GUILD_ID:
    raise ValueError("GUILD_ID not found in .env file. Please check your configuration.")

# Set a generous timeout to handle potential database locks
DB_TIMEOUT = 20.0

# --- Abbreviation Expansion ---
def load_abbreviations(file_path='abbreviations.json'):
    """Loads the abbreviation dictionary from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {file_path} not found. No abbreviations will be loaded.")
        return {}
    except json.JSONDecodeError:
        print(f"Warning: Could not decode {file_path}. No abbreviations will be loaded.")
        return {}

def load_searchable_tracks(file_path='searchable_tracks.json'):
    """Loads the searchable tracks from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {file_path} not found. No searchable tracks will be loaded.")
        return []
    except json.JSONDecodeError:
        print(f"Warning: Could not decode {file_path}. No searchable tracks will be loaded.")
        return []

ABBREVIATION_MAP = load_abbreviations()
SEARCHABLE_TRACKS = load_searchable_tracks()

def expand_abbreviations(query):
    """Expands known abbreviations in the query string."""
    for abbr, full_name in ABBREVIATION_MAP.items():
        # Use regex to replace whole words only to avoid partial matches
        query = re.sub(r'\b' + re.escape(abbr) + r'\b', full_name, query, flags=re.IGNORECASE)
    return query

def get_new_songs(guild_id):
    """Fetches all new songs for a specific guild."""
    conn = sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM play_history WHERE status = 'new' AND guild_id = ? ORDER BY timestamp DESC",
        (guild_id,)
    )
    songs = cursor.fetchall()
    
    conn.close()
    return songs

def clean_youtube_title(title):
    """
    Removes common, non-musical junk from YouTube titles to create a better
    search query for the Last.fm API.
    """
    junk_patterns = [
        'official music video', 'official video', 'music video',
        'official audio', 'lyric video', 'lyrics', 'audio',
        'visualizer', 'hd', '4k', '1080p', '720p', 'live'
    ]
    
    pattern_string = r'\s*[\[(](' + '|'.join(junk_patterns) + r')[\])]\s*'
    
    # Remove the patterns
    cleaned_title = re.sub(pattern_string, '', title, flags=re.IGNORECASE)
    
    # Also, remove anything after a pipe symbol (|), which often indicates a channel name
    cleaned_title = cleaned_title.split('|')[0]
    
    return cleaned_title.strip()

def search_lastfm_and_parse(api_key, title):
    """Searches Last.fm API, parses the JSON, and returns the list of tracks."""
    params = {
        'method': 'track.search',
        'track': title,
        'api_key': api_key,
        'format': 'json',
        'limit': LAST_FM_SEARCH_LIMIT
    }
    try:
        response = requests.get(LAST_FM_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        # Navigate through the JSON structure to get the list of tracks
        return data.get('results', {}).get('trackmatches', {}).get('track', [])
    except requests.RequestException as e:
        print(f"API request error: {e}")
        return None
    except json.JSONDecodeError:
        print("Failed to parse JSON from API response.")
        return None
    except (KeyError, IndexError):
        print(f"Could not parse Last.fm API response for title: {title}")
        return None

def find_match_in_local_json(query):
    """
    Searches for a matching track in the local searchable_tracks.json.
    """
    SIMILARITY_THRESHOLD = 70
    for track_info in SEARCHABLE_TRACKS:
        local_track_title = track_info.get("track")
        if not local_track_title:
            continue

        similarity_score = fuzz.ratio(query.lower(), local_track_title.lower())
        if similarity_score >= SIMILARITY_THRESHOLD:
            print(f"Found suitable track in local JSON: '{local_track_title}' (Similarity: {similarity_score}%)")
            return {"name": local_track_title, "artist": track_info.get("artist")}
    return None


def _find_best_match_for_query(api_key, search_query):
    """
    Helper function to search for a query and return the best match using a
    weighted scoring model.
    """
    # First, try to find a match in the local JSON file
    local_match = find_match_in_local_json(search_query)
    if local_match:
        return local_match

    print(f"Searching Last.fm with query: \"{search_query}\"")
    tracks = search_lastfm_and_parse(api_key, search_query)

    if not tracks:
        return None

    # --- Weighted Scoring Model ---
    w_sim = 0.6
    w_listeners = 0.4

    listeners = [int(track.get('listeners', 0)) for track in tracks]
    max_listeners = max(listeners) if listeners else 0

    best_track = None
    max_score = -1

    print(f"  - Scoring {len(tracks)} results with w_sim={w_sim}, w_listeners={w_listeners}...")

    for i, track in enumerate(tracks):
        similarity_score = fuzz.ratio(search_query.lower(), track.get('name', '').lower())
        norm_sim = similarity_score / 100.0

        current_listeners = int(listeners[i])
        norm_listeners = (current_listeners / max_listeners) if max_listeners > 0 else 0
        
        score = (w_sim * norm_sim) + (w_listeners * norm_listeners)

        print(f"    - Candidate: '{track.get('name', '')}' (Sim: {norm_sim:.2f}, Listeners: {norm_listeners:.2f}) -> Score: {score:.3f}")

        if score > max_score:
            max_score = score
            best_track = track
    
    if best_track:
        final_similarity = fuzz.ratio(search_query.lower(), best_track.get('name', '').lower())
        print(f"Found best match: '{best_track.get('name')}' with {best_track.get('listeners')} listeners and {final_similarity}% similarity (Score: {max_score:.3f}).")
    
    return best_track


def find_best_track(api_key, query, resolved_title):
    """
    Searches Last.fm for a track, trying the query and resolved_title.
    Finds the result with the highest weighted score.
    """
    expanded_query = expand_abbreviations(query)
    cleaned_query = clean_youtube_title(expanded_query)
    cleaned_resolved_title = clean_youtube_title(resolved_title)

    search_terms = []
    
    youtube_regex = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+'
    is_youtube_url = re.match(youtube_regex, expanded_query)

    if is_youtube_url:
        search_terms.append(cleaned_resolved_title)
    else:
        search_terms.append(cleaned_query)
        # Add resolved_title as a fallback if it's different.
        if cleaned_resolved_title.lower() != cleaned_query.lower():
            search_terms.append(cleaned_resolved_title)

    for term in search_terms:
        best_track = _find_best_match_for_query(api_key, term)
        if best_track:
            return best_track
        if len(search_terms) > 1 and term != search_terms[-1]:
            print(f"Search for '{term}' failed. Trying next fallback.")

    print(f"No suitable track found after trying all search terms.")
    return None




def scrobble_track(api_key, api_secret, session_key, track, artist, timestamp_str):
    """Scrobbles a track to Last.fm."""
    params = {
        'method': 'track.scrobble',
        'artist': artist,
        'track': track,
        'timestamp': timestamp_str,
        'api_key': api_key,
        'sk': session_key,
    }
    params['api_sig'] = sign_request(params, api_secret)
    params['format'] = 'json'
    
    try:
        response = requests.post(LAST_FM_API_URL, data=params)
        response.raise_for_status()
        response_data = response.json()

        if 'error' in response_data:
            error_code = response_data['error']
            error_message = response_data['message']
            print(f"Scrobble failed with error code {error_code}: {error_message}")
            return None

        scrobbles = response_data.get('scrobbles', {})
        if '@attr' in scrobbles and scrobbles['@attr'].get('ingored') == '1':
            ignored_message = scrobbles['scrobble']['ignoredMessage']
            print(f"Scrobble ignored: {ignored_message['#text']} (Code: {ignored_message['code']})")

        print(f"Successfully scrobbled '{track}' by {artist}.")
        return response_data

    except requests.RequestException as e:
        print(f"API request error while scrobbling: {e}")
        return None
    except json.JSONDecodeError:
        print("Failed to parse JSON from scrobble API response.")
        return None

def update_song_status(request_id, status):
    """Updates the status of a song in the database."""
    conn = sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT)
    cursor = conn.cursor()
    cursor.execute("UPDATE play_history SET status = ? WHERE request_id = ?", (status, request_id))
    conn.commit()
    conn.close()
    print(f"Updated song {request_id} to status '{status}'.")

def test_manual_query(api_key, query_string):
    """
    Takes a query string, runs it through the matching logic, and prints detailed results.
    Does not scrobble.
    """
    print(f"--- Running Manual Test Query ---")
    print(f"Query: \"{query_string}\"")

    # Expand and clean the query
    expanded_query = expand_abbreviations(query_string)
    print(f"Expanded Query: \"{expanded_query}\"")
    cleaned_query = clean_youtube_title(expanded_query)
    print(f"Cleaned Query for Search: \"{cleaned_query}\"")

    # --- Step 1: Search Last.fm ---
    print("\n--- 1. Last.fm API Search Results ---")
    tracks = search_lastfm_and_parse(api_key, cleaned_query)
    if not tracks:
        print("  No tracks found or error in API request.")
        print("--------------------------")
        return

    for i, track in enumerate(tracks):
        print(f"  Result {i+1}:")
        print(f"    Name:      {track.get('name', 'N/A')}")
        print(f"    Artist:    {track.get('artist', 'N/A')}")
        print(f"    Listeners: {track.get('listeners', 'N/A')}")

    # --- Step 2: Find Best Match using Weighted Scoring ---
    print("\n--- 2. Finding Best Match with Weighted Scoring ---")
    best_match = _find_best_match_for_query(api_key, cleaned_query)

    # --- Step 3: Display Final Result ---
    print("\n--- 3. Final Best Match Selected ---")
    if not best_match:
        print("  No match found.")
        print("--------------------------")
        return
    
    print(f"  Name:      {best_match.get('name', 'N/A')}")
    print(f"  Artist:    {best_match.get('artist', 'N/A')}")
    print(f"  Listeners: {best_match.get('listeners', 'N/A')}")
    print("--------------------------")

def main():
    parser = argparse.ArgumentParser(description="Scrobbler script with temporary debug options.")
    parser.add_argument('--test-query', type=str, help='Run a single test query against the Last.fm API.')
    parser.add_argument('--run-once', action='store_true', help='Run the scrobbler once and exit.')
    parser.add_argument('--authenticate', action='store_true', help='Authenticate with Last.fm to get a session key.')
    args = parser.parse_args()

    api_key = get_last_fm_api_key()

    if args.authenticate:
        api_secret = get_last_fm_api_secret()
        token = get_auth_token(api_key)
        if not token:
            sys.exit(1)
        
        print(f"Please go to this URL to authorize the application:")
        print(f"http://www.last.fm/api/auth/?api_key={api_key}&token={token}")
        
        input("Press Enter after you have authorized the application...")
        
        session_key = get_session_key(api_key, api_secret, token)
        
        if session_key:
            print(f"Success! Your session key is: {session_key}")
            print("Please add this to your .env file as LAST_FM_SESSION_KEY")
        else:
            print("Failed to get session key.")
        sys.exit(0)

    if args.test_query:
        test_manual_query(api_key, args.test_query)
        sys.exit(0)
    
    api_secret = get_last_fm_api_secret()
    session_key = get_last_fm_session_key()

    def scrobble_new_songs():
        sys.stdout.write("Checking for new songs...")
        sys.stdout.flush()
        
        new_songs = get_new_songs(GUILD_ID)
        
        if not new_songs:
            # Clear the "Checking for new songs..." message if none are found
            sys.stdout.write("\r" + " " * 40 + "\r")
            sys.stdout.flush()
            return

        # If songs are found, move to the next line before printing details
        sys.stdout.write("\n")
        sys.stdout.flush()
        print(f"Found {len(new_songs)} new songs. Processing...")
        for song in new_songs:
            query = song['query']
            resolved_title = song['resolved_title']
            timestamp_str = song['timestamp']

            dt_naive = datetime.fromisoformat(timestamp_str)
            dt_utc = dt_naive.replace(tzinfo=timezone.utc)
            unix_timestamp_float = dt_utc.timestamp()
            unix_timestamp_int = int(unix_timestamp_float) # last.fm requires an integer timestamp
            unix_timestamp = str(unix_timestamp_int)
            
            print(f"\n--- Processing Song ID: {song['request_id']} for scrobbling ---")
            print(f"Original Query: {query}")
            print(f"Original Resolved Title: {resolved_title}")

            best_track = find_best_track(api_key, query, resolved_title)

            if best_track:
                track_name = best_track.get('name')
                artist_name = best_track.get('artist')
                
                scrobble_result = scrobble_track(api_key, api_secret, session_key, track_name, artist_name, unix_timestamp)
                if scrobble_result:
                    update_song_status(song['request_id'], 'scrobbled')
                else:
                    update_song_status(song['request_id'], 'failed')
            else:
                print("No suitable track found to scrobble.")
                update_song_status(song['request_id'], 'failed')

    if args.run_once:
        scrobble_new_songs()
        sys.exit(0)

    try:
        print("Scrobbler starting in continuous mode...")
        print("Will check for new songs every 30 seconds.")
        while True:
            scrobble_new_songs()
            
            # Wait for 30 seconds with a spinning cursor
            wait_time = 30
            spinner = ['|', '/', '-', '\\']
            for i in range(wait_time * 4): # Run for 30 seconds, updating 4 times per second
                sys.stdout.write(f"\rWaiting for new song plays... {spinner[i % 4]}")
                sys.stdout.flush()
                time.sleep(0.25)
            # Clear the line after waiting
            sys.stdout.write("\r" + " " * 40 + "\r")
            sys.stdout.flush()

    except KeyboardInterrupt:
        print("\nScrobbler stopped by user.")
        sys.exit(0)

if __name__ == '__main__':
    main()

