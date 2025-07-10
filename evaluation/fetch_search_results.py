# evaluation/fetch_search_results.py
"""
Fetches Last.fm search results for each query in a ground truth CSV file
and saves the raw API responses to a JSON file.

This script uses the main application's configuration and preprocessing logic
to ensure that the fetched data accurately reflects what the scrobbler would see.
"""
import pandas as pd
import requests
import json
import time
import argparse
import sys
from last_fm_auto import config
from last_fm_auto import preprocessing

def _fetch_raw_search_results(api_key: str, title: str) -> dict:
    """
    Searches the Last.fm API for a given title and returns the raw JSON response.
    """
    params = {
        'method': 'track.search',
        'track': title,
        'api_key': api_key,
        'format': 'json',
        'limit': config.LAST_FM_SEARCH_LIMIT
    }
    try:
        response = requests.get(config.LAST_FM_API_URL, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        return response.json()
    except requests.RequestException as e:
        print(f"API request error for title '{title}': {e}")
        return {"error": str(e)}
    except json.JSONDecodeError:
        print(f"Failed to parse JSON for title '{title}'.")
        return {"error": "JSONDecodeError"}

def main():
    """
    Main function to drive the data fetching and saving process.
    Reads file paths from command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Fetch Last.fm search results for a ground truth file.")
    parser.add_argument(
        "--input-csv",
        required=True,
        help="Path to the input ground truth CSV file."
    )
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path for the output JSON file where results will be saved."
    )
    parser.add_argument(
        "--query-column",
        default="query",
        help="The name of the column in the CSV containing the raw query to process."
    )
    parser.add_argument(
        "--id-column",
        default="id",
        help="The name of the column in the CSV containing the unique ID for each query."
    )
    args = parser.parse_args()

    try:
        df = pd.read_csv(args.input_csv)
    except FileNotFoundError:
        print(f"Error: Input file not found at '{args.input_csv}'")
        sys.exit(1)

    api_key = config.LAST_FM_API_KEY
    if not api_key:
        print("Error: LAST_FM_API_KEY not found. Please check your .env configuration.")
        sys.exit(1)

    all_results = {}
    total_rows = len(df)

    print(f"Starting to fetch search results for {total_rows} queries from '{args.input_csv}'...")

    for index, row in df.iterrows():
        query_id = row[args.id_column]
        original_query = row[args.query_column]

        expanded_query = preprocessing.expand_abbreviations(str(original_query))
        search_query = preprocessing.clean_youtube_title(expanded_query)
        
        print(f"Processing {index + 1}/{total_rows} (ID: {query_id}): Searching for '{search_query}'")

        results = _fetch_raw_search_results(api_key, search_query)
        all_results[str(query_id)] = results
        
        # Be respectful to the API endpoint by waiting between requests
        time.sleep(1)

    # Save all the results to the specified output file
    with open(args.output_json, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=4)

    print(f"\nProcess complete.")
    print(f"Saved {len(all_results)} search results to '{args.output_json}'.")

if __name__ == '__main__':
    main()