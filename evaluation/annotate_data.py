# evaluation/annotate_data.py
"""
A command-line tool to interactively annotate a ground truth dataset.

This script reads a ground truth CSV file, and for each row that needs
annotation, it:
1. Displays the query information from the CSV.
2. Runs the project's core `TrackPipeline` to get the algorithm's best guess
   for a match.
3. Displays the algorithm's guess to the user.
4. Prompts the user to input the correct "ground truth" track and artist.
5. Saves progress to the CSV file after each annotation.
"""
import pandas as pd
import os
import sys
import argparse
import json

from last_fm_auto import config
from last_fm_auto.pipeline import TrackPipeline

ANNOTATED_STATUSES = {"annotated", "no_match"}

def clear_screen():
    """Clears the console screen for better visibility."""
    os.system('cls' if os.name == 'nt' else 'clear')

def _load_searchable_tracks(searchable_tracks_path):
    """Loads the local searchable tracks used by the production pipeline."""
    try:
        with open(searchable_tracks_path, 'r', encoding='utf-8') as f:
            searchable_tracks = json.load(f)
    except FileNotFoundError:
        print(f"Warning: Searchable tracks file not found at '{searchable_tracks_path}'. Continuing with an empty local cache.")
        return []
    except json.JSONDecodeError as e:
        print(f"Error: Could not parse searchable tracks file at '{searchable_tracks_path}': {e}")
        sys.exit(1)

    if not isinstance(searchable_tracks, list):
        print(f"Error: Searchable tracks file at '{searchable_tracks_path}' must contain a JSON list.")
        sys.exit(1)

    return searchable_tracks

def _is_annotated(row):
    """Returns True if a row already has a completed annotation."""
    status = str(row.get('annotation_status', '')).strip().lower()
    if status in ANNOTATED_STATUSES:
        return True

    return pd.notna(row['track_gt']) and str(row['track_gt']).strip() != ""

def _display_best_track(best_track):
    """Prints a pipeline result in a compact, readable form."""
    if best_track:
        print(f"  Track:  {best_track.get('name')}")
        print(f"  Artist: {best_track.get('artist')}")
        if best_track.get('album'):
            print(f"  Album:  {best_track.get('album')}")
    else:
        print("  Algorithm found no suitable match.")

def annotate_ground_truth(csv_path, id_col, query_col, title_col, searchable_tracks_path):
    """
    Iterates through a ground truth CSV, runs the internal matching pipeline,
    and prompts the user for manual annotation.
    """
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Error: The file '{csv_path}' was not found.")
        sys.exit(1)

    # Ensure required columns exist
    required_cols = [id_col, query_col, title_col, 'track_gt', 'artist_gt']
    if not all(col in df.columns for col in required_cols):
        print(f"Error: CSV must contain the columns: {', '.join(required_cols)}")
        sys.exit(1)

    if 'annotation_status' not in df.columns:
        df['annotation_status'] = ""

    searchable_tracks = _load_searchable_tracks(searchable_tracks_path)
    track_pipeline = TrackPipeline.from_default_config(searchable_tracks=searchable_tracks)

    total_rows = len(df)
    annotated_rows = df.apply(_is_annotated, axis=1).sum()

    print(f"Starting annotation process for: {os.path.basename(csv_path)}")
    print(f"Searchable tracks loaded: {len(searchable_tracks)}")
    print(f"Total records: {total_rows} | Annotated: {annotated_rows} | Remaining: {total_rows - annotated_rows}")
    input("Press Enter to begin...")

    for index, row in df.iterrows():
        # Annotate if the row has not already been completed.
        if not _is_annotated(row):
            clear_screen()
            
            # --- Display Information to User ---
            print(f"--- Annotating Record {row[id_col]} of {total_rows} ---")
            print(f"Query (from '{query_col}'):    {row[query_col]}")
            print(f"Resolved Title (from '{title_col}'): {row[title_col]}")
            print("-" * 20)

            # --- Run the internal pipeline to get the algorithm's best guess ---
            print("\n--- Algorithm's Best Guess ---")
            best_track = track_pipeline.execute(
                original_query=str(row[query_col]),
                resolved_title=str(row[title_col])
            )
            _display_best_track(best_track)
            
            # --- Prompt User for Annotation ---
            print("\n--- Manual Annotation ---")
            print("Enter the correct track and artist below.")
            print("Commands: 'a' accept guess, 'n' no match, 's' skip, 'q' quit.")

            track_gt = input("Ground Truth Track Name: ").strip()
            command = track_gt.lower()
            if command == 'q':
                break
            if command == 's':
                print("Skipping...")
                continue
            if command == 'n':
                df.at[index, 'track_gt'] = ""
                df.at[index, 'artist_gt'] = ""
                df.at[index, 'annotation_status'] = "no_match"
                df.to_csv(csv_path, index=False)
                print("Saved no-match annotation. Moving to the next record.")
                continue
            if command == 'a':
                if not best_track:
                    print("There is no algorithm guess to accept. Skipping...")
                    input("Press Enter to continue...")
                    continue

                df.at[index, 'track_gt'] = best_track.get('name', '')
                df.at[index, 'artist_gt'] = best_track.get('artist', '')
                df.at[index, 'annotation_status'] = "annotated"
                df.to_csv(csv_path, index=False)
                print("Accepted algorithm guess. Moving to the next record.")
                continue

            artist_gt = input("Ground Truth Artist Name: ").strip()
            if artist_gt.lower() == 'q':
                break
            if artist_gt.lower() == 's':
                print("Skipping...")
                continue

            # Update DataFrame and save immediately to prevent data loss
            df.at[index, 'track_gt'] = track_gt
            df.at[index, 'artist_gt'] = artist_gt
            df.at[index, 'annotation_status'] = "annotated"
            df.to_csv(csv_path, index=False)
            
            print("Saved. Moving to the next record.")

    clear_screen()
    print("Annotation process complete or user quit.")
    final_annotated = df.apply(_is_annotated, axis=1).sum()
    print(f"Total records: {total_rows} | Annotated: {final_annotated}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Interactively annotate a ground truth data file.")
    parser.add_argument(
        "--csv-file",
        required=True,
        help="Path to the CSV file to be annotated (e.g., evaluation/data/ground_truth_data.csv)."
    )
    parser.add_argument(
        "--id-column", default="id",
        help="Name of the column containing the unique ID."
    )
    parser.add_argument(
        "--query-column", default="query",
        help="Name of the column containing the original query string."
    )
    parser.add_argument(
        "--title-column", default="resolved_title",
        help="Name of the column containing the resolved title (especially for YouTube links)."
    )
    parser.add_argument(
        "--searchable-tracks",
        default=config.LOCAL_TRACKS_FILE,
        help="Path to the local searchable tracks JSON file."
    )
    args = parser.parse_args()
        
    annotate_ground_truth(
        args.csv_file,
        args.id_column,
        args.query_column,
        args.title_column,
        args.searchable_tracks
    )
