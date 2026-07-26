#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


class YouTubePlaylistTests(unittest.TestCase):
    def test_reads_required_deduplicated_tags(self):
        from publish_youtube import read_tags

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'youtube-tags.txt'
            path.write_text('Стамбул\nIstanbul\nСтамбул\n', encoding='utf-8')
            self.assertEqual(read_tags(path), ['Стамбул', 'Istanbul'])

    def test_rejects_empty_tags(self):
        from publish_youtube import read_tags

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'youtube-tags.txt'
            path.write_text('\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'empty'):
                read_tags(path)

    def test_audience_maps_to_youtube_privacy(self):
        from publish_youtube import privacy_for_audience

        self.assertEqual(privacy_for_audience('contacts'), 'private')
        self.assertEqual(privacy_for_audience('everyone'), 'public')
        self.assertEqual(privacy_for_audience('link'), 'unlisted')
        with self.assertRaisesRegex(ValueError, 'unsupported audience'):
            privacy_for_audience('unknown')

    def test_selects_exact_playlist_title(self):
        from publish_youtube import select_playlist_id

        items = [
            {'id': 'other', 'snippet': {'title': 'Другое'}},
            {'id': 'travel', 'snippet': {'title': 'Лягушка-путешественница'}},
        ]
        self.assertEqual(select_playlist_id(items, 'Лягушка-путешественница'), 'travel')

    def test_rejects_missing_playlist(self):
        from publish_youtube import select_playlist_id

        with self.assertRaisesRegex(ValueError, 'not found'):
            select_playlist_id([], 'Лягушка-путешественница')

    def test_rejects_duplicate_playlist_titles(self):
        from publish_youtube import select_playlist_id

        items = [
            {'id': 'one', 'snippet': {'title': 'Лягушка-путешественница'}},
            {'id': 'two', 'snippet': {'title': 'Лягушка-путешественница'}},
        ]
        with self.assertRaisesRegex(ValueError, 'multiple'):
            select_playlist_id(items, 'Лягушка-путешественница')


if __name__ == '__main__':
    unittest.main()
