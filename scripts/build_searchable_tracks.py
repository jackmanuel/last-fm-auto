import pandas as pd
import json
import os

def create_track_json_from_csv(filepath):
    """
    Reads a CSV, finds tracks with words starting/ending with an apostrophe,
    and formats them into a specific JSON object.
    
    Args:
        filepath (str): The path to the input CSV file.

    Returns:
        dict: A dictionary structured for JSON output, or None on error.
    """
    try:
        # 1. Load the CSV file
        filepath = "lastfmstats-JackMan3141.csv"
        df = pd.read_csv(filepath, sep=';')
        
        # Ensure required columns exist
        if 'Track' not in df.columns or 'Artist' not in df.columns:
            print("Error: The CSV must contain both 'Track' and 'Artist' columns.")
            return None

    except FileNotFoundError:
        print(f"Error: '{filepath}' not found.")
        return None

    # 2. Filter for the correct tracks using the robust regex
    regex_pattern = r"(^|\s)'\w+|\w+'(?=\s|$)"
    mask = df['Track'].str.contains(regex_pattern, regex=True, na=False)
    filtered_df = df[mask]

    # 3. Build the JSON structure
    output_data = {}
    # Use .iterrows() to loop through the filtered rows
    for index, row in filtered_df.iterrows():
        original_track = row['Track']
        artist_name = row['Artist']
        
        # Create the key by removing all apostrophes from the track title
        clean_track_key = original_track.replace("'", "")
        
        # Create the nested object with the required fields
        track_info = {
            "original_track": original_track,
            "artist": artist_name
        }
        
        # Add the entry to our main dictionary
        output_data[clean_track_key] = track_info
        
    return output_data

def load_or_create_search_data(csv_paths, json_path):
    """
    Loads song data from a JSON cache. If the cache doesn't exist, it generates
    it by reading a list of CSV files, combining them, and removing duplicate
    track titles across all files.
    
    Args:
        csv_paths (list): A list of file paths to the source CSV files.
        json_path (str): Path to the JSON cache file.

    Returns:
        list: A list of song dictionaries ready for searching, or None on error.
    """
    # 1. Try to load from the fast JSON cache first (no changes here)
    if os.path.exists(json_path):
        print(f"Found cache file. Loading data directly from '{json_path}'...")
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not read '{json_path}'. Re-generating...")
            
    # 2. If cache doesn't exist, generate from the list of CSVs
    print(f"Cache not found. Generating new data from source CSVs...")
    
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
        return None

    # Combine all individual DataFrames into one
    print("Combining data from all valid CSV files...")
    combined_df = pd.concat(list_of_dfs, ignore_index=True)

    # Filter the combined DataFrame for tracks using the regex
    regex_pattern = r"(^|\s)'\w+|\w+'(?=\s|$)"
    mask = combined_df['Track'].str.contains(regex_pattern, regex=True, na=False)
    filtered_df = combined_df[mask]

    # Remove duplicate track titles from the *entire combined dataset*
    unique_filtered_df = filtered_df.drop_duplicates(subset=['Track'], keep='first')

    # Convert the final, de-duplicated DataFrame to a list of dicts
    searchable_list = unique_filtered_df[['Track', 'Artist']].rename(
        columns={'Track': 'track', 'Artist': 'artist'}
    ).to_dict('records')

    # 3. Save the newly generated data to the JSON file for next time
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(searchable_list, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved combined data to cache file '{json_path}'.")
    except IOError as e:
        print(f"Error: Could not write cache file to '{json_path}'. {e}")

    return searchable_list


# --- Main script ---
filenames = ['lastfmstats-JackMan3141.csv', 'lastfmstats-juanitosanchz.csv', 'lastfmstats-soabove.csv']
load_or_create_search_data(filenames, 'searchable_tracks.json')
