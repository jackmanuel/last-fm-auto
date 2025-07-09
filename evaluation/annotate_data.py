"""
Automates the process of annotating the ground truth dataset.

This script reads the 'ground_truth_data.csv' file, iterates through each
row, and checks if the ground truth 'track_gt' and 'artist_gt' columns
are already filled.

For each row that needs annotation, it:
1. Clears the screen for better visibility.
2. Displays the current query being processed.
3. Runs the `scrobbler.py --test-query` command with the query.
4. Prompts the user to input the correct track and artist name based on the output.
5. Allows the user to skip a query if needed.
6. Saves the input back to the CSV file immediately, allowing the user to
   stop and resume the process without losing progress.
"""
import pandas as pd
import subprocess
import os
import sys

def clear_screen():
    """Clears the console screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def annotate_ground_truth(csv_path):
    """
    Iterates through the ground truth CSV, runs test queries, and prompts
    the user for manual annotation.
    """
    if not os.path.exists(csv_path):
        print(f"Error: The file '{csv_path}' was not found.")
        print("Please run 'tune_hyperparameters.py' first to generate it.")
        sys.exit(1)

    # Load the CSV file into a pandas DataFrame
    df = pd.read_csv(csv_path)
    
    total_rows = len(df)
    annotated_rows = df['track_gt'].notna().sum()

    print(f"Starting annotation process...")
    print(f"Total records: {total_rows} | Annotated: {annotated_rows} | Remaining: {total_rows - annotated_rows}")
    input("Press Enter to begin...")

    for index, row in df.iterrows():
        # Check if 'track_gt' is empty or NaN
        if pd.isna(row['track_gt']) or not row['track_gt']:
            clear_screen()
            
            print(f"--- Annotating Record {row['id']} of {total_rows} ---")
            print(f"Query:          {row['query']}")
            print(f"Resolved Title: {row['resolved_title']}")
            print("-" * 20)

            # Construct and run the command
            command = ['python', 'scrobbler.py', '--test-query', row['query']]
            try:
                # We use shell=True on Windows to ensure commands with quotes are handled correctly
                is_windows = os.name == 'nt'
                subprocess.run(command, text=True, check=True, shell=is_windows)
            except subprocess.CalledProcessError as e:
                print(f"Error running scrobbler.py: {e}")
                continue
            except FileNotFoundError:
                print("Error: 'python' command not found. Make sure Python is in your system's PATH.")
                sys.exit(1)

            print("\n--- Manual Annotation ---")
            print("Enter the correct track and artist below based on the results.")
            print("Type 's' to skip this entry, or 'q' to quit.")

            # Get user input
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

            # Update the DataFrame and save to CSV
            df.at[index, 'track_gt'] = track_gt
            df.at[index, 'artist_gt'] = artist_gt
            df.to_csv(csv_path, index=False)
            
            print("Saved. Moving to the next record.")

    clear_screen()
    print("Annotation process complete or user quit.")
    final_annotated = df['track_gt'].notna().sum()
    print(f"Total records: {total_rows} | Annotated: {final_annotated}")


if __name__ == '__main__':
    csv_file_path = os.path.join('evaluation', 'ground_truth_data.csv')
    annotate_ground_truth(csv_file_path)
