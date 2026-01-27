from typing import Optional, Dict, List
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

    def _is_youtube_url(self, query: str) -> bool:
        """
        Detects if a query is a YouTube URL.
        Returns True if the query contains youtube.com or youtu.be.
        """
        return 'youtube.com' in query.lower() or 'youtu.be' in query.lower()

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
                # Fetch album info from track.getInfo
                track_info = lastfm_client.get_track_info(best_track['name'], best_track['artist'])
                if track_info and track_info.get('album'):
                    best_track['album'] = track_info['album']
                    log.info(f"Found album: '{best_track['album']}'")
                return best_track

            return None
        except Exception as e:
            log.error(f"API search failed for '{search_query}': {str(e)}")
            return None
        
    def _try_split_and_match(self, query: str, verbose: bool = True) -> Optional[Dict]:
        """
        Attempts to split a query into artist/track and tries local and API matching.
        Returns a match if found, None otherwise.
        """
        log.info(f"Attempting to split query '{query}' into track and artist.")
        split_query = preprocessing.split_artist_track(query, preprocessing.ARTIST_LIST)
        
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
                
            log.info("Both local and API searches with split query failed.")
        else:
            log.info("Attempt to split query into track and artist failed.")
        
        return None
        
    def _try_match_strategies(self, query: str, verbose: bool = True) -> Optional[Dict]:
        """
        Tries multiple strategies to find a match for a query:
        1. Split query and match locally and via API
        2. Match without splitting locally and via API
        Returns a match if found, None otherwise.
        """
        # First try splitting the query
        split_match = self._try_split_and_match(query, verbose)
        if split_match:
            return split_match
        
        # Fallback to query without splitting
        log.info("Falling back to query without splitting.")
        # First try local search
        local_match = self.find_match_in_local_db(track=query, verbose=verbose)
        if local_match:
            return local_match
        
        # Then try API search
        best_track = self._find_best_match_from_api(track=query)
        if best_track:
            return best_track
        
        log.info(f"Search with query failed.")
        return None
        
    def execute(self, original_query: str, resolved_title: str, verbose: bool = True) -> Optional[Dict]:
        """
        Main pipeline entry point. Cleans inputs and tries multiple strategies
        to find the best possible track match.
        """
        # Check if the query is a YouTube URL
        is_youtube_url = self._is_youtube_url(original_query)
        
        # Always process the resolved title
        cleaned_resolved_title = preprocessing.clean_youtube_title(resolved_title)
        
        if is_youtube_url:
            log.info(f"Detected YouTube URL: '{original_query}'. Query will be skipped, using only resolved title.")
            # For YouTube URLs, we don't process the URL as a query
            cleaned_query = None
        else:
            # Step 1: Pre-process inputs for non-URL queries
            expanded_query = preprocessing.expand_abbreviations(original_query)
            cleaned_query = preprocessing.clean_youtube_title(expanded_query)

        # Step 2: Try matching with the query (only if we have a non-URL query)
        if cleaned_query:
            match = self._try_match_strategies(cleaned_query, verbose)
            if match:
                return match
            
            log.info(f"Search with query failed, trying final fallback.")
        
        # Step 3: Final fallback to cleaned resolved YouTube title
        # Skip if the query was already the YouTube title (to avoid redundant searches)
        if cleaned_resolved_title and (not cleaned_query or cleaned_resolved_title.lower() != cleaned_query.lower()):
            if cleaned_query:
                log.info(f"Trying final fallback with resolved title: '{cleaned_resolved_title}'")
            else:
                log.info(f"Using resolved title as primary query: '{cleaned_resolved_title}'")
            
            # Try matching with the resolved title
            match = self._try_match_strategies(cleaned_resolved_title, verbose)
            if match:
                return match

        log.warning(f"No suitable track found after trying all search strategies.")
        return None