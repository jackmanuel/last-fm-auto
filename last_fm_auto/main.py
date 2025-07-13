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
    """Fetches all 'new' songs for a specific guild from the database."""
    try:
        conn = sqlite3.connect(config.DB_FILE, timeout=config.DB_TIMEOUT)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM play_history WHERE status = 'new' AND guild_id = ? ORDER BY timestamp DESC",
            (guild_id,)
        )
        songs = cursor.fetchall()
        conn.close()
        return songs
    except sqlite3.Error as e:
        print(f"Database error fetching new songs: {e}")
        return []

def update_song_status(request_id: str, status: str):
    """Updates the status of a song in the database."""
    try:
        conn = sqlite3.connect(config.DB_FILE, timeout=config.DB_TIMEOUT)
        cursor = conn.cursor()
        cursor.execute("UPDATE play_history SET status = ? WHERE request_id = ?", (status, request_id))
        conn.commit()
        conn.close()
        print(f"Updated song {request_id} to status '{status}'.")
    except sqlite3.Error as e:
        print(f"Database error updating song status for {request_id}: {e}")

# --- Application Flow ---

def process_new_songs(pipeline_inst: pipeline.TrackPipeline):
    """Fetches, processes, and scrobbles new songs."""
    new_songs = get_new_songs(config.GUILD_ID)
    if not new_songs:
        return 0

    print(f"\nFound {len(new_songs)} new song(s) to process.")

    for song in new_songs:
        print(f"\n--- Processing Song ID: {song['request_id']} ---")
        print(f"Query: {song['query']}, Resolved Title: {song['resolved_title']}")

        best_track = pipeline_inst.execute(song['query'], song['resolved_title'])

        if best_track:
            track_name = best_track.get('name')
            artist_name = best_track.get('artist')
            
            # Convert ISO timestamp to Unix timestamp
            ts_utc = datetime.fromisoformat(song['timestamp']).replace(tzinfo=timezone.utc)
            unix_ts = int(ts_utc.timestamp())
            
            scrobble_result = lastfm_client.scrobble_track(track_name, artist_name, unix_ts)
            update_song_status(song['request_id'], 'scrobbled' if scrobble_result else 'failed')
        else:
            print("No suitable track found to scrobble.")
            update_song_status(song['request_id'], 'failed')
    return len(new_songs)

def main():
    parser = argparse.ArgumentParser(description="Last.fm Auto Scrobbler")
    parser.add_argument('--run-once', action='store_true', help='Run the scrobbler once and exit.')
    parser.add_argument('--authenticate', action='store_true', help='Authenticate with Last.fm.')
    args = parser.parse_args()

    if args.authenticate:
        print("Authentication flow not fully implemented in this refactor example.")
        sys.exit(0)
    
    if not config.LAST_FM_SESSION_KEY and not args.authenticate:
        print("Error: LAST_FM_SESSION_KEY not found in .env. Please run with --authenticate first.")
        sys.exit(1)

    # Create the pipeline using the default configuration
    pipeline_inst = pipeline.TrackPipeline.from_default_config(
        searchable_tracks=SEARCHABLE_TRACKS
    )
        
    if args.run_once:
        if not process_new_songs(pipeline_inst):
            print("No new songs to process.")        
        sys.exit(0)

    print("Scrobbler starting in continuous mode... Press Ctrl+C to stop.")
    wait_seconds = 30
    spinner_chars = ['|', '/', '-', '\\']

    try:
        while True:
            process_new_songs(pipeline_inst)
            
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
