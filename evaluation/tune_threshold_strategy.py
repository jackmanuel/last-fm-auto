# evaluation/tune_threshold_strategy.py
"""
Performs hyperparameter tuning for the "threshold and popularity" track
selection strategy.

This script evaluates a selection algorithm that first filters tracks by a
minimum similarity threshold and a minimum listener count, and then selects
the most popular track from the valid candidates.

It correctly handles ground truth entries where the correct outcome is to
find NO match (i.e., blank 'track_gt'). It uses Precision, Recall, and
F1-score as its primary evaluation metrics.
"""
import pandas as pd
import json
import sys
import argparse
from thefuzz import fuzz

# Cleanly import from the installed 'last_fm_auto' package
from last_fm_auto import preprocessing
from last_fm_auto import pipeline

def load_data(ground_truth_csv: str, search_results_json: str) -> tuple[pd.DataFrame, dict]:
    """Loads and prepares the ground truth and search results data."""
    try:
        df = pd.read_csv(ground_truth_csv)
        with open(search_results_json, 'r', encoding='utf-8') as f:
            search_results = json.load(f)
    except FileNotFoundError as e:
        print(f"Error: A required file was not found. Details: {e}")
        sys.exit(1)
    
    # DO NOT dropna here, as null ground truth values are valid test cases.
    return df, search_results

def select_best_track_threshold(search_query: str, tracks: list, sim_threshold: int, min_listeners: int) -> dict | None:
    """Selects the best track using the threshold and popularity strategy."""
    if not tracks:
        return None

    candidates = [t for t in tracks if fuzz.ratio(search_query.lower(), t.get('name', '').lower()) >= sim_threshold]
    if not candidates:
        return None

    final_candidates = [t for t in candidates if int(t.get('listeners', 0)) >= min_listeners]
    if not final_candidates:
        return None
        
    return max(final_candidates, key=lambda t: int(t.get('listeners', 0)))

def evaluate_strategy(df: pd.DataFrame, search_results: dict, sim_threshold: int, min_listeners: int) -> tuple[float, float, float, float]:
    """
    Evaluates the threshold strategy, handling null ground truths correctly.
    Returns (precision, recall, f1_score, accuracy).
    """
    true_positives, false_positives, true_negatives, false_negatives = 0, 0, 0, 0

    for _, row in df.iterrows():
        query_id = str(row['id'])
        search_query = row['cleaned_query']
        
        is_gt_valid = pd.notna(row['track_gt']) and pd.notna(row['artist_gt'])
        gt_track = str(row['track_gt']).lower().strip() if is_gt_valid else None
        gt_artist = str(row['artist_gt']).lower().strip() if is_gt_valid else None

        results_data = search_results.get(query_id)
        tracks = results_data.get('results', {}).get('trackmatches', {}).get('track', []) if results_data else []
        
        predicted_track = select_best_track_threshold(search_query, tracks, sim_threshold, min_listeners)

        if predicted_track: # Model made a prediction
            if is_gt_valid: # And a correct answer exists
                pred_track_name = predicted_track.get('name', '').lower().strip()
                pred_artist_name = predicted_track.get('artist', '').lower().strip()
                if pred_track_name == gt_track and pred_artist_name == gt_artist:
                    true_positives += 1
                else:
                    false_positives += 1
            else: # Model predicted something, but it should have predicted nothing
                false_positives += 1
        else: # Model predicted nothing
            if is_gt_valid: # Model should have made a prediction
                false_negatives += 1
            else: # Model correctly predicted nothing
                true_negatives += 1

    # Calculate metrics
    total_samples = len(df)
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (true_positives + true_negatives) / total_samples if total_samples > 0 else 0
    
    return precision, recall, f1_score, accuracy

def main():
    """Main function to run the hyperparameter tuning process."""
    parser = argparse.ArgumentParser(description="Tune hyperparameters for the threshold and popularity strategy.")
    parser.add_argument("--ground-truth", required=True, help="Path to the ground truth CSV file.")
    parser.add_argument("--search-results", required=True, help="Path to the cached search results JSON.")
    args = parser.parse_args()

    df, search_results = load_data(args.ground_truth, args.search_results)
    print(f"Loaded {len(df)} records for evaluation (including null ground truths).")

    # Pre-process and filter data
    df['cleaned_query'] = df['resolved_title'].apply(lambda q: preprocessing.clean_youtube_title(str(q)))
    df['has_local_match'] = df['cleaned_query'].apply(lambda q: pipeline.TrackPipeline.from_default_config([]).find_match_in_local_db(q, verbose=False) is not None)
    
    filtered_df = df[~df['has_local_match']].copy()
    print(f"Skipping {len(df) - len(filtered_df)} queries with a local DB match.")
    print(f"Starting tuning with {len(filtered_df)} records.")

    # Define the hyperparameter grid
    similarity_thresholds = range(50, 101, 5)
    listener_counts = [0, 10, 20, 30, 50, 75, 100, 500, 1000, 2000, 5000, 10000, 20000]
    
    best_f1_score, best_params = -1, None

    print("\n--- Hyperparameter Tuning Results (Threshold Strategy) ---")
    print(f"{'Sim Thresh':<12}{'Min List.':<12}{'Precision':<12}{'Recall':<12}{'F1-Score':<12}{'Accuracy':<12}")
    print("-" * 72)

    for sim_thresh in similarity_thresholds:
        for min_list in listener_counts:
            precision, recall, f1_score, accuracy = evaluate_strategy(filtered_df, search_results, sim_thresh, min_list)
            print(f"{sim_thresh:<12}{min_list:<12}{precision:<12.2%}{recall:<12.2%}{f1_score:<12.2%}{accuracy:<12.2%}")

            if f1_score > best_f1_score:
                best_f1_score = f1_score
                best_params = {'sim_threshold': sim_thresh, 'min_listeners': min_list}

    print("\n--- Tuning Complete ---")
    if best_params:
        print(f"Best F1-Score: {best_f1_score:.2%}")
        print(f"Best Parameters: Similarity Threshold = {best_params['sim_threshold']}, Min Listeners = {best_params['min_listeners']}")

if __name__ == '__main__':
    main()