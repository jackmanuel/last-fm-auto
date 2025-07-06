import sqlite3
import time
import os
import sys
import re
import requests
import json
from dotenv import load_dotenv

LAST_FM_API_URL = "http://ws.audioscrobbler.com/2.0/"

load_dotenv()

DB_FILE = os.getenv('DATABASE_PATH')
if not DB_FILE:
    raise ValueError("DB_PATH not found in .env file. Please check your configuration.")

GUILD_ID = os.getenv('GUILD_ID')
if not GUILD_ID:
    raise ValueError("GUILD_ID not found in .env file. Please check your configuration.")

# Set a generous timeout to handle potential database locks
DB_TIMEOUT = 20.0 

def get_new_songs(guild_id, limit=5):
    """Fetches a batch of new songs for a specific guild, limited by the given amount."""
    conn = sqlite3.connect(DB_FILE, timeout=DB_TIMEOUT)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM play_history WHERE status = 'new' AND guild_id = ? ORDER BY timestamp DESC LIMIT ?", 
        (guild_id, limit)
    )
    songs = cursor.fetchall()
    
    conn.close()
    return songs

def get__last_fm_api_key():
    """Fetches the Last.fm API key from environment variables."""
    api_key = os.environ.get("LAST_FM_API_KEY")
    if not api_key:
        print("FATAL: LAST_FM_API_KEY environment variable not set.")
        print("Please set the environment variable before running.")
        sys.exit(1)
    return api_key

def clean_youtube_title(title):
    """
    Removes common, non-musical junk from YouTube titles to create a better
    search query for the Last.fm API.
    """
    patterns = [
        r'\(official music video\)', r'\[official music video\]',
        r'\(official video\)', r'\[official video\]', r'\[music video\]',
        r'\(music video\)',
        r'\(official audio\)',
        r'\(lyric video\)', r'\[lyric video\]',
        r'\(lyrics\)', r'\[lyrics\]',
        r'\(hd\)', r'\[hd\]',
        r'\(4k\)', r'\[4k\]',
        r'\(audio\)', r'\[audio\]',
        r'\(visualizer\)', r'\[visualizer\]',
    ]
    
    cleaned_title = title
    for pattern in patterns:
        cleaned_title = re.sub(pattern, '', cleaned_title, flags=re.IGNORECASE)
    
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


def main():
    """
    Main function to test Last.fm API by fetching 5 songs and printing parsed results.
    """
    print("Scrobbler starting for parsed API testing...")

    api_key = get__last_fm_api_key()
    new_songs = get_new_songs(GUILD_ID, limit=5)

    if not new_songs:
        print(f"No new songs found for guild ID {GUILD_ID} to test.")
        return

    print(f"Found {len(new_songs)} new songs for guild ID {GUILD_ID}. Testing Last.fm API and printing parsed results...")
    for song in new_songs:
        original_title = song['resolved_title']
        print(f"\n--- Processing Song ID: {song['request_id']} ---")
        print(f"Original Title: {original_title}")

        cleaned_title = clean_youtube_title(original_title)
        print(f"Cleaned Title for Search: \"{cleaned_title}\"")

        tracks = search_lastfm_and_parse(api_key, cleaned_title)

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

    print("\nTesting finished. The script will now exit.")

if __name__ == '__main__':
    main()
