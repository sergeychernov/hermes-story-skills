import hashlib
import json
import os
import subprocess
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

    def test_oauth_default_client_path_is_not_double_nested(self):
        from setup_youtube_oauth import oauth_default_paths

        client, env = oauth_default_paths(Path('/home/user/.hermes'))
        self.assertEqual(client, Path('/home/user/.hermes/secrets/youtube-client.json'))
        self.assertEqual(env, Path('/home/user/.hermes/.env'))

    def test_oauth_parser_defaults_to_loopback_only(self):
        from setup_youtube_oauth import build_parser

        args = build_parser(Path('/home/user/.hermes')).parse_args([])
        self.assertEqual(args.host, '127.0.0.1')

    def test_oauth_env_temp_file_does_not_follow_predictable_symlink(self):
        from setup_youtube_oauth import update_env

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env_file = root / ".env"
            outside = root / "outside.txt"
            outside.write_text("ORIGINAL\n", encoding="utf-8")
            trap = root / ".env.youtube-oauth.tmp"
            trap.symlink_to(outside)
            update_env(env_file, {
                "YOUTUBE_CLIENT_ID": "id",
                "YOUTUBE_CLIENT_SECRET": "secret",
                "YOUTUBE_REFRESH_TOKEN": "refresh",
            })
            self.assertEqual(outside.read_text(encoding="utf-8"), "ORIGINAL\n")
            self.assertTrue(trap.is_symlink())
            self.assertEqual(env_file.stat().st_mode & 0o777, 0o600)

    def test_rejects_empty_required_metadata_before_upload(self):
        from publish_youtube import read_required_text

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "title.txt"
            path.write_text("  \n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "title"):
                read_required_text(path, "title")

    def test_verifies_green_report_and_exact_video_hash(self):
        from publish_youtube import verify_approved_package

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'video.mp4'
            video.write_bytes(b'approved bytes')
            report = root / 'verification.json'
            report.write_text(json.dumps({
                'ok': True,
                'video': {'sha256': hashlib.sha256(video.read_bytes()).hexdigest()},
            }), encoding='utf-8')
            verify_approved_package(video, report)
            video.write_bytes(b'changed bytes')
            with self.assertRaisesRegex(ValueError, 'hash'):
                verify_approved_package(video, report)

    def test_readback_requires_processing_and_exact_metadata(self):
        import publish_youtube

        responses = [{
            "items": [{
                "snippet": {"title": "Title", "description": "Description", "tags": ["one", "two"]},
                "status": {"privacyStatus": "unlisted", "uploadStatus": "processed"},
                "processingDetails": {"processingStatus": "succeeded"},
            }]
        }]
        original = publish_youtube.api_json
        publish_youtube.api_json = lambda *args, **kwargs: responses.pop(0)
        try:
            result = publish_youtube.wait_for_verified_upload(
                "token", "video-id",
                {"title": "Title", "description": "Description", "tags": ["one", "two"]},
                "unlisted", timeout=0, interval=0,
            )
        finally:
            publish_youtube.api_json = original
        self.assertEqual(result["processing_status"], "succeeded")

    def test_cli_refuses_without_explicit_approval_before_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {}
            for name in ('video.mp4', 'title.txt', 'description.txt', 'tags.txt', 'verification.json'):
                paths[name] = root / name
                paths[name].write_text('{}' if name == 'verification.json' else 'x', encoding='utf-8')
            env = os.environ.copy()
            for key in ('YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN'):
                env.pop(key, None)
            completed = subprocess.run([
                sys.executable, str(Path(__file__).with_name('publish_youtube.py')),
                '--video', str(paths['video.mp4']),
                '--title-file', str(paths['title.txt']),
                '--description-file', str(paths['description.txt']),
                '--tags-file', str(paths['tags.txt']),
                '--verification', str(paths['verification.json']),
                '--audience', 'contacts',
            ], text=True, capture_output=True, env=env)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn('explicit --approved', completed.stderr)


if __name__ == '__main__':
    unittest.main()
