import pandas as pd
import json
import os
import argparse

from last_fm_auto.config import DATA_DIR, LOCAL_TRACKS_FILE

def build_searchable_tracks(csv_paths, json_path):
    """
    Builds a JSON file of songs with apostrophes in their titles from a list of CSV files.
    
    This function will:
    1. Check if the output JSON file already exists. If so, it will do nothing.
    2. Read a list of CSV files.
    3. Combine them and filter for tracks with words starting or ending with an apostrophe.
    4. Remove duplicate tracks.
    5. Save the result to the specified JSON file.
    
    Args:
        csv_paths (list): A list of file paths to the source CSV files.
        json_path (str): Path to the output JSON file.
    """
    if os.path.exists(json_path):
        response = input(f"Output file '{json_path}' already exists. Overwrite? (y/n): ").lower()
        if response not in ['y', 'yes']:
            print("Operation cancelled. Nothing to do.")
            return

    # If cache doesn't exist, generate from the list of CSVs
    print(f"Output file not found or approved for overwrite. Generating new data from source CSVs...")
    
    list_of_dfs = []
    for path in csv_paths:
        if not os.path.exists(path):
            print(f"--> Warning: Source file not found at '{path}'. Skipping.")
            continue
        
        try:
            df = pd.read_csv(path, sep=';')
            if 'Track' not in df.columns or 'Artist' not in df.columns:
                print(f"--> Warning: CSV '{path}' is missing 'Track' or 'Artist' column. Skipping.")
                continue
            list_of_dfs.append(df)
        except Exception as e:
            print(f"--> Warning: Failed to read or process '{path}'. Error: {e}. Skipping.")

    if not list_of_dfs:
        print("Error: No valid CSV files were processed. Cannot generate data.")
        return


    print("Combining data from all valid CSV files...")
    combined_df = pd.concat(list_of_dfs, ignore_index=True)

    # Filter for tracks with apostrophes at the start or end of words
    regex_pattern = r"(^|\s)'\w+|\w+'(?=\s|$)"
    mask = combined_df['Track'].str.contains(regex_pattern, regex=True, na=False)
    filtered_df = combined_df[mask]

    unique_filtered_df = filtered_df.drop_duplicates(subset=['Track'], keep='first')

    searchable_list = unique_filtered_df[['Track', 'Artist']].rename(
        columns={'Track': 'track', 'Artist': 'artist'}
    ).to_dict('records')

    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(searchable_list, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved combined data to output file '{json_path}'.")
    except IOError as e:
        print(f"Error: Could not write output file to '{json_path}'. {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Builds a JSON file of songs with apostrophes from CSV files. "
            "If no files are specified, it automatically searches for *.csv files in the 'data/' directory."
        )
    )
    parser.add_argument(
        "csv_files",
        nargs='*',
        help="Optional: One or more paths to input CSV files. If omitted, searches the 'data/' directory."
    )
    parser.add_argument(
        "--output",
        default=str(LOCAL_TRACKS_FILE),
        help=f"Path to the output JSON file. (default: {LOCAL_TRACKS_FILE})"
    )
    
    args = parser.parse_args()
    
    csv_paths = args.csv_files
    
    # If no file paths were provided, search the 'data' directory
    if not csv_paths:
        print(f"No input files specified. Searching for *.csv in '{DATA_DIR}/'...")
        csv_paths = [str(p) for p in DATA_DIR.glob('*.csv')]
        
        if not csv_paths:
            print(f"Warning: No CSV files found in the '{DATA_DIR}/' directory.")
    
    if not csv_paths:
        print("No CSV files to process. Exiting.")
    else:
        build_searchable_tracks(csv_paths, args.output)

