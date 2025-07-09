"""
Performs hyperparameter tuning for the "threshold and popularity" track
selection strategy.

This script evaluates the performance of a selection algorithm that first
filters tracks by a minimum similarity threshold and a minimum listener count,
and then selects the most popular track from the valid candidates.

The core logic is as follows:
1.  Load the ground truth data and cached search results.
2.  Exclude queries that have a match in the local `searchable_tracks.json`.
3.  Define a grid of hyperparameters: `similarity_threshold` and `min_listener_count`.
4.  For each combination of parameters:
    a. Iterate through each query in the ground truth set.
    b. Filter search results that are above the similarity threshold.
    c. From those, filter results that are above the listener count threshold.
    d. If any candidates remain, select the one with the most listeners.
    e. Compare the prediction against the ground truth.
5.  Calculate the Precision, Recall, and F1-score for the parameter set.
6.  Identify and report the parameters that yield the highest F1-score.
"""

import pandas as pd
import json
import os
import sys
import numpy as np
from thefuzz import fuzz

# Add project root to path to import from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scrobbler import (
    expand_abbreviations,
    clean_youtube_title,
    load_searchable_tracks,
    SIMILARITY_THRESHOLD as DEFAULT_SIMILARITY_THRESHOLD
)

# Load data needed for the local match check once at the start
SEARCHABLE_TRACKS = load_searchable_tracks()

def has_local_match(query):
    """
    Checks for a matching track in the local searchable_tracks.json without printing.
    Returns True if a suitable match is found, otherwise False.
    """
    for track_info in SEARCHABLE_TRACKS:
        local_track_title = track_info.get("track")
        if not local_track_title:
            continue
        # Use the default project threshold for this check
        if fuzz.ratio(query.lower(), local_track_title.lower()) >= DEFAULT_SIMILARITY_THRESHOLD:
            return True
    return False

def load_data(ground_truth_csv, search_results_json):
    """Loads the ground truth data and search results from files."""
    if not os.path.exists(ground_truth_csv):
        print(f"Error: Ground truth file not found at '{ground_truth_csv}'")
        sys.exit(1)
    if not os.path.exists(search_results_json):
        print(f"Error: Search results file not found at '{search_results_json}'")
        sys.exit(1)

    ground_truth_df = pd.read_csv(ground_truth_csv)
    with open(search_results_json, 'r', encoding='utf-8') as f:
        search_results = json.load(f)
    
    ground_truth_df.dropna(subset=['track_gt', 'artist_gt'], inplace=True)
    return ground_truth_df, search_results

def select_best_track_threshold_strategy(search_query, tracks, sim_threshold, min_listeners):
    """
    Selects the best track using the threshold and popularity strategy.
    """
    if not tracks:
        return None

    # Step 1: Filter by similarity threshold
    candidates = []
    for track in tracks:
        similarity_score = fuzz.ratio(search_query.lower(), track.get('name', '').lower())
        if similarity_score >= sim_threshold:
            candidates.append(track)
    
    if not candidates:
        return None

    # Step 2: Filter by minimum listener count
    final_candidates = []
    for track in candidates:
        if int(track.get('listeners', 0)) >= min_listeners:
            final_candidates.append(track)

    if not final_candidates:
        return None
        
    # Step 3: Select the one with the most listeners
    best_match = sorted(final_candidates, key=lambda t: int(t.get('listeners', 0)), reverse=True)[0]
    
    return best_match

def evaluate_strategy(filtered_ground_truth_df, search_results, sim_threshold, min_listeners):
    """
    Evaluates the threshold strategy and returns precision, recall, and F1-score.
    """
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for _, row in filtered_ground_truth_df.iterrows():
        query_id = str(row['id'])
        original_query = row['query']
        gt_track = str(row['track_gt']).lower().strip()
        gt_artist = str(row['artist_gt']).lower().strip()

        results_data = search_results.get(query_id)
        if not results_data or 'results' not in results_data:
            false_negatives += 1
            continue
        
        tracks = results_data.get('results', {}).get('trackmatches', {}).get('track', [])
        if not tracks:
            false_negatives += 1
            continue

        expanded_query = expand_abbreviations(original_query)
        search_query = clean_youtube_title(expanded_query)

        predicted_track = select_best_track_threshold_strategy(search_query, tracks, sim_threshold, min_listeners)

        if predicted_track:
            pred_track_name = predicted_track.get('name', '').lower().strip()
            pred_artist_name = predicted_track.get('artist', '').lower().strip()
            if pred_track_name == gt_track and pred_artist_name == gt_artist:
                true_positives += 1
            else:
                false_positives += 1
        else:
            # The model predicted nothing, but there was a correct answer
            false_negatives += 1

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return precision, recall, f1_score

def main():
    """
    Main function to run the hyperparameter tuning process.
    """
    ground_truth_csv = os.path.join('evaluation', 'ground_truth_data_v2.csv')
    search_results_json = os.path.join('evaluation', 'last_fm_search_results_0709.json')

    print(f"Using ground truth data: '{ground_truth_csv}'")
    print(f"Using search results: '{search_results_json}'")

    ground_truth_df, search_results = load_data(ground_truth_csv, search_results_json)
    
    print(f"Loaded {len(ground_truth_df)} annotated records.")

    rows_to_keep = [not has_local_match(clean_youtube_title(expand_abbreviations(q))) for q in ground_truth_df['query']]
    filtered_df = ground_truth_df[rows_to_keep]
    
    num_skipped = len(ground_truth_df) - len(filtered_df)
    if num_skipped > 0:
        print(f"Skipping {num_skipped} queries that have a match in local JSON.")
    
    print(f"Starting hyperparameter tuning with {len(filtered_df)} records.")

    # Define the hyperparameter grid
    similarity_thresholds = range(50, 101, 5)
    listener_counts = [0, 100, 500, 1000, 2000, 5000, 10000]
    
    best_f1_score = -1
    best_params = None

    print("\n--- Hyperparameter Tuning Results ---")
    print(f"{'Sim Thresh':<12}{'Min List.':<12}{'Prec.':<9}{'Recall':<9}{'F1':<9}")
    print("-" * 55)

    for sim_thresh in similarity_thresholds:
        for min_list in listener_counts:
            precision, recall, f1_score = evaluate_strategy(
                filtered_df, search_results, sim_thresh, min_list
            )
            
            print(f"{sim_thresh:<12}{min_list:<12}{precision:<9.2%}{recall:<9.2%}{f1_score:<9.2%}")

            if f1_score > best_f1_score:
                best_f1_score = f1_score
                best_params = {'sim_threshold': sim_thresh, 'min_listeners': min_list}

    print("\n--- Tuning Complete ---")
    if best_params:
        print(f"Best F1-Score: {best_f1_score:.2%}")
        print(f"Best Parameters: Similarity Threshold = {best_params['sim_threshold']}, "
              f"Min Listeners = {best_params['min_listeners']}")
    else:
        print("Could not determine best parameters.")

if __name__ == '__main__':
    main()
