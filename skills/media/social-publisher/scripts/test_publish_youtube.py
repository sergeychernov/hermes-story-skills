import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Minimal valid image bytes for cover validation tests.
MINIMAL_JPEG = bytes.fromhex('ffd8ffe000104a46494600010100000100010000ffd9')
MINIMAL_PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de'
    '0000000a4944415408d7636000000002000001e221bc330000000049454e44ae426082'
)


def _make_verification_report(video_bytes: bytes, cover_bytes: bytes) -> dict:
    return {
        'ok': True,
        'video': {'sha256': hashlib.sha256(video_bytes).hexdigest()},
        'cover': {'sha256': hashlib.sha256(cover_bytes).hexdigest()},
    }


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

    def test_selected_channel_must_match_oauth_channel(self):
        import publish_youtube

        original = publish_youtube.api_json
        publish_youtube.api_json = lambda *args, **kwargs: {
            'items': [{'id': 'expected', 'snippet': {'title': 'Travel'}}]
        }
        try:
            self.assertEqual(
                publish_youtube.verify_authorized_channel('token', 'expected'),
                {'id': 'expected', 'title': 'Travel'},
            )
            self.assertEqual(
                publish_youtube.verify_authorized_channel('token', None),
                {'id': 'expected', 'title': 'Travel'},
            )
            with self.assertRaisesRegex(ValueError, 'do not match'):
                publish_youtube.verify_authorized_channel('token', 'other')
        finally:
            publish_youtube.api_json = original

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

    def test_verifies_green_report_and_exact_video_and_cover_hash(self):
        from publish_youtube import verify_approved_package

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'video.mp4'
            cover = root / 'cover.jpg'
            video.write_bytes(b'approved bytes')
            cover.write_bytes(MINIMAL_JPEG)
            report = root / 'verification.json'
            report.write_text(json.dumps(_make_verification_report(
                video.read_bytes(), cover.read_bytes(),
            )), encoding='utf-8')
            result = verify_approved_package(video, cover, report)
            self.assertEqual(result['video_sha256'], hashlib.sha256(b'approved bytes').hexdigest())
            self.assertEqual(result['video_bytes'], b'approved bytes')
            self.assertEqual(result['cover_sha256'], hashlib.sha256(MINIMAL_JPEG).hexdigest())
            video.write_bytes(b'changed bytes')
            with self.assertRaisesRegex(ValueError, 'video hash'):
                verify_approved_package(video, cover, report)
            video.write_bytes(b'approved bytes')
            cover.write_bytes(MINIMAL_PNG)
            with self.assertRaisesRegex(ValueError, 'cover hash'):
                verify_approved_package(video, cover, report)

    def test_verify_rejects_missing_cover_in_report(self):
        from publish_youtube import verify_approved_package

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'video.mp4'
            cover = root / 'cover.jpg'
            video.write_bytes(b'approved bytes')
            cover.write_bytes(MINIMAL_JPEG)
            report = root / 'verification.json'
            report.write_text(json.dumps({
                'ok': True,
                'video': {'sha256': hashlib.sha256(b'approved bytes').hexdigest()},
            }), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'cover hash'):
                verify_approved_package(video, cover, report)

    def test_validate_cover_accepts_jpeg_and_png_by_bytes(self):
        from publish_youtube import validate_cover

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jpeg = root / 'cover.jpg'
            png = root / 'cover.png'
            jpeg.write_bytes(MINIMAL_JPEG)
            png.write_bytes(MINIMAL_PNG)
            self.assertEqual(validate_cover(jpeg), ('image/jpeg', MINIMAL_JPEG))
            self.assertEqual(validate_cover(png), ('image/png', MINIMAL_PNG))

    def test_validate_cover_rejects_non_image_and_corrupt_signatures(self):
        from publish_youtube import validate_cover

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_jpeg = root / 'fake.jpg'
            fake_jpeg.write_bytes(b'not a jpeg at all')
            with self.assertRaisesRegex(ValueError, 'unsupported cover'):
                validate_cover(fake_jpeg)
            corrupt = root / 'corrupt.png'
            corrupt.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 20)
            with self.assertRaisesRegex(ValueError, 'corrupt'):
                validate_cover(corrupt)

    def test_validate_cover_rejects_oversized_file(self):
        from publish_youtube import validate_cover, COVER_MAX_BYTES

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            huge = root / 'huge.jpg'
            huge.write_bytes(MINIMAL_JPEG + b'\x00' * (COVER_MAX_BYTES - len(MINIMAL_JPEG) + 1))
            with self.assertRaisesRegex(ValueError, '2 MiB'):
                validate_cover(huge)

    def test_upload_thumbnail_posts_media_with_correct_headers(self):
        import publish_youtube

        captured = {}

        def fake_req(url, data=None, headers=None, method=None):
            captured['url'] = url
            captured['data'] = data
            captured['headers'] = headers
            captured['method'] = method
            return mock.Mock(read=lambda: json.dumps({
                'kind': 'youtube#thumbnailSetResponse',
                'items': [{'default': {'url': 'https://i.ytimg.com/vi/abc/default.jpg'}}],
            }).encode())

        original = publish_youtube.req
        publish_youtube.req = fake_req
        try:
            result = publish_youtube.upload_thumbnail('tok', 'vid123', MINIMAL_JPEG, 'image/jpeg')
        finally:
            publish_youtube.req = original

        self.assertIn('videoId=vid123', captured['url'])
        self.assertIn('uploadType=media', captured['url'])
        self.assertEqual(captured['method'], 'POST')
        self.assertEqual(captured['data'], MINIMAL_JPEG)
        self.assertEqual(captured['headers']['Authorization'], 'Bearer tok')
        self.assertEqual(captured['headers']['Content-Type'], 'image/jpeg')
        self.assertEqual(captured['headers']['Content-Length'], str(len(MINIMAL_JPEG)))
        self.assertEqual(result['kind'], 'youtube#thumbnailSetResponse')
        self.assertTrue(result['items'])

    def test_upload_thumbnail_rejects_invalid_api_response(self):
        import publish_youtube

        def fake_req(url, data=None, headers=None, method=None):
            return mock.Mock(read=lambda: json.dumps({
                'kind': 'youtube#thumbnailSetResponse',
                'items': [],
            }).encode())

        original = publish_youtube.req
        publish_youtube.req = fake_req
        try:
            with self.assertRaisesRegex(RuntimeError, 'thumbnail'):
                publish_youtube.upload_thumbnail('tok', 'vid123', MINIMAL_JPEG, 'image/jpeg')
        finally:
            publish_youtube.req = original

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
            for name in ('video.mp4', 'cover.jpg', 'title.txt', 'description.txt', 'tags.txt', 'verification.json'):
                paths[name] = root / name
                if name == 'cover.jpg':
                    paths[name].write_bytes(MINIMAL_JPEG)
                else:
                    paths[name].write_text('{}' if name == 'verification.json' else 'x', encoding='utf-8')
            env = os.environ.copy()
            for key in ('YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN'):
                env.pop(key, None)
            completed = subprocess.run([
                sys.executable, str(Path(__file__).with_name('publish_youtube.py')),
                '--video', str(paths['video.mp4']),
                '--cover', str(paths['cover.jpg']),
                '--channel', 'current',
                '--title-file', str(paths['title.txt']),
                '--description-file', str(paths['description.txt']),
                '--tags-file', str(paths['tags.txt']),
                '--verification', str(paths['verification.json']),
                '--audience', 'contacts',
            ], text=True, capture_output=True, env=env)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn('explicit --approved', completed.stderr)

    def test_legacy_cli_does_not_require_channel_before_approval_gate(self):
        completed = subprocess.run([
            sys.executable, str(Path(__file__).with_name('publish_youtube.py')),
            '--video', 'missing.mp4',
            '--cover', 'missing-cover.jpg',
            '--title-file', 'missing-title.txt',
            '--description-file', 'missing-description.txt',
            '--tags-file', 'missing-tags.txt',
            '--verification', 'missing-verification.json',
            '--audience', 'contacts',
        ], text=True, capture_output=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('explicit --approved', completed.stderr)
        self.assertNotIn('--channel is required', completed.stderr)

    def test_cover_hash_mismatch_fails_before_oauth(self):
        import publish_youtube

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'video.mp4'
            cover = root / 'cover.jpg'
            video.write_bytes(b'video')
            cover.write_bytes(MINIMAL_JPEG)
            report = root / 'verification.json'
            report.write_text(json.dumps({
                'ok': True,
                'video': {'sha256': hashlib.sha256(b'video').hexdigest()},
                'cover': {'sha256': '0' * 64},
            }), encoding='utf-8')

            network_called = []
            credentials_called = []
            argv = [
                'publish_youtube.py',
                '--video', str(video),
                '--cover', str(cover),
                '--title-file', str(root / 'title.txt'),
                '--description-file', str(root / 'description.txt'),
                '--tags-file', str(root / 'tags.txt'),
                '--verification', str(report),
                '--audience', 'contacts',
                '--approved',
            ]
            original_req = publish_youtube.req
            original_creds = publish_youtube.legacy_environment_credentials
            publish_youtube.req = lambda *a, **k: network_called.append(True)
            publish_youtube.legacy_environment_credentials = (
                lambda environ=None: credentials_called.append(True)
            )
            try:
                with mock.patch.object(sys, 'argv', argv):
                    with self.assertRaisesRegex(SystemExit, 'cover hash'):
                        publish_youtube.main()
            finally:
                publish_youtube.req = original_req
                publish_youtube.legacy_environment_credentials = original_creds

            self.assertFalse(credentials_called)
            self.assertFalse(network_called)

    def test_thumbnail_failure_exits_safe_json_without_video_retry(self):
        import publish_youtube

        call_log = []

        def fake_api_json(path, token, params=None, data=None, method=None):
            call_log.append(('api_json', path))
            if path == '/channels':
                return {'items': [{'id': 'ch', 'snippet': {'title': 'Ch'}}]}
            if path == '/playlists':
                return {'items': [{'id': 'pl', 'snippet': {'title': 'Лягушка-путешественница'}}]}
            if path == '/videos':
                return {'items': [{
                    'snippet': {'title': 'T', 'description': 'D', 'tags': ['tag']},
                    'status': {'privacyStatus': 'private', 'uploadStatus': 'processed'},
                    'processingDetails': {'processingStatus': 'succeeded'},
                }]}
            raise AssertionError(f'unexpected api_json: {path}')

        def fake_req(url, data=None, headers=None, method=None):
            call_log.append(('req', url))
            if 'oauth2.googleapis.com/token' in url:
                return mock.Mock(read=lambda: json.dumps({'access_token': 'tok'}).encode())
            if 'uploadType=resumable' in url:
                return mock.Mock(headers={'Location': 'https://upload.example/resume'})
            if url == 'https://upload.example/resume':
                return mock.Mock(read=lambda: json.dumps({'id': 'vid-abc'}).encode())
            if 'thumbnails/set' in url:
                raise RuntimeError('thumbnail upload failed')
            raise AssertionError(f'unexpected req: {url}')

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / 'video.mp4'
            cover = root / 'cover.jpg'
            video.write_bytes(b'video')
            cover.write_bytes(MINIMAL_JPEG)
            (root / 'title.txt').write_text('T', encoding='utf-8')
            (root / 'description.txt').write_text('D', encoding='utf-8')
            (root / 'tags.txt').write_text('tag\n', encoding='utf-8')
            report = root / 'verification.json'
            report.write_text(json.dumps(_make_verification_report(
                video.read_bytes(), cover.read_bytes(),
            )), encoding='utf-8')

            argv = [
                'publish_youtube.py',
                '--video', str(video),
                '--cover', str(cover),
                '--title-file', str(root / 'title.txt'),
                '--description-file', str(root / 'description.txt'),
                '--tags-file', str(root / 'tags.txt'),
                '--verification', str(report),
                '--audience', 'contacts',
                '--approved',
            ]

            original_api = publish_youtube.api_json
            original_req = publish_youtube.req
            original_creds = publish_youtube.legacy_environment_credentials
            publish_youtube.api_json = fake_api_json
            publish_youtube.req = fake_req
            publish_youtube.legacy_environment_credentials = lambda environ=None: {
                'YOUTUBE_CLIENT_ID': 'id',
                'YOUTUBE_CLIENT_SECRET': 'secret',
                'YOUTUBE_REFRESH_TOKEN': 'refresh',
            }
            try:
                with mock.patch.object(sys, 'argv', argv):
                    with self.assertRaises(SystemExit) as ctx:
                        publish_youtube.main()
            finally:
                publish_youtube.api_json = original_api
                publish_youtube.req = original_req
                publish_youtube.legacy_environment_credentials = original_creds

            payload = json.loads(ctx.exception.args[0])
            self.assertTrue(payload['video_uploaded'])
            self.assertFalse(payload['thumbnail_uploaded'])
            self.assertEqual(payload['id'], 'vid-abc')
            self.assertNotIn(('api_json', '/playlistItems'), call_log)
            processing_index = call_log.index(('api_json', '/videos'))
            thumbnail_index = next(
                index for index, entry in enumerate(call_log)
                if entry[0] == 'req' and 'thumbnails/set' in entry[1]
            )
            self.assertLess(processing_index, thumbnail_index)
            resumable_starts = [
                entry for entry in call_log
                if entry[0] == 'req' and 'uploadType=resumable' in entry[1]
            ]
            self.assertEqual(len(resumable_starts), 1)


if __name__ == '__main__':
    unittest.main()
