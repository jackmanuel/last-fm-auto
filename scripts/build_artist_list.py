import os
import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / 'data'

KNOWN_COMMA_ARTISTS_FILE = Path(DATA_DIR) / 'known_comma_artists.json'
REJECTED_COMMA_ARTISTS_FILE = Path(DATA_DIR) / 'rejected_comma_artists.json'

def load_json_list(file_path, description):
    """Loads a JSON list, returning an empty set when the file is absent."""
    try:
        with open(file_path, 'r', encoding='utf-8') as jsonfile:
            values = json.load(jsonfile)
    except FileNotFoundError:
        print(f"{description} file not found at: {file_path}")
        return set()
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse {description} file at {file_path}. Error: {e}")
        return set()

    if not isinstance(values, list):
        print(f"Warning: {description} file must contain a JSON list: {file_path}")
        return set()

    return set(values)

def merge_artists_to_json(data_directory, output_file_path):
    """
    Merges the 'Artist' column from CSVs in a specified data directory
    into a single JSON file.

    Args:
        data_directory (str): The absolute path to the folder with the CSV files.
        output_file_path (str): The absolute path for the output JSON file.
    """
    all_artists = set()

    # Verify that the directory from the config file actually exists.
    if not os.path.isdir(data_directory):
        print(f"Error: The directory specified in DATA_DIR does not exist.")
        print(f"Path not found: {data_directory}")
        return

    print(f"Reading CSV files from: {data_directory}")
    known_comma_artists = load_json_list(KNOWN_COMMA_ARTISTS_FILE, "Known comma artist")
    rejected_comma_artists = load_json_list(REJECTED_COMMA_ARTISTS_FILE, "Rejected comma artist")

    for filename in os.listdir(data_directory):
        if filename.endswith('.csv'):
            print(filename)
            file_path = os.path.join(data_directory, filename)
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
                    reader = csv.DictReader(csvfile, delimiter=';')
                    for row in reader:
                        if 'Artist' in row and row['Artist']:
                            all_artists.add(row['Artist'].strip())
            except Exception as e:
                print(f"Warning: Could not process file {filename}. Error: {e}")

    if not all_artists:
        print("Warning: No artists were found. The output file will be empty.")

    # Convert the set to a sorted list for consistent output.
    unique_artists = sorted(
        artist for artist in all_artists
        if artist not in rejected_comma_artists
    )
    comma_artists = {artist for artist in all_artists if ',' in artist}
    undecided_comma_artists = sorted(
        artist for artist in comma_artists
        if artist not in known_comma_artists and artist not in rejected_comma_artists
    )
    removed_comma_artists = sorted(
        artist for artist in comma_artists
        if artist in rejected_comma_artists
    )

    # Write the list to the JSON file.
    try:
        with open(output_file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(unique_artists, jsonfile, indent=2, ensure_ascii=False)
        print(f"\nSuccessfully merged {len(unique_artists)} unique artists.")
        print(f"Removed {len(removed_comma_artists)} rejected comma-containing artists.")
        if undecided_comma_artists:
            print(f"Kept {len(undecided_comma_artists)} undecided comma-containing artists.")
            print("Run scripts.curate_comma_artists to finish curation.")
        print(f"Output saved to: {output_file_path}")
    except Exception as e:
        print(f"Error: Could not write to output file {output_file_path}. Error: {e}")


if __name__ == '__main__':

    output_json_path = os.path.join(DATA_DIR, 'artists.json')

    merge_artists_to_json(DATA_DIR, output_json_path)
