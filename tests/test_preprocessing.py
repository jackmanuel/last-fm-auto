import unittest

from last_fm_auto import preprocessing


class SplitArtistTrackTests(unittest.TestCase):
    def test_preserves_spacing_after_removed_parenthetical(self):
        cleaned_title = preprocessing.clean_youtube_title(
            "Nelly Furtado - Promiscuous (Official Music Video) ft. Timbaland"
        )

        self.assertEqual(
            cleaned_title,
            "Nelly Furtado - Promiscuous ft. Timbaland",
        )

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

    def test_normalizes_youtube_channel_suffixes(self):
        self.assertEqual(
            preprocessing.normalize_youtube_channel_name("@boygenius - Topic"),
            "boygenius",
        )
        self.assertEqual(
            preprocessing.normalize_youtube_channel_name("AdeleVEVO"),
            "Adele",
        )
        self.assertEqual(
            preprocessing.normalize_youtube_channel_name("Official Arctic Monkeys"),
            "Arctic Monkeys",
        )
        self.assertEqual(
            preprocessing.normalize_youtube_channel_name("ModjoOfficial"),
            "Modjo",
        )

    def test_strictly_matches_youtube_channel_to_artist(self):
        self.assertEqual(
            preprocessing.match_youtube_channel_artist("boygenius - Topic", ["boygenius", "Boys Noize"])["artist"],
            "boygenius",
        )

    def test_rejects_noisy_youtube_channel_near_match(self):
        self.assertIsNone(
            preprocessing.match_youtube_channel_artist("Some Music Channel", ["Some Musician"])["artist"],
        )


if __name__ == "__main__":
    unittest.main()
