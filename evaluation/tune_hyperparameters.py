
"""
Performs hyperparameter tuning to find the optimal weights for the
scrobbler's track selection algorithm using a weighted scoring model.

This script reads a ground truth dataset and pre-fetched Last.fm search
results. It then iterates through various weight combinations for similarity
and listener count to find the combination that yields the highest accuracy.

Queries that have a match in the local `searchable_tracks.json` are
excluded from this evaluation to ensure the tuning is focused on the
Last.fm search logic.
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
    SIMILARITY_THRESHOLD
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

        similarity_score = fuzz.ratio(query.lower(), local_track_title.lower())
        if similarity_score >= SIMILARITY_THRESHOLD:
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

def select_best_track(search_query, tracks, w_sim, w_listeners):
    """
    Selects the best track from a list of search results based on a weighted score.
    """
    if not tracks:
        return None

    listeners = [int(track.get('listeners', 0)) for track in tracks]
    max_listeners = max(listeners) if listeners else 0

    best_track = None
    max_score = -1

    for i, track in enumerate(tracks):
        similarity_score = fuzz.ratio(search_query.lower(), track.get('name', '').lower())
        norm_sim = similarity_score / 100.0

        current_listeners = int(listeners[i])
        norm_listeners = (current_listeners / max_listeners) if max_listeners > 0 else 0
        
        score = (w_sim * norm_sim) + (w_listeners * norm_listeners)

        if score > max_score:
            max_score = score
            best_track = track
            
    return best_track

def evaluate_hyperparameters(filtered_ground_truth_df, search_results, w_sim, w_listeners):
    """
    Evaluates a set of hyperparameters on a pre-filtered dataset.
    """
    correct_predictions = 0
    total_predictions = 0

    for _, row in filtered_ground_truth_df.iterrows():
        query_id = str(row['id'])
        original_query = row['query']
        gt_track = str(row['track_gt']).lower().strip()
        gt_artist = str(row['artist_gt']).lower().strip()

        results_data = search_results.get(query_id)
        if not results_data or 'results' not in results_data:
            continue
        
        tracks = results_data.get('results', {}).get('trackmatches', {}).get('track', [])
        if not tracks:
            continue

        total_predictions += 1
        
        expanded_query = expand_abbreviations(original_query)
        search_query = clean_youtube_title(expanded_query)

        predicted_track = select_best_track(search_query, tracks, w_sim, w_listeners)

        if predicted_track:
            pred_track_name = predicted_track.get('name', '').lower().strip()
            pred_artist_name = predicted_track.get('artist', '').lower().strip()

            if pred_track_name == gt_track and pred_artist_name == gt_artist:
                correct_predictions += 1
    
    accuracy = (correct_predictions / total_predictions) * 100 if total_predictions > 0 else 0
    return accuracy

def main():
    """
    Main function to run the hyperparameter tuning process.
    """
    ground_truth_csv = os.path.join('evaluation', 'ground_truth_data_v2.csv')
    search_results_json = os.path.join('evaluation', 'last_fm_search_results_0709.json')

    ground_truth_df, search_results = load_data(ground_truth_csv, search_results_json)
    
    print(f"Loaded {len(ground_truth_df)} annotated records.")

    # Pre-filter the DataFrame to exclude queries that have a local match
    rows_to_keep = []
    for _, row in ground_truth_df.iterrows():
        expanded_query = expand_abbreviations(row['query'])
        search_query = clean_youtube_title(expanded_query)
        if not has_local_match(search_query):
            rows_to_keep.append(True)
        else:
            rows_to_keep.append(False)
            
    filtered_df = ground_truth_df[rows_to_keep]
    
    num_skipped = len(ground_truth_df) - len(filtered_df)
    if num_skipped > 0:
        print(f"Skipping {num_skipped} queries that have a match in local JSON.")
    
    print(f"Starting hyperparameter tuning with {len(filtered_df)} records.")
    
    weights = np.arange(0.0, 1.05, 0.05)
    
    best_accuracy = -1
    best_weights = None

    print("\n--- Hyperparameter Tuning Results ---")
    for w_sim in weights:
        w_listeners = 1.0 - w_sim
        
        accuracy = evaluate_hyperparameters(filtered_df, search_results, w_sim, w_listeners)
        
        print(f"w_sim: {w_sim:.2f}, w_listeners: {w_listeners:.2f} -> Accuracy: {accuracy:.2f}%")

        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_weights = (w_sim, w_listeners)

    print("\n--- Tuning Complete ---")
    if best_weights:
        print(f"Best Accuracy (on {len(filtered_df)} items): {best_accuracy:.2f}%")
        print(f"Best Weights: w_sim = {best_weights[0]:.2f}, w_listeners = {best_weights[1]:.2f}")
    else:
        print("Could not determine best weights.")

if __name__ == '__main__':
    main()
