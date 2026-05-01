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
        "--query",
        type=str,
        help="The search query to test, e.g., 'My Song (Music Video)'"
    )
    parser.add_argument(
        "--resolved-title",
        type=str,
        help="The resolved title to use"
    )
    parser.add_argument(
        "--youtube-channel",
        type=str,
        help="The YouTube channel/uploader name to use as a strict artist hint"
    )
    args = parser.parse_args()

    # Validate that at least one argument is provided
    if not args.query and not args.resolved_title:
        parser.error("At least one of --query or --resolved-title must be provided")

    # Use the provided values or fall back to the other if one is missing
    query = args.query if args.query else args.resolved_title
    resolved_title = args.resolved_title if args.resolved_title else args.query

    print(f"--- Running Test Query ---")
    print(f"Input Query: \"{query}\"")
    print(f"Resolved Title: \"{resolved_title}\"")
    if args.youtube_channel:
        print(f"YouTube Channel: \"{args.youtube_channel}\"")
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

    # Execute the pipeline with the provided query and resolved title
    best_match = pipeline.execute(
        original_query=query,
        resolved_title=resolved_title,
        youtube_channel=args.youtube_channel
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
