from typing import Optional, Dict, List
from datetime import datetime
from thefuzz import fuzz
from . import lastfm_client
from . import scoring
from . import preprocessing
from . import config
from .logger import log

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
            'POPULARITY_THRESHOLD': config.POPULARITY_THRESHOLD
        }
        return cls(config=pipeline_config, searchable_tracks=searchable_tracks)

    def find_match_in_local_db(self, track: str, artist: Optional[str] = None, verbose: bool = True) -> Optional[Dict]:
        """Searches for the best matching track in the local searchable_tracks.json."""
        best_match = None
        max_similarity = 0
        
        query_for_log = f"{artist} - {track}" if artist else track
        if verbose:
            log.info(f'Searching local DB for query: "{query_for_log}"')

        for track_info in self.searchable_tracks:
            local_track_title = track_info.get("track")
            local_track_artist = track_info.get("artist")
            if not local_track_title or not local_track_artist:
                continue

            if artist:
                # If we have a split query, match artist and track separately
                artist_similarity = fuzz.ratio(artist, local_track_artist)
                track_similarity = fuzz.ratio(track, local_track_title)
                # Combine scores (giving more weight to track)
                similarity = (0.4 * artist_similarity) + (0.6 * track_similarity)
            else:
                # Fallback to original method if no artist was split
                similarity = scoring.calculate_similarity(track, local_track_title, local_track_artist)

            if similarity > max_similarity:
                max_similarity = similarity
                best_match = {"name": local_track_title, "artist": local_track_artist}

        if best_match and max_similarity >= config.LOCAL_SIMILARITY_THRESHOLD:
            log.info(
                f"Found suitable track in local DB for '{query_for_log}': "
                f"'{best_match['name']}', '{best_match['artist']}' "
                f"(Similarity: {max_similarity:.2f}%)"
            )
            return best_match
        
        if verbose:
            log.info(f"No suitable match found for '{query_for_log}' locally.")
        return None

    def _find_best_match_from_api(self, track: str, artist: Optional[str] = None) -> Optional[Dict]:
        """Search Last.fm API with error handling and stats tracking"""
        try:
            search_query = f"{artist} - {track}" if artist else track
            log.info(f'Searching Last.fm with query: "{search_query}"')
            tracks = lastfm_client.search_track(track, artist=artist)

            if not tracks:
                return None

            best_track, max_score = scoring.select_best_track(
                search_query,
                tracks,
                weight_similarity=self.config['WEIGHT_SIMILARITY'],
                weight_popularity=self.config['WEIGHT_POPULARITY'],
                popularity_threshold=self.config['POPULARITY_THRESHOLD']
            )

            if best_track:
                log.info(f"Found best match: '{best_track['name']}' with a score of {max_score:.3f}")
                return best_track

            return None
        except Exception as e:
            log.error(f"API search failed for '{search_query}': {str(e)}")
            return None
        
    def execute(self, original_query: str, resolved_title: str, verbose: bool = True) -> Optional[Dict]:
        """
        Main pipeline entry point. Cleans inputs and tries multiple strategies
        to find the best possible track match.
        """
        # Step 1: Pre-process inputs
        expanded_query = preprocessing.expand_abbreviations(original_query)
        cleaned_query = preprocessing.clean_youtube_title(expanded_query)

        cleaned_resolved_title = preprocessing.clean_youtube_title(resolved_title)

        # Step 2: Split query and try precise search with artist/track
        log.info(f"Attempting to split query '{cleaned_query}' into track and artist.")
        split_query = preprocessing.split_artist_track(cleaned_query, preprocessing.ARTIST_LIST)
        
        if split_query.get("artist"):
            log.info(f"Query split into Artist: '{split_query['artist']}' and Track: '{split_query['track']}'")
            
            # First try local match with split query
            local_match = self.find_match_in_local_db(
                track=split_query['track'],
                artist=split_query['artist'],
                verbose=verbose
            )
            if local_match:
                return local_match
            
            # Then try API search with split query
            best_track = self._find_best_match_from_api(
                track=split_query['track'],
                artist=split_query['artist']
            )
            if best_track:
                return best_track
                
            log.info("Both local and API searches with split query failed, falling back to original query.")
        else:
            log.info("Attempt to split query into track and artist failed.")

        # Step 3: Fallback to original query (cleaned but not split)
        # First try local search with original query
        local_match = self.find_match_in_local_db(track=cleaned_query, verbose=verbose)
        if local_match:
            return local_match
        
        # Then try API search with original query
        best_track = self._find_best_match_from_api(track=cleaned_query)
        if best_track:
            return best_track
        
        log.info(f"Search with original query failed, trying final fallback.")

        # Step 4: Final fallback to cleaned resolved YouTube title
        if cleaned_resolved_title.lower() != cleaned_query.lower():
            local_match = self.find_match_in_local_db(track=cleaned_resolved_title, verbose=verbose)
            if local_match:
                return local_match
            
            best_track = self._find_best_match_from_api(track=cleaned_resolved_title)
            if best_track:
                return best_track

        log.warning(f"No suitable track found after trying all search strategies.")
        return None