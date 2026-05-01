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


if __name__ == "__main__":
    unittest.main()
