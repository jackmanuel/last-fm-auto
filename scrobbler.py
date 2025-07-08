import sqlite3
import time
import os
import sys
import re
import requests
import json
import argparse
import hashlib
from dotenv import load_dotenv
from lastfm_auth import get_last_fm_api_key, get_last_fm_api_secret, get_last_fm_session_key, sign_request, get_auth_token, get_session_key
from datetime import datetime, timezone

LAST_FM_API_URL = "http://ws.audioscrobbler.com/2.0/"
LAST_FM_MIN_LISTENERS = 1000

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

ABBREVIATION_MAP = load_abbreviations()

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
        'limit': 5 # Fetch up to 5 results
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


def find_best_track(api_key, query, resolved_title):
    """
    Searches Last.fm for a track, first using the query and then the resolved_title.
    Returns the first track found with more than 1000 listeners.
    """
    # Expand abbreviations in the query
    expanded_query = expand_abbreviations(query)
    
    # Check if the query is a YouTube URL
    youtube_regex = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+'
    is_youtube_url = re.match(youtube_regex, expanded_query)

    if not is_youtube_url:
        # 1. Try with the query if it's not a YouTube URL
        cleaned_query = clean_youtube_title(expanded_query)
        print(f"Searching Last.fm with query: \"{cleaned_query}\"")
        tracks = search_lastfm_and_parse(api_key, cleaned_query)
        if tracks:
            for track in tracks:
                if int(track.get('listeners', 0)) > LAST_FM_MIN_LISTENERS:
                    print("Found suitable track from query.")
                    return track
    else:
        print("Query is a YouTube URL, skipping to resolved_title.")

    # 2. Fallback to resolved_title
    cleaned_resolved_title = clean_youtube_title(resolved_title)
    print(f"Falling back to resolved_title. Searching Last.fm with: \"{cleaned_resolved_title}\"")
    tracks = search_lastfm_and_parse(api_key, cleaned_resolved_title)
    if tracks:
        for track in tracks:
            if int(track.get('listeners', 0)) > LAST_FM_MIN_LISTENERS:
                print("Found suitable track from resolved_title.")
                return track

    # 3. If nothing is found
    print(f"No track found with over {LAST_FM_MIN_LISTENERS} listeners from either query or resolved_title.")
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

# --- TEMPORARY DEBUG FUNCTION ---
def test_manual_query(api_key, query_string):
    """
    Takes a query string and prints the Last.fm API response.
    """
    print(f"--- Running Manual Test Query ---")
    print(f"Query: \"{query_string}\"")

    # Expand abbreviations in the manual query
    expanded_query = expand_abbreviations(query_string)
    print(f"Expanded Query: \"{expanded_query}\"")

    cleaned_query = clean_youtube_title(expanded_query)
    print(f"Cleaned Query for Search: \"{cleaned_query}\"")

    tracks = search_lastfm_and_parse(api_key, cleaned_query)

    print("--- Last.fm Parsed API Response ---")
    if tracks:
        for i, track in enumerate(tracks):
            print(f"  Result {i+1}:")
            print(f"    Name:      {track.get('name', 'N/A')}")
            print(f"    Artist:    {track.get('artist', 'N/A')}")
            print(f"    URL:       {track.get('url', 'N/A')}")
            print(f"    Listeners: {track.get('listeners', 'N/A')}")
    else:
        print("  No tracks found or error in API request.")
    print("-----------------------------------")

def main():
    """
    Main function to test Last.fm API by fetching 5 songs and printing parsed results.
    """
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
        print("Checking for new songs...")
        new_songs = get_new_songs(GUILD_ID)
        if not new_songs:
            print("No new songs found.")
            return

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
        while True:
            scrobble_new_songs()
            print("\nWaiting for 30 seconds before next check...")
            time.sleep(30)
    except KeyboardInterrupt:
        print("\nScrobbler stopped by user.")
        sys.exit(0)

if __name__ == '__main__':
    main()

