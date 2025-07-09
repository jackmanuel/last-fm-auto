"""Fetches Last.fm search results for each query in a ground truth CSV file
and saves the raw API responses to a JSON file.

This script is designed to gather the data needed for evaluating different
search result selection algorithms. It iterates through a given CSV,
processes each query, and stores the complete JSON response from the
Last.fm API."""

import pandas as pd
import requests
import json
import os
import sys
import time
import re

# Add the project's root directory to the Python path to allow importing
# modules from the parent directory (e.g., lastfm_auth, scrobbler).
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lastfm_auth import get_last_fm_api_key
from scrobbler import expand_abbreviations, clean_youtube_title, LAST_FM_API_URL, LAST_FM_SEARCH_LIMIT

def is_youtube_url(query):
    """Checks if a query string is a YouTube URL."""
    if not isinstance(query, str):
        return False
    youtube_regex = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+'
    return re.match(youtube_regex, query)

def fetch_raw_search_results(api_key, title):
    """
    Searches the Last.fm API for a given title and returns the raw JSON response.
    """
    params = {
        'method': 'track.search',
        'track': title,
        'api_key': api_key,
        'format': 'json',
        'limit': LAST_FM_SEARCH_LIMIT
    }
    try:
        response = requests.get(LAST_FM_API_URL, params=params)
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
    """
    input_csv_path = os.path.join('evaluation', 'ground_truth_data_v1.csv')
    output_json_path = os.path.join('evaluation', f'last_fm_search_results_{time.strftime("%m%d")}.json')

    if not os.path.exists(input_csv_path):
        print(f"Error: Input file not found at '{input_csv_path}'")
        sys.exit(1)

    try:
        api_key = get_last_fm_api_key()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    df = pd.read_csv(input_csv_path)
    all_results = {}
    total_rows = len(df)

    print(f"Starting to fetch search results for {total_rows} queries...")

    for index, row in df.iterrows():
        query_id = row['id']
        original_query = row['query']

        print(f"Processing record {index + 1}/{total_rows} (ID: {query_id})... ", end="")

        if is_youtube_url(original_query):
            print("Skipped (YouTube URL).")
            continue

        # Process the query using the same logic as the scrobbler
        expanded_query = expand_abbreviations(original_query)
        search_query = clean_youtube_title(expanded_query)

        # Fetch the raw search results from the API
        results = fetch_raw_search_results(api_key, search_query)
        all_results[query_id] = results
        
        print(f"Done. Fetched results for '{search_query}'.")

        # Be respectful to the API endpoint
        time.sleep(1)

    # Save all the results to a single JSON file
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=4)

    print(f"\nProcess complete.")
    print(f"Saved {len(all_results)} search results to '{output_json_path}'.")


if __name__ == '__main__':
    main()
