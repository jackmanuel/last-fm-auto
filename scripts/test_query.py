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

# Add a check to ensure the package is installed and importable
try:
    from last_fm_auto import pipeline
except ModuleNotFoundError:
    print("Error: The 'last_fm_auto' package was not found.")
    print("Please ensure you have run 'pip install -e .' from the project root.")
    sys.exit(1)

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

    # We call the main pipeline function directly.
    # For a manual query, the original_query and resolved_title are the same.
    best_match = pipeline.find_best_track(
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