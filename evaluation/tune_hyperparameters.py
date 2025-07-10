# evaluation/tune_hyperparameters.py
"""
Performs hyperparameter tuning to find the optimal weights for the
scrobbler's track selection algorithm.

This single, unified script supports multiple scoring strategies, selectable
via the command line. It reads a ground truth dataset and pre-fetched
search results, then iterates through weight combinations to find the
one that yields the highest accuracy for the chosen strategy.

Supported Strategies:
  - linear: A standard weighted sum of similarity and listener count.
  - log:    A weighted sum using logarithmically scaled listener counts to
            reduce the dominance of ultra-popular tracks.
"""
import pandas as pd
import json
import sys
import numpy as np
import argparse
from thefuzz import fuzz

from last_fm_auto import preprocessing
from last_fm_auto import pipeline

# --- Scoring Strategy Functions ---

def select_best_track_linear(search_query: str, tracks: list, w_sim: float, w_listeners: float) -> dict | None:
    """Selects the best track using a linear weighted score."""
    if not tracks:
        return None

    listeners = [int(track.get('listeners', 0)) for track in tracks]
    max_listeners = max(listeners) if listeners else 0
    best_track, max_score = None, -1

    for i, track in enumerate(tracks):
        norm_sim = fuzz.ratio(search_query.lower(), track.get('name', '').lower()) / 100.0
        norm_listeners = (listeners[i] / max_listeners) if max_listeners > 0 else 0
        score = (w_sim * norm_sim) + (w_listeners * norm_listeners)

        if score > max_score:
            max_score, best_track = score, track
            
    return best_track

def select_best_track_log(search_query: str, tracks: list, w_sim: float, w_listeners: float) -> dict | None:
    """Selects the best track using a log-scaled weighted score."""
    if not tracks:
        return None

    listeners = [np.log1p(int(track.get('listeners', 0))) for track in tracks]
    max_listeners = max(listeners) if listeners else 0
    best_track, max_score = None, -1

    for i, track in enumerate(tracks):
        norm_sim = fuzz.ratio(search_query.lower(), track.get('name', '').lower()) / 100.0
        norm_log_listeners = (listeners[i] / max_listeners) if max_listeners > 0 else 0
        score = (w_sim * norm_sim) + (w_listeners * norm_log_listeners)

        if score > max_score:
            max_score, best_track = score, track
            
    return best_track

# --- Main Evaluation Logic ---

def load_data(ground_truth_csv: str, search_results_json: str) -> tuple[pd.DataFrame, dict]:
    """Loads and prepares the ground truth and search results data."""
    try:
        df = pd.read_csv(ground_truth_csv)
        with open(search_results_json, 'r', encoding='utf-8') as f:
            search_results = json.load(f)
    except FileNotFoundError as e:
        print(f"Error: A required file was not found. Details: {e}")
        sys.exit(1)
    
    df.dropna(subset=['track_gt', 'artist_gt'], inplace=True)
    return df, search_results

def evaluate_hyperparameters(df: pd.DataFrame, search_results: dict, w_sim: float, w_listeners: float, selection_function: callable) -> float:
    """Evaluates a set of hyperparameters using a given selection function."""
    correct_predictions = 0

    for _, row in df.iterrows():
        query_id = str(row['id'])
        search_query = row['cleaned_query']
        gt_track = str(row['track_gt']).lower().strip()
        gt_artist = str(row['artist_gt']).lower().strip()

        results_data = search_results.get(query_id)
        tracks = results_data.get('results', {}).get('trackmatches', {}).get('track', []) if results_data else []

        predicted_track = selection_function(search_query, tracks, w_sim, w_listeners)

        if predicted_track:
            pred_track_name = predicted_track.get('name', '').lower().strip()
            pred_artist_name = predicted_track.get('artist', '').lower().strip()
            if pred_track_name == gt_track and pred_artist_name == gt_artist:
                correct_predictions += 1
    
    return (correct_predictions / len(df)) * 100 if not df.empty else 0

def main():
    """Main function to run the hyperparameter tuning process."""
    STRATEGY_MAP = {
        'linear': select_best_track_linear,
        'log': select_best_track_log
    }

    parser = argparse.ArgumentParser(description="Tune hyperparameters for the track selection model.")
    parser.add_argument("--ground-truth", required=True, help="Path to the ground truth CSV file.")
    parser.add_argument("--search-results", required=True, help="Path to the cached search results JSON.")
    parser.add_argument(
        "--strategy",
        choices=STRATEGY_MAP.keys(),
        default='linear',
        help="The scoring strategy to use for tuning."
    )
    args = parser.parse_args()

    selection_function = STRATEGY_MAP[args.strategy]
    df, search_results = load_data(args.ground_truth, args.search_results)
    
    print(f"Loaded {len(df)} annotated records.")
    print(f"Using '{args.strategy}' scoring strategy.")

    # Pre-process and filter data
    df['cleaned_query'] = df['query'].apply(lambda q: preprocessing.clean_youtube_title(preprocessing.expand_abbreviations(str(q))))
    df['has_local_match'] = df['cleaned_query'].apply(lambda q: pipeline._find_match_in_local_db(q) is not None)
    
    filtered_df = df[~df['has_local_match']].copy()
    print(f"Skipping {len(df) - len(filtered_df)} queries with a local DB match.")
    print(f"Starting tuning with {len(filtered_df)} records.")
    
    # Run tuning loop
    weights = np.arange(0.0, 1.05, 0.05)
    best_accuracy, best_weights = -1, None

    for w_sim in weights:
        w_listeners = 1.0 - w_sim
        accuracy = evaluate_hyperparameters(filtered_df, search_results, w_sim, w_listeners, selection_function)
        print(f"w_sim: {w_sim:.2f}, w_listeners: {w_listeners:.2f} -> Accuracy: {accuracy:.2f}%")

        if accuracy > best_accuracy:
            best_accuracy, best_weights = accuracy, (w_sim, w_listeners)

    print("\n--- Tuning Complete ---")
    if best_weights:
        print(f"Strategy: '{args.strategy}'")
        print(f"Best Accuracy (on {len(filtered_df)} items): {best_accuracy:.2f}%")
        print(f"Best Weights: w_sim = {best_weights[0]:.2f}, w_listeners = {best_weights[1]:.2f}")

if __name__ == '__main__':
    main()