# last_fm_auto/main.py
"""
Main application entry point for the Last.fm Auto Scrobbler.
Handles command-line arguments, the main processing loop, and database interactions.
"""
import sqlite3
import time
import sys
import argparse
from datetime import datetime, timezone
from . import config
from . import pipeline
from . import lastfm_client
from . import preprocessing

# Load the searchable tracks once when the module is initialized
SEARCHABLE_TRACKS = preprocessing._load_json_data(config.LOCAL_TRACKS_FILE, "Searchable Tracks")

# --- Database Interaction ---

def get_new_songs(guild_id: str) -> list:
    """Fetches all 'new', 'completed' songs for a specific guild from the database."""
    try:
        conn = sqlite3.connect(config.DB_FILE, timeout=config.DB_TIMEOUT)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM play_history WHERE play_status = 'completed' AND scrobble_status = 'new' AND guild_id = ? ORDER BY play_start_timestamp DESC",
            (guild_id,)
        )
        songs = cursor.fetchall()
        conn.close()
        return songs
    except sqlite3.Error as e:
        print(f"Database error fetching new songs: {e}")
        return []

def update_song_scrobble_status(request_id: str, scrobble_status: str):
    """Updates the scrobble_status of a song in the database."""
    try:
        conn = sqlite3.connect(config.DB_FILE, timeout=config.DB_TIMEOUT)
        cursor = conn.cursor()
        cursor.execute("UPDATE play_history SET scrobble_status = ? WHERE request_id = ?", (scrobble_status, request_id))
        conn.commit()
        conn.close()
        print(f"Updated song {request_id} to scrobble_status '{scrobble_status}'.")
    except sqlite3.Error as e:
        print(f"Database error updating song scrobble_status for {request_id}: {e}")

def get_playing_song(guild_id: str) -> sqlite3.Row | None:
    """Fetches the current 'playing' song for a specific guild from the database."""
    try:
        conn = sqlite3.connect(config.DB_FILE, timeout=config.DB_TIMEOUT)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM play_history WHERE play_status = 'playing' AND guild_id = ? ORDER BY play_start_timestamp DESC LIMIT 1",
            (guild_id,)
        )
        song = cursor.fetchone()
        conn.close()
        return song
    except sqlite3.Error as e:
        print(f"Database error fetching playing song: {e}")
        return None

def process_now_playing(pipeline_inst: pipeline.TrackPipeline, last_fm_now_playing_track: dict, processed_tracks_cache: dict) -> dict:
    """
    Checks the currently playing song, updates Last.fm 'Now Playing' status,
    and caches the processed track details.
    Returns the updated now playing track.
    """
    playing_song = get_playing_song(config.GUILD_ID)

    # If no song is playing, there's nothing to do.
    if not playing_song:
        return last_fm_now_playing_track

    # If the currently playing song is the same as the one we last reported, do nothing.
    if last_fm_now_playing_track and last_fm_now_playing_track.get('request_id') == playing_song['request_id']:
        return last_fm_now_playing_track

    # A new song is playing
    request_id = playing_song['request_id']
    print(f"\n--- New song detected, processing: {request_id} ---")
    best_track = pipeline_inst.execute(playing_song['query'], playing_song['resolved_title'])

    # Cache the result, whether it's a valid track or None (a failure)
    processed_tracks_cache[request_id] = best_track
    print(f"Cached processed info for request_id: {request_id}")

    # This object is used to check if the 'playing' song has changed.
    # We create it even if the track lookup failed, to prevent reprocessing.
    updated_track_info = {
        'request_id': request_id,
        'name': best_track.get('name') if best_track else None,
        'artist': best_track.get('artist') if best_track else None
    }

    if best_track:
        # Update Last.fm 'Now Playing' only if we found a valid track
        lastfm_client.update_now_playing(updated_track_info['artist'], updated_track_info['name'])
        print(f"Updated 'Now Playing' to: {updated_track_info['name']}")
    else:
        print("No suitable track found for 'Now Playing'. Caching failure.")
        # Note: We don't clear the 'Now Playing' on Last.fm, we just let it be.
    
    return updated_track_info

def process_new_songs(pipeline_inst: pipeline.TrackPipeline, processed_tracks_cache: dict):
    """
    Fetches new songs, processes them, and scrobbles them.
    Uses a cache of processed tracks to avoid redundant pipeline calls.
    """
    new_songs = get_new_songs(config.GUILD_ID)
    if not new_songs:
        return 0

    print(f"\nFound {len(new_songs)} new song(s) to process.")

    for song in new_songs:
        request_id = song['request_id']
        print(f"\n--- Processing Song ID: {request_id} ---")
        
        track_name, artist_name = None, None

        # Optimization: Check if the track has already been processed and is in our cache.
        if request_id in processed_tracks_cache:
            print(f"Using cached info for scrobbling request_id: {request_id}")
            cached_info = processed_tracks_cache.pop(request_id) # Use and remove from cache
            
            # Handle cached failures (None)
            if cached_info is None:
                print("Cached result was a failure. Marking as failed.")
                update_song_scrobble_status(request_id, 'failed')
                continue # Move to the next song

            track_name = cached_info.get('name')
            artist_name = cached_info.get('artist')
        else:
            # Fallback for songs that weren't 'Now Playing' (e.g., from a backlog)
            print(f"No cache hit. Query: {song['query']}, Resolved Title: {song['resolved_title']}")
            best_track = pipeline_inst.execute(song['query'], song['resolved_title'])
            if best_track:
                track_name = best_track.get('name')
                artist_name = best_track.get('artist')

        if track_name and artist_name:
            # Calculate scrobble timestamp from play_start_timestamp and duration
            start_ts_utc = datetime.fromisoformat(song['play_start_timestamp']).replace(tzinfo=timezone.utc)
            scrobble_ts = int(start_ts_utc.timestamp()) + song['duration']
            
            scrobble_result = lastfm_client.scrobble_track(track_name, artist_name, scrobble_ts)
            update_song_scrobble_status(song['request_id'], 'scrobbled' if scrobble_result else 'failed')
        else:
            print("No suitable track found to scrobble.")
            update_song_scrobble_status(song['request_id'], 'failed')
            
    return len(new_songs)

def main():
    parser = argparse.ArgumentParser(description="Last.fm Auto Scrobbler")
    parser.add_argument('--run-once', action='store_true', help='Run the scrobbler once and exit.')
    parser.add_argument('--authenticate', action='store_true', help='Authenticate with Last.fm.')
    args = parser.parse_args()

    if args.authenticate:
        lastfm_client.authenticate()
        sys.exit(0)
    
    if not config.LAST_FM_SESSION_KEY and not args.authenticate:
        print("Error: LAST_FM_SESSION_KEY not found in .env. Please run with --authenticate first.")
        sys.exit(1)

    # Create the pipeline using the default configuration
    pipeline_inst = pipeline.TrackPipeline.from_default_config(
        searchable_tracks=SEARCHABLE_TRACKS
    )

    if args.run_once:
        if not process_new_songs(pipeline_inst, {}):
            print("No new songs to process.")
        sys.exit(0)

    print("Scrobbler starting in continuous mode... Press Ctrl+C to stop.")
    wait_seconds = 5
    spinner_chars = ['|', '/', '-', '\\']
    last_fm_now_playing_track = None
    processed_tracks_cache = {}

    try:
        while True:
            # 1. Handle 'Now Playing' status and cache the result
            last_fm_now_playing_track = process_now_playing(
                pipeline_inst, last_fm_now_playing_track, processed_tracks_cache
            )

            # 2. Handle scrobbling of completed tracks, using the cache
            process_new_songs(pipeline_inst, processed_tracks_cache)
            
            # 3. Wait before the next cycle
            for i in range(wait_seconds * 4):
                char = spinner_chars[i % len(spinner_chars)]
                sys.stdout.write(f"\rWaiting for new song plays... {char}")
                sys.stdout.flush()
                time.sleep(0.25)
            
            # Clear the spinner line before the next check
            sys.stdout.write("\r" + " " * 50 + "\r")
            sys.stdout.flush()

    except KeyboardInterrupt:
        print("\nScrobbler stopped by user.")
        sys.exit(0)

if __name__ == '__main__':
    main()
