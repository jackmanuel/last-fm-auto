import os
import sys
import requests
import json
import hashlib

LAST_FM_API_URL = "http://ws.audioscrobbler.com/2.0/"

def get_last_fm_api_key():
    """Fetches the Last.fm API key from environment variables."""
    api_key = os.environ.get("LAST_FM_API_KEY")
    if not api_key:
        print("FATAL: LAST_FM_API_KEY environment variable not set.")
        print("Please set the environment variable before running.")
        sys.exit(1)
    return api_key

def get_last_fm_api_secret():
    """Fetches the Last.fm API secret from environment variables."""
    api_secret = os.environ.get("LAST_FM_SHARED_SECRET")
    if not api_secret:
        print("FATAL: LAST_FM_API_SECRET environment variable not set.")
        print("Please set the environment variable before running.")
        sys.exit(1)
    return api_secret

def get_last_fm_session_key():
    """Fetches the Last.fm session key from environment variables."""
    session_key = os.environ.get("LAST_FM_SESSION_KEY")
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
        response = requests.get(LAST_FM_API_URL, params=params)
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
        response = requests.get(LAST_FM_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('session', {}).get('key')
    except requests.RequestException as e:
        print(f"API request error while getting session key: {e}")
        return None
    except json.JSONDecodeError:
        print("Failed to parse JSON from getSession API response.")
        return None
