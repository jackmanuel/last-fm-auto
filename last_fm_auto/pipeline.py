# last_fm_auto/pipeline.py
"""
Orchestrates the track matching pipeline, coordinating local and remote search strategies.
"""
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

    def _try_artist_hint_match(self, track: str, artist: str, verbose: bool = True) -> Optional[Dict]:
        """
        Tries matching a track with an externally supplied artist hint.
        The hint is treated as evidence, not as part of the raw title text.
        """
        log.info(f"Trying artist hint. Artist: '{artist}', Track: '{track}'")

        local_match = self.find_match_in_local_db(
            track=track,
            artist=artist,
            verbose=verbose
        )
        if local_match:
            return local_match

        return self._find_best_match_from_api(track=track, artist=artist)
        
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

    def _prepare_non_url_queries(self, original_query: str) -> List[str]:
        """
        Returns cleaned non-URL query variants in the order they should be tried.
        If the raw query already contains a recognizable artist, try it before
        abbreviation expansion so artist names such as "Earl Sweatshirt" do not
        get expanded into duplicated text.
        """
        cleaned_original_query = preprocessing.clean_youtube_title(original_query)
        raw_split = preprocessing.split_artist_track(cleaned_original_query, preprocessing.ARTIST_LIST)

        if raw_split.get("artist"):
            return [cleaned_original_query]

        expanded_query = preprocessing.expand_abbreviations(original_query)
        cleaned_expanded_query = preprocessing.clean_youtube_title(expanded_query)

        if cleaned_expanded_query.lower() == cleaned_original_query.lower():
            return [cleaned_original_query]

        return [cleaned_expanded_query]
        
    def execute(
        self,
        original_query: str,
        resolved_title: str,
        youtube_channel: Optional[str] = None,
        verbose: bool = True
    ) -> Optional[Dict]:
        """
        Main pipeline entry point. Cleans inputs and tries multiple strategies
        to find the best possible track match.
        """
        is_youtube_url = self._is_youtube_url(original_query)

        channel_artist_hint = None
        if is_youtube_url and youtube_channel:
            channel_match = preprocessing.match_youtube_channel_artist(
                youtube_channel,
                preprocessing.ARTIST_LIST
            )
            if channel_match.get("artist"):
                channel_artist_hint = channel_match["artist"]
                log.info(
                    f"YouTube channel '{youtube_channel}' matched artist hint "
                    f"'{channel_artist_hint}' (score: {channel_match['score']}, "
                    f"runner-up: {channel_match['runner_up_score']})."
                )
            else:
                log.info(
                    f"YouTube channel '{youtube_channel}' did not produce a strong artist hint "
                    f"(normalized: '{channel_match['normalized_channel']}', "
                    f"score: {channel_match['score']}, runner-up: {channel_match['runner_up_score']})."
                )
        
        cleaned_resolved_title = preprocessing.clean_youtube_title(resolved_title)
        
        if is_youtube_url:
            log.info(f"Detected YouTube URL: '{original_query}'. Query will be skipped, using only resolved title.")
            cleaned_queries = []
        else:
            # Step 1: Pre-process inputs for non-URL queries
            cleaned_queries = self._prepare_non_url_queries(original_query)

        # Step 2: Try matching with the query (only if we have a non-URL query)
        for cleaned_query in cleaned_queries:
            match = self._try_match_strategies(cleaned_query, verbose)
            if match:
                return match

        if cleaned_queries:
            log.info(f"Search with query failed, trying final fallback.")
        
        # Step 3: Final fallback to cleaned resolved YouTube title
        # Skip if the query was already the YouTube title (to avoid redundant searches)
        cleaned_query = cleaned_queries[-1] if cleaned_queries else None
        if cleaned_resolved_title and (not cleaned_query or cleaned_resolved_title.lower() != cleaned_query.lower()):
            if cleaned_query:
                log.info(f"Trying final fallback with resolved title: '{cleaned_resolved_title}'")
            else:
                log.info(f"Using resolved title as primary query: '{cleaned_resolved_title}'")

            if channel_artist_hint:
                title_split = preprocessing.split_artist_track(cleaned_resolved_title, preprocessing.ARTIST_LIST)
                if title_split.get("artist"):
                    log.info(
                        f"Resolved title already contains artist signal '{title_split['artist']}'. "
                        "Trying normal title strategies first."
                    )
                else:
                    match = self._try_artist_hint_match(
                        track=cleaned_resolved_title,
                        artist=channel_artist_hint,
                        verbose=verbose
                    )
                    if match:
                        return match
            
            match = self._try_match_strategies(cleaned_resolved_title, verbose)
            if match:
                return match

            if channel_artist_hint:
                title_split = preprocessing.split_artist_track(cleaned_resolved_title, preprocessing.ARTIST_LIST)
                if title_split.get("artist") and not preprocessing.is_same_artist(title_split["artist"], channel_artist_hint):
                    log.info(
                        f"Normal title strategies failed. Trying YouTube channel artist hint "
                        f"'{channel_artist_hint}' as a fallback."
                    )
                    match = self._try_artist_hint_match(
                        track=title_split["track"],
                        artist=channel_artist_hint,
                        verbose=verbose
                    )
                    if match:
                        return match

        log.warning(f"No suitable track found after trying all search strategies.")
        return None
