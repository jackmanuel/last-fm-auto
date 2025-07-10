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

# --- Authentication and API Key Management ---

def get_last_fm_session_key():
    """Fetches the Last.fm session key from environment variables."""
    session_key = config.LAST_FM_SESSION_KEY
    if not session_key:
        print("FATAL: LAST_FM_SESSION_KEY environment variable not set.")
        print("Please set the environment variable before running.")
        sys.exit(1)
    return session_key

def sign_request(params, api_secret):
    """Signs a Last.fm API request with an MD5 hash."""
    sorted_params = sorted(params.items())
    signature = "".join([f"{k}{v}" for k, v in sorted_params]) + api_secret
    return hashlib.md5(signature.encode('utf-8')).hexdigest()

def get_auth_token(api_key):
    """Gets a request token from the Last.fm API."""
    params = {
        'method': 'auth.getToken',
        'api_key': api_key,
        'format': 'json'
    }
    try:
        response = requests.get(config.LAST_FM_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('token')
    except requests.RequestException as e:
        print(f"API request error while getting token: {e}")
        return None
    except json.JSONDecodeError:
        print("Failed to parse JSON from getToken API response.")
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
        return data.get('session', {}).get('key')
    except requests.RequestException as e:
        print(f"API request error while getting session key: {e}")
        return None
    except json.JSONDecodeError:
        print("Failed to parse JSON from getSession API response.")
        return None
    

# --- Search and Scrobbling Functions ---S

def search_track(query: str) -> list | None:
    """Searches Last.fm API, parses the JSON, and returns the list of tracks."""
    params = {
        'method': 'track.search',
        'track': query,
        'api_key': config.LAST_FM_API_KEY,
        'format': 'json',
        'limit': config.LAST_FM_SEARCH_LIMIT
    }
    try:
        response = requests.get(config.LAST_FM_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('results', {}).get('trackmatches', {}).get('track', [])
    except requests.RequestException as e:
        print(f"API request error during search: {e}")
    except json.JSONDecodeError:
        print("Failed to parse JSON from search API response.")
    return None

def scrobble_track(track: str, artist: str, timestamp: int) -> dict | None:
    """Scrobbles a track to Last.fm."""
    if not config.LAST_FM_SESSION_KEY:
        print("Error: Cannot scrobble without a session key.")
        return None

    params = {
        'method': 'track.scrobble',
        'artist': artist,
        'track': track,
        'timestamp': str(timestamp),
        'api_key': config.LAST_FM_API_KEY,
        'sk': config.LAST_FM_SESSION_KEY,
    }
    params['api_sig'] = sign_request(params, config.LAST_FM_API_SECRET)
    params['format'] = 'json'
    
    try:
        response = requests.post(config.LAST_FM_API_URL, data=params)
        response.raise_for_status()
        response_data = response.json()

        if 'error' in response_data:
            print(f"Scrobble failed: {response_data['message']} (Code: {response_data['error']})")
            return None
        
        print(f"Successfully scrobbled '{track}' by {artist}.")
        return response_data
    except requests.RequestException as e:
        print(f"API request error while scrobbling: {e}")
    except json.JSONDecodeError:
        print("Failed to parse JSON from scrobble API response.")
    return None