# evaluation/tune_hyperparameters.py
"""
Performs hyperparameter tuning for weighted sum strategies, now including a
rejection threshold.

This script searches a 3D grid of hyperparameters:
  1. w_sim (weight for similarity)
  2. w_listeners (weight for popularity)
  3. rejection_threshold (minimum score to accept a match)

Because the model can reject results, it uses Precision, Recall, and
F1-score as its primary evaluation metrics.
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

def select_best_track_linear(search_query: str, tracks: list, w_sim: float, w_listeners: float) -> tuple[dict | None, float]:
    if not tracks: return None, 0.0
    listeners = [int(t.get('listeners', 0)) for t in tracks]
    max_listeners = max(listeners) if listeners else 0
    best_track, max_score = None, -1
    for i, track in enumerate(tracks):
        norm_sim = fuzz.ratio(search_query.lower(), track.get('name', '').lower()) / 100.0
        norm_listeners = (listeners[i] / max_listeners) if max_listeners > 0 else 0
        score = (w_sim * norm_sim) + (w_listeners * norm_listeners)
        if score > max_score: max_score, best_track = score, track
    return best_track, max_score

def select_best_track_log(search_query: str, tracks: list, w_sim: float, w_listeners: float) -> tuple[dict | None, float]:
    if not tracks: return None, 0.0
    listeners = [np.log1p(int(t.get('listeners', 0))) for t in tracks]
    max_listeners = max(listeners) if listeners else 0
    best_track, max_score = None, -1
    for i, track in enumerate(tracks):
        norm_sim = fuzz.ratio(search_query.lower(), track.get('name', '').lower()) / 100.0
        norm_log_listeners = (listeners[i] / max_listeners) if max_listeners > 0 else 0
        score = (w_sim * norm_sim) + (w_listeners * norm_log_listeners)
        if score > max_score: max_score, best_track = score, track
    return best_track, max_score

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
    
    return df, search_results

def evaluate_hyperparameters(df: pd.DataFrame, search_results: dict, w_sim: float, w_listeners: float, rejection_threshold: float, selection_function: callable) -> tuple[float, float, float, float, list]:
    """
    Evaluates a set of hyperparameters.
    Returns: (precision, recall, f1_score, accuracy, list_of_failures)
    """
    tp, fp, tn, fn = 0, 0, 0, 0
    failures = []

    for _, row in df.iterrows():
        is_gt_valid = pd.notna(row['track_gt'])
        gt_track = str(row['track_gt']).lower().strip() if is_gt_valid else None
        gt_artist = str(row['artist_gt']).lower().strip() if is_gt_valid else None
        gt_track_str = f"{gt_track} by {gt_artist}" if is_gt_valid else "None"
        
        results_data = search_results.get(str(row['id']))
        tracks = results_data.get('results', {}).get('trackmatches', {}).get('track', []) if results_data else []
        
        best_track, score = selection_function(row['cleaned_query'], tracks, w_sim, w_listeners)
        predicted_track = best_track if score >= rejection_threshold else None

        pred_name = predicted_track.get('name', '').lower().strip() if predicted_track else None
        pred_artist = predicted_track.get('artist', '').lower().strip() if predicted_track else None
        pred_track_str = f"{pred_name} by {pred_artist}" if predicted_track else "None"

        if predicted_track:
            if is_gt_valid:
                if pred_name == gt_track and pred_artist == gt_artist:
                    tp += 1
                else:
                    fp += 1
                    failures.append({'query': row['cleaned_query'], 'predicted': pred_track_str, 'ground_truth': gt_track_str, 'type': 'FP'})
            else:
                fp += 1
                failures.append({'query': row['cleaned_query'], 'predicted': pred_track_str, 'ground_truth': gt_track_str, 'type': 'FP'})
        else: # Model predicted nothing
            if is_gt_valid:
                fn += 1
                failures.append({'query': row['cleaned_query'], 'predicted': pred_track_str, 'ground_truth': gt_track_str, 'type': 'FN'})
            else:
                tn += 1
    
    total_samples = tp + fp + tn + fn
    accuracy = (tp + tn) / total_samples if total_samples > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    return precision, recall, f1_score, accuracy, failures

def main():
    STRATEGY_MAP = {'linear': select_best_track_linear, 'log': select_best_track_log}
    parser = argparse.ArgumentParser(description="Tune weighted-sum hyperparameters, including a rejection threshold.")
    parser.add_argument("--ground-truth", required=True, help="Path to the ground truth CSV file.")
    parser.add_argument("--search-results", required=True, help="Path to the cached search results JSON.")
    parser.add_argument("--strategy", choices=STRATEGY_MAP.keys(), default='linear', help="The scoring strategy to use.")
    args = parser.parse_args()

    selection_function = STRATEGY_MAP[args.strategy]
    df, search_results = load_data(args.ground_truth, args.search_results)
    
    # Use resolved_title for YouTube links, otherwise use the original query
    df['search_term'] = df.apply(
        lambda row: str(row['resolved_title']) if str(row['query']).startswith('http') else str(row['query']),
        axis=1
    )
    df['cleaned_query'] = df['search_term'].apply(lambda q: preprocessing.clean_youtube_title(preprocessing.expand_abbreviations(str(q))))
    df['has_local_match'] = df['cleaned_query'].apply(lambda q: pipeline._find_match_in_local_db(q) is not None)
    filtered_df = df[~df['has_local_match']].copy()
    print(f"Tuning with {len(filtered_df)} records (after skipping {len(df) - len(filtered_df)} local matches).")

    # --- 3D Hyperparameter Grid ---
    weights = np.arange(0.0, 1.05, 0.05)
    thresholds = np.arange(0.0, 0.85, 0.05)
    
    best_f1, best_params, best_accuracy, best_failures = -1, None, -1, []

    print("\n--- Hyperparameter Tuning Results ---")
    print(f"{'w_sim':<8}{'w_list':<8}{'thresh':<8}{'Precision':<12}{'Recall':<12}{'F1-Score':<12}{'Accuracy':<12}")
    print("-" * 72)

    for w_sim in weights:
        w_listeners = round(1.0 - w_sim, 2)
        for threshold in thresholds:
            precision, recall, f1, accuracy, failures = evaluate_hyperparameters(filtered_df, search_results, w_sim, w_listeners, threshold, selection_function)
            
            line = f"{w_sim:<8.2f}{w_listeners:<8.2f}{threshold:<8.2f}{precision:<12.2%}{recall:<12.2%}{f1:<12.2%}{accuracy:<12.2%}"
            if f1 > best_f1:
                best_f1 = f1
                best_accuracy = accuracy
                best_params = {'w_sim': w_sim, 'w_listeners': w_listeners, 'threshold': threshold}
                best_failures = failures
                print(f"{line} *")
            else:
                print(line)
    
    print("\n--- Tuning Complete ---")
    if best_params:
        print(f"Strategy: '{args.strategy}'")
        print(f"Best F1-Score: {best_f1:.2%} (Accuracy: {best_accuracy:.2%})")
        print(f"Best Parameters: w_sim={best_params['w_sim']:.2f}, w_listeners={best_params['w_listeners']:.2f}, threshold={best_params['threshold']:.2f}")

    if best_failures:
        print("\n--- Failures for Best Hyperparameters ---")
        for failure in best_failures:
            print(f"\n- Type: {failure['type']}")
            print(f"  - Query:     '{failure['query']}'")
            print(f"  - Predicted: '{failure['predicted']}'")
            print(f"  - Correct:   '{failure['ground_truth']}'")

if __name__ == '__main__':
    main()