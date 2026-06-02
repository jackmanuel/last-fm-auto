# evaluation/evaluate_splitting.py
"""
Utility script to evaluate and grid search optimal hyperparameters for splitting artist and track names.
"""
import argparse
import json
import re
import itertools
from thefuzz import process
from last_fm_auto.preprocessing import ARTIST_LIST, DASH_SEPARATOR_PATTERN, expand_abbreviations

_ARTIST_MATCH_CACHE = {}

def extract_artist_match(artist_candidate, artist_list):
    """Caches repeated fuzzy artist lookups during grid search."""
    if artist_candidate not in _ARTIST_MATCH_CACHE:
        _ARTIST_MATCH_CACHE[artist_candidate] = process.extractOne(artist_candidate, artist_list)
    return _ARTIST_MATCH_CACHE[artist_candidate]

def testable_split_artist_track(query, artist_list, threshold, length_ratio_threshold, penalty_factor):
    """A version of the split_artist_track function with tunable hyperparameters."""
    if not artist_list:
        return {"artist": None, "track": query}

    parts = re.split(DASH_SEPARATOR_PATTERN, query, maxsplit=1)
    if len(parts) == 2:
        part1, part2 = parts[0].strip(), parts[1].strip()
        match1, score1, *_ = extract_artist_match(part1, artist_list)
        match2, score2, *_ = extract_artist_match(part2, artist_list)
        if score1 > score2 and score1 >= threshold:
            return {"artist": match1, "track": part2}
        if score2 > score1 and score2 >= threshold:
            return {"artist": match2, "track": part1}

    words = query.split()
    best_match = {"artist": None, "track": query, "score": 0}

    for i in range(1, len(words)):
        track_candidate = " ".join(words[:i])
        artist_candidate = " ".join(words[i:])
        result = extract_artist_match(artist_candidate, artist_list)
        if result:
            match, score, *_ = result
            if len(artist_candidate) * length_ratio_threshold < len(match):
                score *= penalty_factor

            if score > best_match["score"]:
                best_match = {"artist": match, "track": track_candidate, "score": score}

    if best_match["score"] >= threshold and best_match["track"]:
        return {"artist": best_match["artist"], "track": best_match["track"]}

    return {"artist": None, "track": query}

def evaluate_prediction(prediction, ground_truth):
    """Compares a prediction to the ground truth, returns True for a match."""
    pred_artist = prediction.get('artist')
    pred_track = prediction.get('track')
    gt_artist = ground_truth.get('artist')
    gt_track = ground_truth.get('track')

    # Normalize None and empty strings for comparison
    pred_artist = pred_artist if pred_artist else None
    gt_artist = gt_artist if gt_artist else None
    pred_track = pred_track if pred_track else None
    gt_track = gt_track if gt_track else None

    artist_match = _normalized_text(pred_artist) == _normalized_text(gt_artist)
    track_match = _normalized_text(pred_track) == _normalized_text(gt_track)
    
    return artist_match and track_match

def _normalized_text(value):
    """Normalizes text for evaluation comparisons."""
    if value is None:
        return None
    return str(value).strip().casefold()

def evaluate_hyperparameters(ground_truth_data, artist_list):
    """Performs a grid search to find the best hyperparameters."""
    thresholds = [75, 80, 85, 90]
    length_ratio_thresholds = [1.5, 2.0, 2.5]
    penalty_factors = [0.7, 0.8, 0.9]

    param_grid = list(itertools.product(thresholds, length_ratio_thresholds, penalty_factors))
    print(f"Starting grid search: {len(param_grid)} combinations to test.")

    results = []

    for i, (threshold, length_ratio, penalty) in enumerate(param_grid):
        correct_predictions = 0
        for item in ground_truth_data:
            query = expand_abbreviations(item['query'])
            prediction = testable_split_artist_track(query, artist_list, threshold, length_ratio, penalty)
            if evaluate_prediction(prediction, item):
                correct_predictions += 1
        
        accuracy = correct_predictions / len(ground_truth_data)
        params = {
            "threshold": threshold,
            "length_ratio_threshold": length_ratio,
            "penalty_factor": penalty
        }
        results.append((accuracy, params))
        print(f"[{i+1}/{len(param_grid)}] Acc: {accuracy:.2%} | Params: {params}")

    results.sort(key=lambda x: x[0], reverse=True)

    print("\n--- Top 5 Results ---")
    for acc, params in results[:5]:
        print(f"Accuracy: {acc:.2%}, Parameters: {params}")

    print("\n--- Best Parameters Found ---")
    best_accuracy, best_params = results[0]
    print(f"Accuracy: {best_accuracy:.2%}")
    print(f"Parameters: {json.dumps(best_params, indent=4)}")

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate and tune hyperparameters for the artist-track splitting logic."
    )
    parser.add_argument(
        "ground_truth_file",
        type=str,
        help="Path to the JSON file containing ground truth queries and splits."
    )
    args = parser.parse_args()

    try:
        with open(args.ground_truth_file, 'r', encoding='utf-8') as f:
            ground_truth = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: Could not load ground truth file '{args.ground_truth_file}'. {e}")
        return

    if not ARTIST_LIST:
        print("Error: Artist list is empty. Please ensure 'data/artists.json' is populated.")
        return

    evaluate_hyperparameters(ground_truth, ARTIST_LIST)

if __name__ == "__main__":
    main()
