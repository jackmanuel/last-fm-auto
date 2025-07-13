# scripts/test_query.py
"""
A command-line utility to test the project's core matching pipeline with a
single query string.

This script provides a way to see the step-by-step logic and the final
result for any given input, which is invaluable for debugging and
understanding the model's behavior.
"""
import argparse
import sys
import json
from last_fm_auto import config
from last_fm_auto.pipeline import TrackPipeline

def main():
    """
    Parses command-line arguments and runs a single query through the pipeline.
    """
    parser = argparse.ArgumentParser(
        description="Run a single test query through the track matching pipeline."
    )
    parser.add_argument(
        "query_string",
        type=str,
        help="The search query to test, e.g., 'My Song (Music Video)'"
    )
    args = parser.parse_args()

    print(f"--- Running Test Query ---")
    print(f"Input: \"{args.query_string}\"")
    print("-" * 26)

    # Load searchable tracks from the local JSON file
    try:
        with open(config.LOCAL_TRACKS_FILE, 'r', encoding='utf-8') as f:
            searchable_tracks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading searchable tracks: {e}")
        sys.exit(1)

    # Instantiate the pipeline using the default configuration
    pipeline = TrackPipeline.from_default_config(searchable_tracks=searchable_tracks)

    # For a manual query, the original_query and resolved_title are the same.
    best_match = pipeline.execute(
        original_query=args.query_string,
        resolved_title=args.query_string
    )

    print("-" * 26)
    print("--- Final Result ---")
    if best_match:
        print(f"  Track:  {best_match.get('name')}")
        print(f"  Artist: {best_match.get('artist')}")
    else:
        print("  No suitable match was found by the pipeline.")
    print("-" * 26)

if __name__ == "__main__":
    main()
