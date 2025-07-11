# last_fm_auto/scoring.py
"""
Provides the core track scoring and selection logic.
This module centralizes the algorithm for choosing the best track from a list
of candidates based on similarity and popularity, ensuring that both the main
pipeline and the evaluation scripts use the same logic.
"""
from thefuzz import fuzz

def _print_track_info(i, track, similarity_score, score):
    track_name = track.get('name', '')
    artist_name = track.get('artist', '')
    listeners = track.get('listeners', 0)

    TRACK_WIDTH = 50
    ARTIST_WIDTH = 30
    SIM_WIDTH = 12
    LISTENERS_WIDTH = 10
    SCORE_WIDTH = 8

    # Truncate track and artist names if they are too long
    display_track = (track_name[:TRACK_WIDTH-5] + '...') if len(track_name) > TRACK_WIDTH else track_name
    display_artist = (artist_name[:ARTIST_WIDTH-5] + '...') if len(artist_name) > ARTIST_WIDTH else artist_name


    if i == 0:
        print(f"{'Track':<{TRACK_WIDTH}} {'Artist':<{ARTIST_WIDTH}} {'Similarity':<{SIM_WIDTH}} {'Listeners':<{LISTENERS_WIDTH}} {'Score':<{SCORE_WIDTH}}")
        print("-" * (TRACK_WIDTH + ARTIST_WIDTH + SIM_WIDTH + LISTENERS_WIDTH + SCORE_WIDTH + 4))

    print(f"{display_track:<{TRACK_WIDTH}} "
            f"{display_artist:<{ARTIST_WIDTH}} "
            f"{similarity_score:<{SIM_WIDTH}.0f} "
            f"{listeners:<{LISTENERS_WIDTH}} "
            f"{score:<{SCORE_WIDTH}.3f}")


def _calculate_similarity(query: str, track_name: str, artist_name: str) -> float:
    """Calculates the fuzzy string matching similarity score."""
    query_lower = query.lower()
    track_name_lower = track_name.lower()
    artist_name_lower = artist_name.lower()

    sim_track_only = fuzz.ratio(query_lower, track_name_lower)
    sim_artist_track = fuzz.ratio(query_lower, f"{artist_name_lower} {track_name_lower}")
    sim_track_artist = fuzz.ratio(query_lower, f"{track_name_lower} {artist_name_lower}")
    
    return max(sim_track_only, sim_artist_track, sim_track_artist)

def select_best_track(
    search_query: str,
    tracks: list,
    weight_similarity: float,
    weight_popularity: float,
    popularity_threshold: int,
    listener_transform: callable = lambda x: x,
    print_info: bool = True
) -> tuple[dict | None, float]:
    """
    Selects the best track from a list based on a weighted score of similarity and popularity.
    Args:
        search_query: The user's search query.
        tracks: A list of track dictionaries from the Last.fm API.
        weight_similarity: The weight for the similarity score.
        weight_popularity: The weight for the popularity score.
        popularity_threshold: The minimum number of listeners for a track to be considered.
        listener_transform: A function to transform listener counts before normalization (e.g., np.log1p).
    Returns:
        A tuple containing the best track dictionary and its calculated score.
        Returns (None, -1) if no suitable track is found.
    """
    if not tracks:
        return None, -1

    popular_tracks = [t for t in tracks if int(t.get('listeners', 0)) >= popularity_threshold]
    if not popular_tracks:
        return None, -1

    transformed_listeners = [listener_transform(int(t.get('listeners', 0))) for t in popular_tracks]
    max_listeners = max(transformed_listeners) if transformed_listeners else 0

    best_track = None
    max_score = -1

    for i, track in enumerate(popular_tracks):
        track_name = track.get('name', '')
        artist_name = track.get('artist', '')

        similarity_score = _calculate_similarity(search_query, track_name, artist_name)
        norm_sim = similarity_score / 100.0
        
        norm_listeners = (transformed_listeners[i] / max_listeners) if max_listeners > 0 else 0
        
        score = (weight_similarity * norm_sim) + (weight_popularity * norm_listeners)

        if print_info: 
            _print_track_info(i, track, similarity_score, score)

        if score > max_score:
            max_score = score
            best_track = track
            
    return best_track, max_score
