import argparse
import json
import os
import sys
import sqlite3
import pandas as pd

def clear_screen():
    """Clears the console screen for better visibility."""
    os.system('cls' if os.name == 'nt' else 'clear')

def is_youtube_url(url):
    """Checks if a URL is a YouTube URL."""
    if not isinstance(url, str):
        return False
    return "youtube.com" in url or "youtu.be" in url

def build_ground_truth(db_path, output_json):
    """
    Interactively builds a ground truth JSON file from a list of queries
    extracted from an SQLite database.
    """
    try:
        with open(output_json, 'r', encoding='utf-8') as f:
            ground_truth_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        ground_truth_data = []

    annotated_queries = {item['query'] for item in ground_truth_data}

    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query("SELECT query FROM play_history", conn)
        conn.close()
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Error accessing the database at '{db_path}': {e}", file=sys.stderr)
        sys.exit(1)

    queries_df = df[~df["query"].apply(is_youtube_url)]
    queries = queries_df["query"].drop_duplicates().tolist()

    queries_to_annotate = [q for q in queries if q not in annotated_queries]
    
    total_queries = len(queries)
    remaining_to_annotate = len(queries_to_annotate)
    already_annotated = total_queries - remaining_to_annotate

    print("--- Ground Truth Annotation ---")
    print(f"Total unique non-YouTube queries in database: {total_queries}")
    print(f"Already annotated: {already_annotated}")
    print(f"Remaining to annotate: {remaining_to_annotate}")
    if remaining_to_annotate == 0:
        print("Nothing to do.")
        return

    input("Press Enter to begin...")

    for i, query in enumerate(queries_to_annotate):
        clear_screen()
        print(f"--- Annotating Query {i + 1} of {remaining_to_annotate} ---")
        print(f"Query: {query}")
        print("-" * 20)
        print("Enter the correct track and artist. Leave artist blank for 'None'.")
        print("Type 's' to skip this query, 'q' to save and quit.")

        try:
            track_gt = input("  Correct Track:  ").strip()
            if track_gt.lower() == 'q':
                break
            if track_gt.lower() == 's':
                continue

            artist_gt = input("  Correct Artist: ").strip()
            if artist_gt.lower() == 'q':
                break
            if artist_gt.lower() == 's':
                continue
        except KeyboardInterrupt:
            print("\nCaught interrupt. Quitting...")
            break
            
        ground_truth_data.append({
            "query": query,
            "track": track_gt,
            "artist": artist_gt if artist_gt else None
        })

        try:
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(ground_truth_data, f, indent=2, ensure_ascii=False)
            print("Saved.")
        except IOError as e:
            print(f"FATAL: Could not save to output file '{output_json}'. Error: {e}", file=sys.stderr)
            break

    clear_screen()
    print("Annotation process complete or user quit.")
    print(f"Total annotated records in '{output_json}': {len(ground_truth_data)}")

def main():
    parser = argparse.ArgumentParser(
        description="Interactively build a ground truth JSON for artist-track splitting from a database.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--db-path",
        required=True,
        help="Path to the SQLite database containing the 'play_history' table."
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to the output ground truth JSON file to be created or updated."
    )
    args = parser.parse_args()
    
    build_ground_truth(args.db_path, args.output_json)

if __name__ == "__main__":
    main()