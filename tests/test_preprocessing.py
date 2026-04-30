import unittest

from last_fm_auto import preprocessing


class SplitArtistTrackTests(unittest.TestCase):
    def test_splits_youtube_title_with_en_dash_separator(self):
        cleaned_title = preprocessing.clean_youtube_title(
            "boygenius \u2013 Not Strong Enough (official music video)"
        )

        self.assertEqual(
            preprocessing.split_artist_track(cleaned_title, ["boygenius"]),
            {"artist": "boygenius", "track": "Not Strong Enough"},
        )

    def test_splits_common_unicode_dash_separators(self):
        for separator in ["-", "\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"]:
            with self.subTest(separator=separator.encode("unicode_escape").decode()):
                self.assertEqual(
                    preprocessing.split_artist_track(
                        f"boygenius {separator} Not Strong Enough",
                        ["boygenius"],
                    ),
                    {"artist": "boygenius", "track": "Not Strong Enough"},
                )


if __name__ == "__main__":
    unittest.main()
