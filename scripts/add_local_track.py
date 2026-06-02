# scripts/add_local_track.py
"""
Utility script to manually add a new track to the local tracks file.
"""
import argparse
import json
from pathlib import Path

def add_local_track(track_name, artist_name):
    """
    Adds a new track to the local_tracks.json file.
    """
    file_path = Path(__file__).parent.parent / "data" / "local_tracks.json"

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tracks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        tracks = []

    new_track = {"track": track_name, "artist": artist_name}
    
    if new_track not in tracks:
        tracks.append(new_track)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(tracks, f, indent=4, ensure_ascii=False)
        
        print(f"Successfully added '{track_name}' by '{artist_name}' to local tracks.")
    else:
        print(f"Track '{track_name}' by '{artist_name}' already exists in local tracks.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a new track to the local tracks file.")
    parser.add_argument("--track", required=True, help="The name of the track.")
    parser.add_argument("--artist", required=True, help="The name of the artist.")

    args = parser.parse_args()

    add_local_track(args.track, args.artist)
