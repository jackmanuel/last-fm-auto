# scripts/curate_comma_artists.py
"""
Utility script to interactively curate artist names containing commas.
"""
import argparse
import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
KNOWN_COMMA_ARTISTS_FILE = DATA_DIR / 'known_comma_artists.json'
REJECTED_COMMA_ARTISTS_FILE = DATA_DIR / 'rejected_comma_artists.json'


def load_json_list(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as jsonfile:
            data = json.load(jsonfile)
    except FileNotFoundError:
        return []

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {file_path}")

    return data


def save_json_list(file_path, values):
    with open(file_path, 'w', encoding='utf-8') as jsonfile:
        json.dump(sorted(values), jsonfile, indent=2, ensure_ascii=False)


def collect_artists_from_csvs(data_directory):
    artists = set()

    for csv_path in sorted(data_directory.glob('*.csv')):
        print(f"Reading {csv_path.name}")
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=';')
                for row in reader:
                    artist = row.get('Artist')
                    if artist:
                        artists.add(artist.strip())
        except Exception as e:
            print(f"Warning: Could not process {csv_path.name}. Error: {e}")

    return artists


def collect_artists_from_json(artists_json):
    with open(artists_json, 'r', encoding='utf-8') as jsonfile:
        artists = json.load(jsonfile)

    if not isinstance(artists, list):
        raise ValueError(f"Expected a JSON list in {artists_json}")

    return {artist.strip() for artist in artists if isinstance(artist, str) and artist.strip()}


def choose_artists_source(args):
    if args.from_json:
        return collect_artists_from_json(args.from_json)

    artists = collect_artists_from_csvs(args.data_dir)
    if artists:
        return artists

    print("No CSV artists found. Falling back to data/artists.json.")
    return collect_artists_from_json(args.data_dir / 'artists.json')


def curate_comma_artists(args):
    artists = choose_artists_source(args)
    comma_artists = sorted(artist for artist in artists if ',' in artist)

    known = set(load_json_list(args.known_file))
    rejected = set(load_json_list(args.rejected_file))
    already_decided = known | rejected
    pending = [artist for artist in comma_artists if artist not in already_decided]

    print(f"Found {len(comma_artists)} comma-containing artist names.")
    print(f"Already approved: {len(known)}")
    print(f"Already rejected: {len(rejected)}")
    print(f"Remaining to judge: {len(pending)}")
    print()
    print("Enter y to keep as a real artist name, n to reject as a collaboration, u to undo, q to quit.")

    history = []
    index = 0
    while index < len(pending):
        artist = pending[index]
        answer = input(f"[{index + 1}/{len(pending)}] Keep '{artist}'? [y/n/u/q] ").strip().casefold()

        if answer == 'q':
            break

        if answer == 'u':
            if not history:
                print("Nothing to undo.")
                continue

            previous_artist, previous_choice = history.pop()
            if previous_choice == 'y':
                known.discard(previous_artist)
            else:
                rejected.discard(previous_artist)
            index -= 1
            save_json_list(args.known_file, known)
            save_json_list(args.rejected_file, rejected)
            continue

        if answer not in {'y', 'n'}:
            print("Please enter y, n, u, or q.")
            continue

        if answer == 'y':
            known.add(artist)
        else:
            rejected.add(artist)

        history.append((artist, answer))
        save_json_list(args.known_file, known)
        save_json_list(args.rejected_file, rejected)
        index += 1

    print()
    print(f"Approved comma artists: {len(known)}")
    print(f"Rejected comma artists: {len(rejected)}")
    print(f"Known comma artists saved to: {args.known_file}")
    print(f"Rejected comma artists saved to: {args.rejected_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Interactively curate comma-containing artist names."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help="Directory containing lastfmstats CSV files and artists.json."
    )
    parser.add_argument(
        "--from-json",
        type=Path,
        help="Read artists from a specific artists.json file instead of CSV files."
    )
    parser.add_argument(
        "--known-file",
        type=Path,
        default=KNOWN_COMMA_ARTISTS_FILE,
        help="Output JSON list of approved comma-containing artist names."
    )
    parser.add_argument(
        "--rejected-file",
        type=Path,
        default=REJECTED_COMMA_ARTISTS_FILE,
        help="Output JSON list of rejected comma-containing artist names."
    )
    args = parser.parse_args()

    curate_comma_artists(args)


if __name__ == '__main__':
    main()
