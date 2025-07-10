# evaluation/annotate_data.py
"""
A command-line tool to interactively annotate a ground truth dataset.

This script reads a ground truth CSV file, and for each row that needs
annotation, it:
1. Displays the query information from the CSV.
2. Runs the project's core `pipeline.find_best_track` function to get the
   algorithm's best guess for a match.
3. Displays the algorithm's guess to the user.
4. Prompts the user to input the correct "ground truth" track and artist.
5. Saves progress to the CSV file after each annotation.
"""
import pandas as pd
import os
import sys
import argparse

from last_fm_auto import pipeline

def clear_screen():
    """Clears the console screen for better visibility."""
    os.system('cls' if os.name == 'nt' else 'clear')

def annotate_ground_truth(csv_path, id_col, query_col, title_col):
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

    total_rows = len(df)
    annotated_rows = df['track_gt'].notna().sum()

    print(f"Starting annotation process for: {os.path.basename(csv_path)}")
    print(f"Total records: {total_rows} | Annotated: {annotated_rows} | Remaining: {total_rows - annotated_rows}")
    input("Press Enter to begin...")

    for index, row in df.iterrows():
        # Annotate if the ground truth track name is missing
        if pd.isna(row['track_gt']) or not row['track_gt']:
            clear_screen()
            
            # --- Display Information to User ---
            print(f"--- Annotating Record {row[id_col]} of {total_rows} ---")
            print(f"Query (from '{query_col}'):    {row[query_col]}")
            print(f"Resolved Title (from '{title_col}'): {row[title_col]}")
            print("-" * 20)

            # --- Run the internal pipeline to get the algorithm's best guess ---
            print("\n--- Algorithm's Best Guess ---")
            best_track = pipeline.find_best_track(
                original_query=str(row[query_col]),
                resolved_title=str(row[title_col])
            )
            if best_track:
                print(f"  Track:  {best_track.get('name')}")
                print(f"  Artist: {best_track.get('artist')}")
            else:
                print("  Algorithm found no suitable match.")
            
            # --- Prompt User for Annotation ---
            print("\n--- Manual Annotation ---")
            print("Enter the correct track and artist below. Type 's' to skip, 'q' to quit.")

            track_gt = input("Ground Truth Track Name: ").strip()
            if track_gt.lower() == 'q':
                break
            if track_gt.lower() == 's':
                print("Skipping...")
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
            df.to_csv(csv_path, index=False)
            
            print("Saved. Moving to the next record.")

    clear_screen()
    print("Annotation process complete or user quit.")
    final_annotated = df['track_gt'].notna().sum()
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
    args = parser.parse_args()
        
    annotate_ground_truth(args.csv_file, args.id_column, args.query_column, args.title_column)