import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from last_fm_auto import config, main


class ScrobbleModeTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.db_file = Path(directory) / 'history.db'
        self.enterContext(patch.multiple(
            config,
            DB_FILE=self.db_file,
            LAST_FM_API_KEY='test-key',
            LAST_FM_API_SECRET='test-secret',
            LAST_FM_SESSION_KEY='test-session',
        ))

    def test_startup_rejects_invalid_scope(self):
        cases = (
            ('guild', None, 'GUILD_ID'),
            ('standalone', 'my-guild', 'Unset GUILD_ID'),
            ('stand-alone', None, 'SCROBBLE_MODE'),
        )
        for mode, guild_id, message in cases:
            with self.subTest(mode=mode, guild_id=guild_id):
                with patch.multiple(config, SCROBBLE_MODE=mode, GUILD_ID=guild_id):
                    with self.assertRaisesRegex(ValueError, message):
                        config.validate_config(require_session_key=True)

    def test_guild_mode_filters_completed_and_playing_rows(self):
        with closing(sqlite3.connect(self.db_file)) as conn:
            conn.executescript("""
                CREATE TABLE play_history (
                    request_id INTEGER PRIMARY KEY, guild_id TEXT,
                    play_status TEXT, scrobble_status TEXT, play_start_timestamp TEXT
                );
                INSERT INTO play_history VALUES
                    (1, 'my-guild', 'completed', 'new', '2026-01-01T10:00:00'),
                    (2, 'other-guild', 'completed', 'new', '2026-01-01T10:01:00'),
                    (3, 'my-guild', 'playing', 'new', '2026-01-01T10:02:00'),
                    (4, 'other-guild', 'playing', 'new', '2026-01-01T10:03:00');
            """)

        with patch.multiple(config, SCROBBLE_MODE='guild', GUILD_ID='my-guild'):
            config.validate_config(require_session_key=True)
            self.assertEqual([row['request_id'] for row in main.get_new_songs('my-guild')], [1])
            self.assertEqual(main.get_playing_song('my-guild')['request_id'], 3)
            self.assertEqual(main.get_new_songs(None), [])
            self.assertIsNone(main.get_playing_song(None))

    def test_standalone_poll_scrobbles_and_updates_now_playing_without_guild_column(self):
        with closing(sqlite3.connect(self.db_file)) as conn:
            conn.executescript("""
                CREATE TABLE play_history (
                    request_id INTEGER PRIMARY KEY, query TEXT, resolved_title TEXT,
                    channel_name TEXT, play_start_timestamp TEXT, duration INTEGER,
                    play_status TEXT, scrobble_status TEXT
                );
                INSERT INTO play_history VALUES
                    (1, 'Song', 'Song', NULL, '2026-01-01T10:00:00', 120, 'completed', 'new'),
                    (2, 'Song', 'Song', NULL, '2026-01-01T10:02:00', 120, 'playing', 'new');
            """)

        with (
            patch.multiple(config, SCROBBLE_MODE='standalone', GUILD_ID=None),
            patch('sys.argv', ['last_fm_auto.main']),
            patch.object(main.pipeline.TrackPipeline, 'from_default_config') as make_pipeline,
            patch.object(main.lastfm_client, 'update_now_playing') as now_playing,
            patch.object(main.lastfm_client, 'scrobble_track', return_value=True) as scrobble,
            patch.object(main.time, 'sleep', side_effect=KeyboardInterrupt),
        ):
            make_pipeline.return_value.execute.return_value = {'name': 'Song', 'artist': 'Artist'}
            with self.assertRaises(SystemExit) as exit_result:
                main.main()

        self.assertEqual(exit_result.exception.code, 0)
        now_playing.assert_called_once_with('Artist', 'Song', None)
        scrobble.assert_called_once()
        with closing(sqlite3.connect(self.db_file)) as conn:
            statuses = conn.execute('SELECT scrobble_status FROM play_history ORDER BY request_id').fetchall()
        self.assertEqual(statuses, [('scrobbled',), ('new',)])
