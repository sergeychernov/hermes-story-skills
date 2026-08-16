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


def _make_opening_video(path: Path, cover_frames: int) -> bytes:
    total_frames = max(5, cover_frames + 1)
    pixels = 32 * 32
    red = bytes((220, 20, 20)) * pixels
    blue = bytes((20, 20, 220)) * pixels
    raw = red * cover_frames + blue * (total_frames - cover_frames)
    subprocess.run([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '32x32', '-r', '30', '-i', '-',
        '-frames:v', str(total_frames), '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-r', '30', '-fps_mode', 'cfr', '-video_track_timescale', '90000', str(path),
    ], input=raw, check=True, capture_output=True)
    return path.read_bytes()


def _write_story(root: Path, *, audience: str = "contacts") -> Path:
    story = root / "story.json"
    story.write_text(json.dumps({
        "schema_version": 1,
        "id": "test-story",
        "publication": {
            "targets": {
                "youtube": {
                    "channel_key": "legacy-env",
                    "audience": audience,
                    "playlist_title": "Лягушка-путешественница",
                    "video_path": "video.mp4",
                    "cover_path": "cover.jpg",
                    "title_file": "youtube-title.txt",
                    "description_file": "youtube-description.txt",
                    "tags_file": "youtube-tags.txt",
                    "verification_file": "video.mp4.report.json",
                    "cover_verification_file": "cover.jpg.report.json",
                    "made_for_kids": False,
                    "contains_synthetic_media": False,
                    "notify_subscribers": False,
                    "recording_date_decision": "omit",
                    "location_decision": "omit"
                }
            }
        }
    }), encoding="utf-8")
    return story


def _write_approved_preflight(root: Path, *, audience: str = "contacts") -> tuple[Path, Path]:
    from youtube_metadata_preflight import build_approved_manifest

    for old_name, canonical_name in (
        ("title.txt", "youtube-title.txt"),
        ("description.txt", "youtube-description.txt"),
        ("tags.txt", "youtube-tags.txt"),
    ):
        old_path = root / old_name
        canonical_path = root / canonical_name
        if old_path.is_file() and not canonical_path.exists():
            canonical_path.write_bytes(old_path.read_bytes())
    video = root / "video.mp4"
    cover = root / "cover.jpg"
    (root / "video.mp4.report.json").write_text(json.dumps({
        "artifact": "video.mp4",
        "status": "review-ready",
        "timeline": {"cover_frames": 4, "first_live_frame": 4},
        "video": {
            "full_decode": "passed",
            "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        },
    }), encoding="utf-8")
    (root / "cover.jpg.report.json").write_text(json.dumps({
        "output": {
            "path": "cover.jpg",
            "sha256": hashlib.sha256(cover.read_bytes()).hexdigest(),
        },
        "platform_contract": {
            "platform": "youtube",
            "surface": "standard_api_thumbnail",
        },
        "visual_review": "user-approved",
    }), encoding="utf-8")
    story = _write_story(root, audience=audience)
    path = root / "youtube-publication-preflight.json"
    manifest = build_approved_manifest(
        story,
        approved_at="2026-08-16T04:00:00Z",
        approval_note="Test user approved exact metadata summary",
    )
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return story, path


class YouTubePlaylistTests(unittest.TestCase):
    def test_publish_record_is_immutable_atomic_and_private(self):
        from publish_youtube import write_publish_record

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = root / "story.json"
            story.write_text("{}", encoding="utf-8")
            record = {"video_id": "abc-123", "platform": "youtube"}
            path = write_publish_record(story, record)
            self.assertEqual(path.name, "publish-record-abc-123.json")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), record)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                write_publish_record(story, record)

    def test_upload_attempt_is_private_immutable_and_blocks_repeat(self):
        from publish_youtube import reserve_upload_attempt, write_upload_result

        with tempfile.TemporaryDirectory() as directory:
            story = Path(directory) / 'story.json'
            story.write_text('{}', encoding='utf-8')
            attempt = reserve_upload_attempt(
                story, media_sha256='a' * 64, manifest_sha256='b' * 64,
                channel_key='current',
            )
            self.assertEqual(attempt.stat().st_mode & 0o777, 0o600)
            self.assertTrue(json.loads(attempt.read_text())['do_not_retry_blindly'])
            with self.assertRaisesRegex(ValueError, 'already exists'):
                reserve_upload_attempt(
                    story, media_sha256='a' * 64, manifest_sha256='c' * 64,
                    channel_key='current',
                )
            result = write_upload_result(attempt, 'video-123')
            self.assertEqual(result.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(result.read_text())['video_id'], 'video-123')

    def test_existing_publish_record_blocks_same_media_hash(self):
        from publish_youtube import refuse_existing_publication

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = root / 'story.json'
            story.write_text('{}', encoding='utf-8')
            (root / 'publish-record-old.json').write_text(json.dumps({
                'platform': 'youtube', 'media_sha256': 'c' * 64,
            }), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'already have'):
                refuse_existing_publication(story, 'c' * 64)
            refuse_existing_publication(story, 'd' * 64)

    def test_live_media_gate_proves_exact_four_frame_cover(self):
        from publish_youtube import verify_four_frame_cover_bytes

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = verify_four_frame_cover_bytes(
                _make_opening_video(root / 'four.mp4', 4)
            )
            self.assertEqual(evidence['cover_frames'], 4)
            self.assertEqual(evidence['first_live_frame'], 4)
            with self.assertRaisesRegex(ValueError, 'frames 0..3'):
                verify_four_frame_cover_bytes(_make_opening_video(root / 'one.mp4', 1))
            with self.assertRaisesRegex(ValueError, 'frame 4 is still the cover'):
                verify_four_frame_cover_bytes(_make_opening_video(root / 'long.mp4', 24))

    def test_recording_date_readback_accepts_youtube_midnight_normalization(self):
        from publish_youtube import _same_recording_date

        self.assertTrue(_same_recording_date(
            "2026-08-12T00:00:00Z", "2026-08-12T15:30:00+08:00"
        ))
        self.assertFalse(_same_recording_date(
            "2026-08-13T00:00:00Z", "2026-08-12T15:30:00+08:00"
        ))

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

    def test_snapshot_rehashes_exact_bytes_that_will_be_consumed(self):
        from publish_youtube import snapshot_approved_artifacts

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            title = root / "youtube-title.txt"
            title.write_bytes(b"Approved title")
            manifest = root / "approved.json"
            manifest.write_text(json.dumps({
                "package": {
                    "title_file": hashlib.sha256(title.read_bytes()).hexdigest(),
                },
            }), encoding="utf-8")
            snapshots = snapshot_approved_artifacts(
                manifest, {"title_file": title}
            )
            self.assertEqual(snapshots["title_file"], b"Approved title")
            title.write_bytes(b"Changed after approval")
            with self.assertRaisesRegex(ValueError, "title_file hash"):
                snapshot_approved_artifacts(manifest, {"title_file": title})

    def test_untrusted_schema_content_is_rejected(self):
        from publish_youtube import require_trusted_schema

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trusted = root / "trusted.json"
            candidate = root / "candidate.json"
            trusted.write_text('{"approval": true}', encoding="utf-8")
            candidate.write_text('{"approval": false}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "untrusted publication schema"):
                require_trusted_schema(candidate, trusted, "publication schema")

    def test_frozen_cover_report_snapshot_is_semantically_revalidated(self):
        from publish_youtube import validate_snapshot_eligibility

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = _write_story(root)
            video = root / "video.mp4"
            cover = root / "cover.jpg"
            video.write_bytes(b"video")
            cover.write_bytes(MINIMAL_JPEG)
            (root / "title.txt").write_text("Title", encoding="utf-8")
            (root / "description.txt").write_text("Description", encoding="utf-8")
            (root / "tags.txt").write_text("tag", encoding="utf-8")
            _write_approved_preflight(root)
            config = json.loads(story.read_text(encoding="utf-8"))[
                "publication"
            ]["targets"]["youtube"]
            schema_path = Path(__file__).resolve().parents[1] / "templates/youtube-publication.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            snapshots = {
                "video": video.read_bytes(),
                "cover": cover.read_bytes(),
                "verification_file": (root / "video.mp4.report.json").read_bytes(),
                "cover_verification_file": (root / "cover.jpg.report.json").read_bytes(),
                "title_file": (root / "youtube-title.txt").read_bytes(),
                "description_file": (root / "youtube-description.txt").read_bytes(),
                "tags_file": (root / "youtube-tags.txt").read_bytes(),
            }
            report = json.loads(snapshots["cover_verification_file"])
            report["visual_review"] = "rejected"
            snapshots["cover_verification_file"] = json.dumps(report).encode("utf-8")
            with self.assertRaisesRegex(ValueError, "no longer eligible"):
                validate_snapshot_eligibility(config, schema, snapshots)

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

    def test_readback_requires_both_processing_success_flags(self):
        import publish_youtube

        base = {
            "snippet": {"title": "Title", "description": "Description", "tags": ["one"]},
            "status": {"privacyStatus": "unlisted"},
            "processingDetails": {},
        }
        original = publish_youtube.api_json
        try:
            for upload_status, processing_status in (
                ("processed", "processing"),
                ("uploaded", "succeeded"),
            ):
                with self.subTest(
                    upload_status=upload_status,
                    processing_status=processing_status,
                ):
                    item = json.loads(json.dumps(base))
                    item["status"]["uploadStatus"] = upload_status
                    item["processingDetails"]["processingStatus"] = processing_status
                    publish_youtube.api_json = lambda *args, _item=item, **kwargs: {
                        "items": [_item]
                    }
                    with self.assertRaises(TimeoutError):
                        publish_youtube.wait_for_verified_upload(
                            "token", "video-id",
                            {"title": "Title", "description": "Description", "tags": ["one"]},
                            "unlisted", timeout=0, interval=0,
                        )
        finally:
            publish_youtube.api_json = original

    def test_readback_requires_extended_approved_metadata(self):
        import publish_youtube

        response = {
            "items": [{
                "snippet": {
                    "title": "Title",
                    "description": "Description",
                    "tags": ["one"],
                    "categoryId": "19",
                    "defaultLanguage": "ru",
                },
                "status": {
                    "privacyStatus": "public",
                    "uploadStatus": "processed",
                    "selfDeclaredMadeForKids": False,
                    "containsSyntheticMedia": True,
                    "embeddable": True,
                    "license": "youtube",
                    "publicStatsViewable": True,
                },
                "recordingDetails": {
                    "recordingDate": "2026-08-13T02:00:00Z",
                },
                "processingDetails": {"processingStatus": "succeeded"},
            }]
        }
        original = publish_youtube.api_json
        publish_youtube.api_json = lambda *args, **kwargs: response
        expected = {
            "title": "Title",
            "description": "Description",
            "tags": ["one"],
            "category_id": "19",
            "default_language": "ru",
            "made_for_kids": False,
            "contains_synthetic_media": True,
                "notify_subscribers": False,
            "embeddable": True,
            "license": "youtube",
            "public_stats_viewable": True,
            "recording_date": "2026-08-13T02:00:00Z",
        }
        try:
            result = publish_youtube.wait_for_verified_upload(
                "token", "video-id", expected, "public", timeout=0, interval=0,
            )
            self.assertEqual(result["processing_status"], "succeeded")
            response["items"][0]["status"]["containsSyntheticMedia"] = False
            with self.assertRaisesRegex(ValueError, "extended metadata"):
                publish_youtube.wait_for_verified_upload(
                    "token", "video-id", expected, "public", timeout=0, interval=0,
                )
            expected["contains_synthetic_media"] = False
            del response["items"][0]["status"]["containsSyntheticMedia"]
            result = publish_youtube.wait_for_verified_upload(
                "token", "video-id", expected, "public", timeout=0, interval=0,
            )
            self.assertEqual(result["processing_status"], "succeeded")
        finally:
            publish_youtube.api_json = original

    def test_upload_url_binds_notify_subscribers_decision(self):
        from publish_youtube import build_youtube_upload_url

        quiet = build_youtube_upload_url("snippet,status", False)
        loud = build_youtube_upload_url("snippet,status,recordingDetails", True)
        self.assertIn("notifySubscribers=false", quiet)
        self.assertIn("part=snippet%2Cstatus", quiet)
        self.assertIn("notifySubscribers=true", loud)
        self.assertIn("recordingDetails", loud)

    def test_api_metadata_uses_approved_preflight_decisions(self):
        from publish_youtube import build_youtube_api_metadata

        meta, parts = build_youtube_api_metadata(
            title="Title",
            description="Description",
            tags=["one", "two"],
            privacy="public",
            decisions={
                "category_id": "19",
                "default_language": "ru",
                "made_for_kids": False,
                "contains_synthetic_media": True,
                "notify_subscribers": False,
                "embeddable": True,
                "license": "youtube",
                "public_stats_viewable": True,
                "recording_date_decision": "set",
                "recording_date": "2026-08-13",
                "location_decision": "description",
                "location_text": "Пекинский зоопарк, Пекин, Китай",
            },
        )

        self.assertEqual(parts, "snippet,status,recordingDetails")
        self.assertEqual(meta["snippet"]["categoryId"], "19")
        self.assertEqual(meta["snippet"]["defaultLanguage"], "ru")
        self.assertFalse(meta["status"]["selfDeclaredMadeForKids"])
        self.assertTrue(meta["status"]["containsSyntheticMedia"])
        self.assertTrue(meta["status"]["embeddable"])
        self.assertTrue(meta["status"]["publicStatsViewable"])
        self.assertEqual(meta["status"]["license"], "youtube")
        self.assertEqual(
            meta["recordingDetails"]["recordingDate"],
            "2026-08-13T00:00:00Z",
        )
        self.assertNotIn("location", meta["recordingDetails"])

    def test_cli_refuses_without_metadata_preflight_before_credentials(self):
        import publish_youtube

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "video.mp4"
            cover = root / "cover.jpg"
            video.write_bytes(b"video")
            cover.write_bytes(MINIMAL_JPEG)
            (root / "title.txt").write_text("Title", encoding="utf-8")
            (root / "description.txt").write_text("Description", encoding="utf-8")
            (root / "tags.txt").write_text("tag\n", encoding="utf-8")
            report = root / "verification.json"
            report.write_text(json.dumps(_make_verification_report(
                video.read_bytes(), cover.read_bytes(),
            )), encoding="utf-8")
            story = _write_story(root, audience="everyone")
            credentials_called = []
            network_called = []
            argv = [
                "publish_youtube.py",
                "--story", str(story),
                "--approved",
            ]
            original_req = publish_youtube.req
            original_creds = publish_youtube.legacy_environment_credentials
            publish_youtube.req = lambda *a, **k: network_called.append(True)
            publish_youtube.legacy_environment_credentials = (
                lambda environ=None: credentials_called.append(True)
            )
            try:
                with mock.patch.object(sys, "argv", argv):
                    with self.assertRaisesRegex(SystemExit, "--metadata-preflight"):
                        publish_youtube.main()
            finally:
                publish_youtube.req = original_req
                publish_youtube.legacy_environment_credentials = original_creds
            self.assertFalse(credentials_called)
            self.assertFalse(network_called)

    def test_cli_refuses_without_explicit_approval_before_story_or_credentials(self):
        completed = subprocess.run([
            sys.executable, str(Path(__file__).with_name('publish_youtube.py')),
            '--story', 'missing-story.json',
        ], text=True, capture_output=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('explicit --approved', completed.stderr)
        self.assertNotIn('missing-story', completed.stderr)

    def test_cli_does_not_require_story_before_approval_gate(self):
        completed = subprocess.run([
            sys.executable, str(Path(__file__).with_name('publish_youtube.py')),
        ], text=True, capture_output=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('explicit --approved', completed.stderr)
        self.assertNotIn('--story is required', completed.stderr)

    def test_cover_mutation_after_approval_fails_before_oauth(self):
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

            (root / 'title.txt').write_text('T', encoding='utf-8')
            (root / 'description.txt').write_text('D', encoding='utf-8')
            (root / 'tags.txt').write_text('tag\n', encoding='utf-8')
            story, preflight = _write_approved_preflight(root)
            cover.write_bytes(MINIMAL_PNG)
            network_called = []
            credentials_called = []
            argv = [
                'publish_youtube.py',
                '--story', str(story),
                '--metadata-preflight', str(preflight),
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
                    with self.assertRaisesRegex(SystemExit, 'configuration is incomplete'):
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
                    'snippet': {
                        'title': 'T',
                        'description': 'D',
                        'tags': ['tag'],
                        'categoryId': '19',
                        'defaultLanguage': 'ru',
                    },
                    'status': {
                        'privacyStatus': 'private',
                        'uploadStatus': 'processed',
                        'selfDeclaredMadeForKids': False,
                        'containsSyntheticMedia': False,
                        'embeddable': True,
                        'license': 'youtube',
                        'publicStatsViewable': True,
                    },
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
            story, preflight = _write_approved_preflight(root)

            argv = [
                'publish_youtube.py',
                '--story', str(story),
                '--metadata-preflight', str(preflight),
                '--approved',
            ]

            original_api = publish_youtube.api_json
            original_req = publish_youtube.req
            original_creds = publish_youtube.legacy_environment_credentials
            original_frame_gate = publish_youtube.verify_four_frame_cover_bytes
            publish_youtube.api_json = fake_api_json
            publish_youtube.req = fake_req
            publish_youtube.verify_four_frame_cover_bytes = lambda _video: {
                'cover_frames': 4, 'first_live_frame': 4,
                'cover_ssim': [1.0, 1.0, 1.0], 'first_live_ssim': 0.0,
            }
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
                publish_youtube.verify_four_frame_cover_bytes = original_frame_gate

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
    def test_ambiguous_insert_failure_blocks_blind_retry(self):
        import urllib.error
        import publish_youtube

        calls = []

        def fake_api_json(path, token, params=None, data=None, method=None):
            if path == '/channels':
                return {'items': [{'id': 'ch', 'snippet': {'title': 'Ch'}}]}
            if path == '/playlists':
                return {'items': [{'id': 'pl', 'snippet': {'title': 'Лягушка-путешественница'}}]}
            raise AssertionError(f'unexpected api_json: {path}')

        def fake_req(url, data=None, headers=None, method=None):
            calls.append(url)
            if 'oauth2.googleapis.com/token' in url:
                return mock.Mock(read=lambda: json.dumps({'access_token': 'tok'}).encode())
            if 'uploadType=resumable' in url:
                raise urllib.error.URLError('response lost')
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
            (root / 'verification.json').write_text(json.dumps(
                _make_verification_report(video.read_bytes(), cover.read_bytes())
            ), encoding='utf-8')
            story, preflight = _write_approved_preflight(root)
            argv = [
                'publish_youtube.py', '--story', str(story),
                '--metadata-preflight', str(preflight), '--approved',
            ]
            patches = (
                mock.patch.object(publish_youtube, 'api_json', fake_api_json),
                mock.patch.object(publish_youtube, 'req', fake_req),
                mock.patch.object(publish_youtube, 'legacy_environment_credentials', lambda environ=None: {
                    'YOUTUBE_CLIENT_ID': 'id', 'YOUTUBE_CLIENT_SECRET': 'secret',
                    'YOUTUBE_REFRESH_TOKEN': 'refresh',
                }),
                mock.patch.object(publish_youtube, 'verify_four_frame_cover_bytes', lambda _video: {
                    'cover_frames': 4, 'first_live_frame': 4,
                    'cover_ssim': [1.0, 1.0, 1.0], 'first_live_ssim': 0.0,
                }),
            )
            with patches[0], patches[1], patches[2], patches[3]:
                with mock.patch.object(sys, 'argv', argv):
                    with self.assertRaises(SystemExit) as first:
                        publish_youtube.main()
                payload = json.loads(first.exception.args[0])
                self.assertTrue(payload['do_not_retry'])
                self.assertEqual(payload['video_upload_state'], 'ambiguous')
                self.assertTrue(Path(payload['upload_attempt_record']).is_file())
                with mock.patch.object(sys, 'argv', argv):
                    with self.assertRaisesRegex(SystemExit, 'attempt already exists'):
                        publish_youtube.main()
            resumable = [url for url in calls if 'uploadType=resumable' in url]
            self.assertEqual(len(resumable), 1)


if __name__ == '__main__':
    unittest.main()
