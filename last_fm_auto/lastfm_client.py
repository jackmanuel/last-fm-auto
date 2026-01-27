# last_fm_auto/lastfm_client.py
"""
Client for interacting with the Last.fm API.
Handles authentication, request signing, and all API calls.
"""
import requests
import hashlib
import json
import sys
from . import config
from .logger import log

# --- Authentication and API Key Management ---

def get_last_fm_session_key():
    """Fetches the Last.fm session key from environment variables."""
    session_key = config.LAST_FM_SESSION_KEY
    if not session_key:
        log.critical("LAST_FM_SESSION_KEY environment variable not set.")
        log.critical("Please set the environment variable before running.")
        sys.exit(1)
    return session_key

def sign_request(params, api_secret):
    """Signs a Last.fm API request with an MD5 hash."""
    sorted_params = sorted(params.items())
    signature = "".join([f"{k}{v}" for k, v in sorted_params]) + api_secret
    return hashlib.md5(signature.encode('utf-8')).hexdigest()

def get_auth_token(api_key, api_secret):
    """Gets a request token from the Last.fm API."""
    params = {
        'method': 'auth.getToken',
        'api_key': api_key
    }
    params['api_sig'] = sign_request(params, api_secret)
    params['format'] = 'json'
    
    try:
        response = requests.get(config.LAST_FM_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('token')
    except requests.RequestException as e:
        log.error(f"API request error while getting token: {e}")
        return None
    except json.JSONDecodeError:
        log.error("Failed to parse JSON from getToken API response.")
        return None

def get_session_key(api_key, api_secret, token):
    """Gets a session key from the Last.fm API."""
    params = {
        'method': 'auth.getSession',
        'api_key': api_key,
        'token': token
    }
    params['api_sig'] = sign_request(params, api_secret)
    params['format'] = 'json'
    try:
        response = requests.get(config.LAST_FM_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        session = data.get('session')
        if not session or 'key' not in session:
            error_message = data.get('message', 'Unknown error')
            log.error(f"Error getting session key: {error_message}")
            return None
        return session.get('key')
    except requests.RequestException as e:
        log.error(f"API request error while getting session key: {e}")
        return None
    except json.JSONDecodeError:
        log.error("Failed to parse JSON from getSession API response.")
        return None

def _save_session_key_to_env(session_key):
    """Saves the session key to the .env file."""
    env_path = config.ENV_PATH
    lines = []
    key_found = False
    if env_path.exists():
        with open(env_path, 'r') as f:
            lines = f.readlines()
    
    with open(env_path, 'w') as f:
        for line in lines:
            if line.strip().startswith('LAST_FM_SESSION_KEY='):
                f.write(f'LAST_FM_SESSION_KEY="{session_key}"\n')
                key_found = True
            else:
                f.write(line)
        if not key_found:
            f.write(f'\nLAST_FM_SESSION_KEY="{session_key}"\n')
    log.info("Session key successfully saved to .env file.")


def authenticate():
    """Guides the user through the Last.fm authentication process."""
    api_key = config.LAST_FM_API_KEY
    api_secret = config.LAST_FM_API_SECRET

    if not api_key or not api_secret:
        log.error("LAST_FM_API_KEY or LAST_FM_API_SECRET not found in .env file.")
        log.error("Please create a .env file in the project root with your credentials.")
        sys.exit(1)

    # 1. Get an auth token
    log.info("Requesting authentication token from Last.fm...")
    token = get_auth_token(api_key, api_secret)
    if not token:
        log.error("Could not get an authentication token. Please check your API key and secret.")
        sys.exit(1)

    # 2. Ask user to authorize
    auth_url = f"http://www.last.fm/api/auth/?api_key={api_key}&token={token}"
    print("\n--- User Authorization Required ---")
    print("Please open the following URL in your web browser to grant permission:")
    print(auth_url)
    input("\nPress Enter after you have authorized the application...")

    # 3. Get a session key
    log.info("Fetching session key...")
    session_key = get_session_key(api_key, api_secret, token)

    if session_key:
        # 4. Save the session key
        _save_session_key_to_env(session_key)
        log.info("Authentication successful! You can now run the scrobbler.")
    else:
        log.error("Authentication failed. Could not retrieve a session key.")
        log.error("Please try the process again.")
        sys.exit(1)

# --- Search and Scrobbling Functions ---

def search_track(track: str, artist: str | None = None) -> list | None:
    """Searches Last.fm API, parses the JSON, and returns the list of tracks."""
    params = {
        'method': 'track.search',
        'track': track,
        'api_key': config.LAST_FM_API_KEY,
        'format': 'json',
        'limit': config.LAST_FM_SEARCH_LIMIT
    }
    if artist:
        params['artist'] = artist
    try:
        response = requests.get(config.LAST_FM_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('results', {}).get('trackmatches', {}).get('track', [])
    except requests.RequestException as e:
        log.error(f"API request error during search: {e}")
    except json.JSONDecodeError:
        log.error("Failed to parse JSON from search API response.")
    return None

def get_track_info(track: str, artist: str) -> dict | None:
    """Gets detailed track info from Last.fm, including album information."""
    params = {
        'method': 'track.getInfo',
        'track': track,
        'artist': artist,
        'api_key': config.LAST_FM_API_KEY,
        'autocorrect': '1',
        'format': 'json'
    }
    try:
        response = requests.get(config.LAST_FM_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        track_data = data.get('track', {})
        if not track_data:
            return None
            
        result = {
            'name': track_data.get('name'),
            'artist': track_data.get('artist', {}).get('name')
        }
        
        # Extract album info if available
        album_data = track_data.get('album')
        if album_data:
            result['album'] = album_data.get('title')
        
        return result
    except requests.RequestException as e:
        log.error(f"API request error during track.getInfo: {e}")
    except json.JSONDecodeError:
        log.error("Failed to parse JSON from track.getInfo API response.")
    return None

def scrobble_track(track: str, artist: str, timestamp: int, album: str | None = None) -> dict | None:
    """Scrobbles a track to Last.fm."""
    if not config.LAST_FM_SESSION_KEY:
        log.error("Cannot scrobble without a session key.")
        return None

    params = {
        'method': 'track.scrobble',
        'artist': artist,
        'track': track,
        'timestamp': str(timestamp),
        'api_key': config.LAST_FM_API_KEY,
        'sk': config.LAST_FM_SESSION_KEY,
    }
    if album:
        params['album'] = album
    params['api_sig'] = sign_request(params, config.LAST_FM_API_SECRET)
    params['format'] = 'json'
    
    try:
        response = requests.post(config.LAST_FM_API_URL, data=params)
        response.raise_for_status()
        response_data = response.json()

        if 'error' in response_data:
            log.error(f"Scrobble failed: {response_data['message']} (Code: {response_data['error']})")
            return None
        
        album_info = f" from '{album}'" if album else ""
        log.info(f"Successfully scrobbled '{track}' by {artist}{album_info}.")
        return response_data
    except requests.RequestException as e:
        log.error(f"API request error while scrobbling: {e}")
    except json.JSONDecodeError:
        log.error("Failed to parse JSON from scrobble API response.")
    return None


def update_now_playing(artist: str, track: str, album: str | None = None) -> dict | None:
    """Updates the 'Now Playing' status on Last.fm."""
    if not config.LAST_FM_SESSION_KEY:
        log.error("Cannot update 'Now Playing' without a session key.")
        return None

    params = {
        'method': 'track.updateNowPlaying',
        'artist': artist,
        'track': track,
        'api_key': config.LAST_FM_API_KEY,
        'sk': config.LAST_FM_SESSION_KEY
    }
    if album:
        params['album'] = album

    params['api_sig'] = sign_request(params, config.LAST_FM_API_SECRET)
    params['format'] = 'json'

    try:
        response = requests.post(config.LAST_FM_API_URL, data=params)
        response.raise_for_status()
        response_data = response.json()

        if 'error' in response_data:
            log.error(f"Update 'Now Playing' failed: {response_data['message']} (Code: {response_data['error']})")
            return None

        log.info(f"Successfully updated 'Now Playing' for '{track}' by {artist}.")
        return response_data
    except requests.RequestException as e:
        log.error(f"API request error while updating 'Now Playing': {e}")
    except json.JSONDecodeError:
        log.error("Failed to parse JSON from 'Now Playing' API response.")
    return None
