# Scrobbler Evaluation and Tuning

This directory contains scripts for evaluating and fine-tuning the track selection logic of the Last.fm scrobbler. The goal is to find the optimal parameters that result in the most accurate track matching.

## Core Files

- `ground_truth_data_vX.csv`: A manually annotated CSV file that serves as the "correct answer" key for our tests. It contains queries and their corresponding ground truth track and artist names.
- `last_fm_search_results_XXXX.json`: A cached JSON file containing the raw Last.fm API search results for each query in the ground truth file. This prevents us from hitting the API repeatedly during tuning.

## Tuning Strategies

There are two different scripts for tuning two distinct track selection strategies.

### 1. Weighted Scoring Model (`tune_hyperparameters.py`)

This script tunes a flexible, weighted scoring model.

- **Logic**: It calculates a score for every search result based on a weighted sum of normalized similarity and listener count. The track with the highest score is chosen.
  ```
  score = (w_sim * normalized_similarity) + (w_listeners * normalized_listeners)
  ```
- **Tuning**: It finds the best balance between the similarity score (`w_sim`) and the listener count (`w_listeners`).
- **When to Use**: This model is useful for finding a nuanced balance between how much the title needs to match versus how popular a track is.

### 2. Threshold & Popularity Model (`tune_threshold_strategy.py`)

This script tunes the classic, more rigid selection strategy.

- **Logic**: It uses a multi-step filtering process:
  1.  Keep only tracks that are above a hard `similarity_threshold`.
  2.  From that list, keep only tracks that are above a hard `min_listener_count`.
  3.  From the final candidates, select the one with the most listeners.
- **Tuning**: It finds the best `similarity_threshold` and `min_listener_count` to maximize the F1-score, which balances finding correct tracks and rejecting incorrect ones.
- **When to Use**: This model is better if you want to enforce strict, non-negotiable rules for what constitutes a valid match.

## How to Customize the Tuning

In both tuning scripts, you can easily modify the search space for the hyperparameters.

- **`tune_hyperparameters.py`**:
  - To change the weight increments, modify the `weights` numpy array in the `main()` function:
    ```python
    # Before: 0.05 increments
    weights = np.arange(0.0, 1.05, 0.05)

    # After: 0.01 for a finer search
    weights = np.arange(0.0, 1.01, 0.01)
    ```

- **`tune_threshold_strategy.py`**:
  - To change the search intervals for the thresholds, modify the `similarity_thresholds` and `listener_counts` lists in the `main()` function:
    ```python
    # Before
    similarity_thresholds = range(50, 101, 5)
    listener_counts = [0, 100, 500, 1000, 2000, 5000, 10000]

    # After: Tighter range for similarity, different listener tiers
    similarity_thresholds = range(65, 86, 1) # Search between 65 and 85
    listener_counts = [1000, 1500, 2000, 3000]
    ```

## Helper Scripts

- **`fetch_search_results.py`**: Run this script to populate the `last_fm_search_results_XXXX.json` file by calling the Last.fm API for every query in your ground truth CSV.
- **`annotate_data.py`**: An interactive script to help you efficiently create your `ground_truth_data.csv` file by automating the process of running test queries and prompting you for the correct answer.
