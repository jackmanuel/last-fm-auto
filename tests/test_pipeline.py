# tests/test_pipeline.py
"""
Unit tests for the TrackPipeline class and its matching strategies.
"""
import unittest

from last_fm_auto import preprocessing
from last_fm_auto.pipeline import TrackPipeline


class TrackPipelineYouTubeChannelTests(unittest.TestCase):
    def test_uses_strong_youtube_channel_artist_hint_for_title_only_video(self):
        original_artist_list = preprocessing.ARTIST_LIST
        preprocessing.ARTIST_LIST = ["Known Artist"]
        try:
            pipeline = TrackPipeline.from_default_config(
                searchable_tracks=[
                    {"track": "Darkness", "artist": "Known Artist"},
                    {"track": "Darkness", "artist": "Popular Wrong Artist"},
                ]
            )

            match = pipeline.execute(
                original_query="https://www.youtube.com/watch?v=example",
                resolved_title="Darkness",
                youtube_channel="Known Artist - Topic",
                verbose=False,
            )
        finally:
            preprocessing.ARTIST_LIST = original_artist_list

        self.assertEqual(match, {"name": "Darkness", "artist": "Known Artist"})


class TrackPipelineQueryPreparationTests(unittest.TestCase):
    def test_preserves_query_when_raw_artist_match_exists_before_abbreviation(self):
        original_artist_list = preprocessing.ARTIST_LIST
        preprocessing.ARTIST_LIST = ["Earl Sweatshirt"]
        try:
            pipeline = TrackPipeline.from_default_config(searchable_tracks=[])

            queries = pipeline._prepare_non_url_queries("couch earl sweatshirt")
        finally:
            preprocessing.ARTIST_LIST = original_artist_list

        self.assertEqual(queries, ["couch earl sweatshirt"])

    def test_expands_abbreviation_when_raw_artist_match_is_missing(self):
        original_artist_list = preprocessing.ARTIST_LIST
        preprocessing.ARTIST_LIST = ["Earl Sweatshirt"]
        try:
            pipeline = TrackPipeline.from_default_config(searchable_tracks=[])

            queries = pipeline._prepare_non_url_queries("veins earl")
        finally:
            preprocessing.ARTIST_LIST = original_artist_list

        self.assertEqual(queries, ["veins Earl Sweatshirt"])


if __name__ == "__main__":
    unittest.main()
