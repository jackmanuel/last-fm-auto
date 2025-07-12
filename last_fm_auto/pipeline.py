from typing import Optional, Dict, List
from datetime import datetime
from thefuzz import fuzz
from . import lastfm_client
from . import scoring
from . import preprocessing
from . import config

class TrackPipeline:
    """Orchestrates the track matching pipeline with configurable strategies"""
    
    def __init__(self, config: Dict, searchable_tracks: List[Dict]):
        self.config = config
        self.searchable_tracks = searchable_tracks

    @classmethod
    def from_default_config(cls, searchable_tracks: List[Dict]):
        """Creates a TrackPipeline instance using default app configuration."""
        pipeline_config = {
            'LOCAL_SIMILARITY_THRESHOLD': config.LOCAL_SIMILARITY_THRESHOLD,
            'WEIGHT_SIMILARITY': config.WEIGHT_SIMILARITY,
            'WEIGHT_POPULARITY': config.WEIGHT_POPULARITY,
            'POPULARITY_THRESHOLD': config.POPULARITY_THRESHOLD,
            'REJECTION_THRESHOLD': config.REJECTION_THRESHOLD
        }
        return cls(config=pipeline_config, searchable_tracks=searchable_tracks)

    def find_match_in_local_db(self, query: str) -> Optional[Dict]:
        """Searches for a matching track in the local searchable_tracks.json."""
        for track_info in self.searchable_tracks:
            local_track_title = track_info.get("track")
            if not local_track_title:
                continue

            similarity = fuzz.ratio(query.lower(), local_track_title.lower())
            if similarity >= self.config['LOCAL_SIMILARITY_THRESHOLD']:
                print(f"Found suitable track in local DB: '{local_track_title}' (Similarity: {similarity}%)")
                return {"name": local_track_title, "artist": track_info.get("artist")}
        return None

    def _find_best_match_from_api(self, search_term: str) -> Optional[Dict]:
        """Search Last.fm API with error handling and stats tracking"""
        try:
            print(f"Searching Last.fm with query: \"{search_term}\"")
            tracks = lastfm_client.search_track(search_term)
            
            if not tracks:
                return None

            best_track, max_score = scoring.select_best_track(
                search_term,
                tracks,
                weight_similarity=self.config['WEIGHT_SIMILARITY'],
                weight_popularity=self.config['WEIGHT_POPULARITY'],
                popularity_threshold=self.config['POPULARITY_THRESHOLD']
            )

            if best_track and max_score >= self.config['REJECTION_THRESHOLD']:
                print(f"Found best match: '{best_track['name']}' with a score of {max_score:.3f}")
                return best_track
            elif best_track:
                print(f"Rejected '{best_track['name']}' (score {max_score:.3f} < {self.config['REJECTION_THRESHOLD']})")
                return None
                
            return None
        except Exception as e:
            print(f"API search failed for '{search_term}': {str(e)}")
            return None

    def execute(self, original_query: str, resolved_title: str) -> Optional[Dict]:
        """
        Main pipeline entry point. Cleans inputs and tries multiple strategies
        to find the best possible track match.
        """
        # Step 1: Pre-process inputs
        expanded_query = preprocessing.expand_abbreviations(original_query)
        cleaned_query = preprocessing.clean_youtube_title(expanded_query)

        cleaned_resolved_title = preprocessing.clean_youtube_title(resolved_title)

        # Step 2: Check local database first
        local_match = self.find_match_in_local_db(cleaned_query)
        if local_match:
            return local_match

        # Step 3: Determine API search terms
        is_youtube_url = 'youtube.com' in original_query or 'youtu.be' in original_query
        search_terms = [cleaned_resolved_title] if is_youtube_url else [cleaned_query]
        
        # Add resolved_title as a fallback if different
        if not is_youtube_url and cleaned_resolved_title.lower() != cleaned_query.lower():
            search_terms.append(cleaned_resolved_title)

        # Step 4: Execute search against API
        for term in search_terms:
            best_track = self._find_best_match_from_api(term)
            if best_track:
                return best_track
            print(f"Search for '{term}' failed. Trying next fallback if available.")

        print(f"No suitable track found after trying all search terms.")
        return None
