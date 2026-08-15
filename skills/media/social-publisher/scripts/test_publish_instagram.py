#!/usr/bin/env python3
import argparse
import hashlib
import http.client
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
import warnings
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

PUBLIC_TEST_IP = "93.184.216.34"
VIDEO_BYTES = b"approved-instagram-video"


def _verification_report(video_bytes: bytes = VIDEO_BYTES) -> dict:
    return {"ok": True, "video": {"sha256": hashlib.sha256(video_bytes).hexdigest()}}


def _make_package(root: Path) -> dict[str, Path]:
    video = root / "reel-short.mp4"
    video.write_bytes(VIDEO_BYTES)
    verification = root / "verification.json"
    verification.write_text(json.dumps(_verification_report()), encoding="utf-8")
    caption = root / "instagram-caption.txt"
    caption.write_text("Approved caption", encoding="utf-8")
    return {"video": video, "verification": verification, "caption": caption}


class InstagramGateTests(unittest.TestCase):
    def test_cli_refuses_without_explicit_approval_before_credentials_or_network(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _make_package(Path(directory))
            env = os.environ.copy()
            env.pop("INSTAGRAM_ACCESS_TOKEN", None)
            env.pop("INSTAGRAM_USER_ID", None)
            script = Path(__file__).with_name("publish_instagram.py")
            completed = subprocess.run([
                sys.executable,
                str(script),
                "--video", str(paths["video"]),
                "--video-url", "https://example.invalid/video.mp4",
                "--verification", str(paths["verification"]),
                "--caption-file", str(paths["caption"]),
            ], text=True, capture_output=True, env=env)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("explicit --approved", completed.stderr)


class InstagramValidationTests(unittest.TestCase):
    def test_read_caption_requires_non_empty_utf8_and_max_length(self):
        from publish_instagram import CAPTION_MAX_LENGTH, read_caption

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "caption.txt"
            path.write_text("  hello  \n", encoding="utf-8")
            self.assertEqual(read_caption(path), "hello")
            path.write_text("\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-empty"):
                read_caption(path)
            path.write_text("x" * (CAPTION_MAX_LENGTH + 1), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "2200"):
                read_caption(path)

    def test_validate_api_version_syntax(self):
        from publish_instagram import validate_api_version

        validate_api_version("v24.0")
        with self.assertRaisesRegex(ValueError, "syntax"):
            validate_api_version("24.0")
        with self.assertRaisesRegex(ValueError, "syntax"):
            validate_api_version("v24")

    def test_verify_local_package_requires_green_report_and_exact_hash(self):
        from publish_instagram import verify_local_package

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _make_package(root)
            self.assertEqual(
                verify_local_package(paths["video"], paths["verification"]),
                hashlib.sha256(VIDEO_BYTES).hexdigest(),
            )
            paths["video"].write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "video hash"):
                verify_local_package(paths["video"], paths["verification"])

    def test_url_validation_rejects_credentials_fragment_and_private_targets(self):
        from publish_instagram import validate_public_https_url

        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate_public_https_url("http://example.com/v.mp4", resolve=False)
        with self.assertRaisesRegex(ValueError, "fragment"):
            validate_public_https_url("https://example.com/v.mp4#secret", resolve=False)
        with self.assertRaisesRegex(ValueError, "credentials"):
            validate_public_https_url("https://user:pass@example.com/v.mp4", resolve=False)
        with self.assertRaisesRegex(ValueError, "localhost"):
            validate_public_https_url("https://localhost/v.mp4", resolve=False)
        with self.assertRaisesRegex(ValueError, "private"):
            validate_public_https_url("https://127.0.0.1/v.mp4", resolve=False)
        with self.assertRaisesRegex(ValueError, "private"):
            validate_public_https_url("https://10.0.0.1/v.mp4", resolve=False)

    def test_url_validation_rejects_private_dns_resolution(self):
        from publish_instagram import validate_public_https_url

        def private_resolver(_host):
            return ["127.0.0.1"]

        with self.assertRaisesRegex(ValueError, "private"):
            validate_public_https_url("https://cdn.example.com/v.mp4", resolver=private_resolver)

    def test_redirect_handler_rejects_unsafe_target(self):
        from publish_instagram import SafeRedirectHandler, validate_public_https_url

        handler = SafeRedirectHandler(resolver=lambda host: [PUBLIC_TEST_IP])
        request = mock.Mock(full_url="https://cdn.example.com/start.mp4")
        with self.assertRaisesRegex(ValueError, "localhost"):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {"Location": "https://localhost/redirect.mp4"},
                "https://localhost/redirect.mp4",
            )
        validate_public_https_url(
            "https://cdn.example.com/final.mp4",
            resolver=lambda host: [PUBLIC_TEST_IP],
        )

    def test_download_validates_content_type_and_size(self):
        import publish_instagram

        class FakeResponse:
            def __init__(self, url, body=b"", content_type="video/mp4"):
                self._url = url
                self.headers = {"Content-Type": content_type}
                self._body = body

            def geturl(self):
                return self._url

            def read(self, size=-1):
                if not self._body:
                    return b""
                chunk, self._body = self._body, b""
                return chunk

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class GoodOpener:
            def open(self, request, timeout=120):
                if "bad-type" in request.full_url:
                    return FakeResponse(request.full_url, body=VIDEO_BYTES, content_type="text/plain")
                if "too-big" in request.full_url:
                    return FakeResponse(request.full_url, body=b"x" * (300 * 1024 * 1024 + 1))
                if "bad-hash" in request.full_url:
                    return FakeResponse(request.full_url, body=b"wrong")
                return FakeResponse(request.full_url, body=VIDEO_BYTES)

        resolver = lambda host: [PUBLIC_TEST_IP]
        with self.assertRaisesRegex(ValueError, "video/mp4"):
            publish_instagram.download_remote_media(
                "https://cdn.example.com/bad-type.mp4",
                hashlib.sha256(VIDEO_BYTES).hexdigest(),
                opener=GoodOpener(),
                resolver=resolver,
            )
        with self.assertRaisesRegex(ValueError, "300 MiB"):
            publish_instagram.download_remote_media(
                "https://cdn.example.com/too-big.mp4",
                hashlib.sha256(VIDEO_BYTES).hexdigest(),
                opener=GoodOpener(),
                resolver=resolver,
            )
        with self.assertRaisesRegex(ValueError, "hash"):
            publish_instagram.download_remote_media(
                "https://cdn.example.com/bad-hash.mp4",
                hashlib.sha256(VIDEO_BYTES).hexdigest(),
                opener=GoodOpener(),
                resolver=resolver,
            )

    def test_selected_identity_must_match_registered_user_id(self):
        import publish_instagram

        original = publish_instagram.fetch_instagram_identity
        publish_instagram.fetch_instagram_identity = lambda *a, **k: {"id": "expected", "username": "frog"}
        try:
            with self.assertRaisesRegex(ValueError, "username"):
                publish_instagram.verify_registered_identity("tok", "v24.0", "expected", "wrong")
            self.assertEqual(
                publish_instagram.verify_registered_identity("tok", "v24.0", "expected", None),
                {"id": "expected", "username": "frog"},
            )
            publish_instagram.fetch_instagram_identity = lambda *a, **k: {"id": "other", "username": "frog"}
            with self.assertRaisesRegex(ValueError, "do not match"):
                publish_instagram.verify_registered_identity("tok", "v24.0", "expected", None)
        finally:
            publish_instagram.fetch_instagram_identity = original

    def test_duplicate_record_blocks_before_instagram_writes(self):
        import publish_instagram

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _make_package(root)
            record = root / "instagram-publish.json"
            record.write_text(json.dumps({
                "platform": "instagram",
                "target": {"key": "legacy-env", "id": "12345", "username": "frog"},
                "sha256": hashlib.sha256(VIDEO_BYTES).hexdigest(),
            }), encoding="utf-8")
            network_called = []
            argv = [
                "publish_instagram.py",
                "--video", str(paths["video"]),
                "--video-url", "https://cdn.example.com/video.mp4",
                "--verification", str(paths["verification"]),
                "--caption-file", str(paths["caption"]),
                "--record", str(record),
                "--approved",
            ]
            original_download = publish_instagram.download_remote_media
            original_legacy = publish_instagram.legacy_environment_credentials
            original_resolver = publish_instagram.resolve_host
            publish_instagram.download_remote_media = lambda *a, **k: network_called.append(True) or (VIDEO_BYTES, "https://cdn.example.com/v.mp4")
            publish_instagram.legacy_environment_credentials = lambda environ=None: {
                "INSTAGRAM_ACCESS_TOKEN": "tok",
                "INSTAGRAM_USER_ID": "12345",
            }
            publish_instagram.resolve_host = lambda host: [PUBLIC_TEST_IP]
            try:
                with mock.patch.object(sys, "argv", argv):
                    with self.assertRaisesRegex(SystemExit, "duplicate"):
                        publish_instagram.main()
            finally:
                publish_instagram.download_remote_media = original_download
                publish_instagram.legacy_environment_credentials = original_legacy
                publish_instagram.resolve_host = original_resolver
            self.assertFalse(network_called)

    def test_publish_record_is_atomic_and_mode_600(self):
        from publish_instagram import write_publish_record_atomic

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "instagram-publish-travel.json"
            write_publish_record_atomic(path, {"platform": "instagram", "sha256": "abc"})
            self.assertTrue(path.is_file())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_same_target_and_video_serializes_concurrent_publish_sections(self):
        import publish_instagram

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _make_package(root)
            args = argparse.Namespace(
                approved=True,
                account=None,
                video=paths["video"],
                verification=paths["verification"],
                record=root / "instagram-publish.json",
            )
            state_lock = threading.Lock()
            state = {"active": 0, "max_active": 0}

            def fake_publish(*_args, **_kwargs):
                with state_lock:
                    state["active"] += 1
                    state["max_active"] = max(state["max_active"], state["active"])
                time.sleep(0.1)
                with state_lock:
                    state["active"] -= 1
                return {"ok": True}

            credentials = {
                "INSTAGRAM_ACCESS_TOKEN": "tok",
                "INSTAGRAM_USER_ID": "12345",
            }
            errors = []

            def worker():
                try:
                    publish_instagram.publish(args)
                except Exception as exc:  # pragma: no cover - assertion evidence
                    errors.append(exc)

            with mock.patch.object(
                publish_instagram, "legacy_environment_credentials", return_value=credentials
            ), mock.patch.object(publish_instagram, "_publish_with_lock_held", side_effect=fake_publish):
                threads = [threading.Thread(target=worker) for _ in range(2)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=2)

            self.assertFalse(errors)
            self.assertEqual(state["max_active"], 1)

    def test_poll_status_handles_error_and_timeout(self):
        import publish_instagram

        statuses = [{"status_code": "IN_PROGRESS"}, {"status_code": "ERROR", "status": "failed"}]
        publish_instagram.api_get = lambda *a, **k: statuses.pop(0)
        with self.assertRaisesRegex(ValueError, "container failed"):
            publish_instagram.poll_container_status("tok", "cid", "v24.0", timeout=1, interval=0)

        publish_instagram.api_get = lambda *a, **k: {"status_code": "IN_PROGRESS"}
        with self.assertRaisesRegex(TimeoutError, "timeout"):
            publish_instagram.poll_container_status(
                "tok", "cid", "v24.0", timeout=0, interval=0, monotonic=lambda: 1.0,
            )

    def test_readback_requires_reel_product_and_exact_caption(self):
        import publish_instagram

        publish_instagram.api_get = lambda *a, **k: {
            "id": "mid",
            "username": "frog",
            "media_type": "VIDEO",
            "media_product_type": "REELS",
            "permalink": "https://instagram.com/reel/abc/",
            "caption": "Approved caption",
            "timestamp": "2026-01-01T00:00:00+0000",
        }
        result = publish_instagram.read_back_published_media(
            "tok", "mid", "v24.0", expected_username="frog", expected_caption="Approved caption",
        )
        self.assertEqual(result["media_product_type"], "REELS")

        publish_instagram.api_get = lambda *a, **k: {
            "id": "mid",
            "username": "frog",
            "media_type": "VIDEO",
            "media_product_type": "FEED",
            "permalink": "https://instagram.com/p/abc/",
            "caption": "Approved caption",
            "timestamp": "2026-01-01T00:00:00+0000",
        }
        with self.assertRaisesRegex(ValueError, "REELS"):
            publish_instagram.read_back_published_media(
                "tok", "mid", "v24.0", expected_username="frog", expected_caption="Approved caption",
            )

    def test_provisional_record_blocks_repeat_even_when_readback_failed(self):
        import publish_instagram

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _make_package(root)
            record = root / "instagram-publish.json"
            record.write_text(json.dumps({
                "platform": "instagram",
                "target": {"key": "legacy-env", "id": "12345", "username": "frog"},
                "timestamp": None,
                "media_id": "media-1",
                "permalink": None,
                "sha256": hashlib.sha256(VIDEO_BYTES).hexdigest(),
                "caption_sha256": hashlib.sha256("Approved caption".encode()).hexdigest(),
                "visibility": "public",
            }), encoding="utf-8")
            network_called = []
            originals = {
                "download": publish_instagram.download_remote_media,
                "legacy": publish_instagram.legacy_environment_credentials,
                "resolver": publish_instagram.resolve_host,
            }
            publish_instagram.download_remote_media = lambda *a, **k: network_called.append(True)
            publish_instagram.legacy_environment_credentials = lambda environ=None: {
                "INSTAGRAM_ACCESS_TOKEN": "tok",
                "INSTAGRAM_USER_ID": "12345",
            }
            publish_instagram.resolve_host = lambda host: [PUBLIC_TEST_IP]
            argv = [
                "publish_instagram.py",
                "--video", str(paths["video"]),
                "--video-url", "https://cdn.example.com/video.mp4",
                "--verification", str(paths["verification"]),
                "--caption-file", str(paths["caption"]),
                "--approved",
            ]
            try:
                with mock.patch.object(sys, "argv", argv):
                    with self.assertRaisesRegex(SystemExit, "duplicate"):
                        publish_instagram.main()
            finally:
                for name, value in originals.items():
                    setattr(publish_instagram, {
                        "download": "download_remote_media",
                        "legacy": "legacy_environment_credentials",
                        "resolver": "resolve_host",
                    }[name], value)
            self.assertFalse(network_called)

    def test_duplicate_scan_inspects_all_instagram_publish_records_in_video_parent(self):
        import publish_instagram

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _make_package(root)
            sibling = root / "instagram-publish-other.json"
            sibling.write_text(json.dumps({
                "platform": "instagram",
                "target": {"key": "legacy-env", "id": "12345", "username": "frog"},
                "sha256": hashlib.sha256(VIDEO_BYTES).hexdigest(),
            }), encoding="utf-8")
            override = root / "instagram-publish-custom.json"
            network_called = []
            originals = {
                "download": publish_instagram.download_remote_media,
                "legacy": publish_instagram.legacy_environment_credentials,
                "resolver": publish_instagram.resolve_host,
            }
            publish_instagram.download_remote_media = lambda *a, **k: network_called.append(True)
            publish_instagram.legacy_environment_credentials = lambda environ=None: {
                "INSTAGRAM_ACCESS_TOKEN": "tok",
                "INSTAGRAM_USER_ID": "12345",
            }
            publish_instagram.resolve_host = lambda host: [PUBLIC_TEST_IP]
            argv = [
                "publish_instagram.py",
                "--video", str(paths["video"]),
                "--video-url", "https://cdn.example.com/video.mp4",
                "--verification", str(paths["verification"]),
                "--caption-file", str(paths["caption"]),
                "--record", str(override),
                "--approved",
            ]
            try:
                with mock.patch.object(sys, "argv", argv):
                    with self.assertRaisesRegex(SystemExit, "duplicate"):
                        publish_instagram.main()
            finally:
                for name, value in originals.items():
                    setattr(publish_instagram, {
                        "download": "download_remote_media",
                        "legacy": "legacy_environment_credentials",
                        "resolver": "resolve_host",
                    }[name], value)
            self.assertFalse(network_called)

    def test_malformed_publish_record_fails_closed_before_instagram_writes(self):
        import publish_instagram

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _make_package(root)
            bad = root / "instagram-publish-broken.json"
            bad.write_text("not-json", encoding="utf-8")
            network_called = []
            originals = {
                "download": publish_instagram.download_remote_media,
                "legacy": publish_instagram.legacy_environment_credentials,
                "resolver": publish_instagram.resolve_host,
            }
            publish_instagram.download_remote_media = lambda *a, **k: network_called.append(True)
            publish_instagram.legacy_environment_credentials = lambda environ=None: {
                "INSTAGRAM_ACCESS_TOKEN": "tok",
                "INSTAGRAM_USER_ID": "12345",
            }
            publish_instagram.resolve_host = lambda host: [PUBLIC_TEST_IP]
            argv = [
                "publish_instagram.py",
                "--video", str(paths["video"]),
                "--video-url", "https://cdn.example.com/video.mp4",
                "--verification", str(paths["verification"]),
                "--caption-file", str(paths["caption"]),
                "--approved",
            ]
            try:
                with mock.patch.object(sys, "argv", argv):
                    with self.assertRaisesRegex(SystemExit, "invalid publish record"):
                        publish_instagram.main()
            finally:
                for name, value in originals.items():
                    setattr(publish_instagram, {
                        "download": "download_remote_media",
                        "legacy": "legacy_environment_credentials",
                        "resolver": "resolve_host",
                    }[name], value)
            self.assertFalse(network_called)

    def test_publish_record_atomically_replaces_symlink_without_touching_target(self):
        from publish_instagram import write_publish_record_atomic

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "outside.json"
            outside.write_text("DO NOT OVERWRITE\n", encoding="utf-8")
            record = root / "instagram-publish-travel.json"
            record.symlink_to(outside)
            write_publish_record_atomic(record, {
                "platform": "instagram",
                "target": {"key": "travel", "id": "1", "username": "frog"},
                "timestamp": "2026-01-01T00:00:00+0000",
                "media_id": "mid",
                "permalink": "https://instagram.com/reel/abc/",
                "sha256": "abc",
                "caption_sha256": "def",
                "visibility": "public",
            })
            self.assertEqual(outside.read_text(encoding="utf-8"), "DO NOT OVERWRITE\n")
            self.assertFalse(record.is_symlink())
            self.assertEqual(json.loads(record.read_text(encoding="utf-8"))["media_id"], "mid")

    def test_dns_rebinding_blocks_connect_when_later_resolution_is_private(self):
        import publish_instagram

        resolve_calls = 0

        def rebinding_resolver(_host):
            nonlocal resolve_calls
            resolve_calls += 1
            if resolve_calls == 1:
                return [PUBLIC_TEST_IP]
            return ["127.0.0.1"]

        connections = []

        def track_create_connection(address, *args, **kwargs):
            connections.append(address)
            raise OSError("unexpected connection")

        opener = publish_instagram.build_media_opener(rebinding_resolver)
        with mock.patch("socket.create_connection", track_create_connection):
            with self.assertRaisesRegex(ValueError, "private"):
                publish_instagram.download_remote_media(
                    "https://cdn.example.com/video.mp4",
                    hashlib.sha256(VIDEO_BYTES).hexdigest(),
                    opener=opener,
                    resolver=rebinding_resolver,
                )
        self.assertEqual(connections, [])

    def test_instagram_api_opener_rejects_get_redirect_without_forwarding_token(self):
        from publish_instagram import NoRedirectHandler

        handler = NoRedirectHandler()
        request = urllib.request.Request(
            "https://graph.instagram.com/v24.0/me?access_token=secret-token",
            method="GET",
        )
        with self.assertRaisesRegex(ValueError, "must not be redirected"):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {"Location": "https://evil.example/steal"},
                "https://evil.example/steal",
            )

    def test_instagram_api_opener_rejects_post_redirect_without_forwarding_token(self):
        from publish_instagram import NoRedirectHandler

        handler = NoRedirectHandler()
        payload = urllib.parse.urlencode(
            {"creation_id": "container-1", "access_token": "secret-token"},
        ).encode()
        request = urllib.request.Request(
            "https://graph.instagram.com/v24.0/12345/media_publish",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with self.assertRaisesRegex(ValueError, "must not be redirected"):
            handler.redirect_request(
                request,
                None,
                307,
                "Temporary Redirect",
                {"Location": "https://evil.example/steal"},
                "https://evil.example/steal",
            )

    def test_readback_requires_exact_media_id_video_reels_https_permalink_and_timestamp(self):
        import publish_instagram

        base = {
            "id": "mid",
            "username": "frog",
            "media_type": "VIDEO",
            "media_product_type": "REELS",
            "permalink": "https://instagram.com/reel/abc/",
            "caption": "Approved caption",
            "timestamp": "2026-01-01T00:00:00+0000",
        }
        publish_instagram.api_get = lambda *a, **k: dict(base)
        publish_instagram.read_back_published_media(
            "tok", "mid", "v24.0", expected_username="frog", expected_caption="Approved caption",
        )

        publish_instagram.api_get = lambda *a, **k: {**base, "id": "other"}
        with self.assertRaisesRegex(ValueError, "does not match published media_id"):
            publish_instagram.read_back_published_media(
                "tok", "mid", "v24.0", expected_username="frog", expected_caption="Approved caption",
            )

        publish_instagram.api_get = lambda *a, **k: {**base, "media_type": "IMAGE"}
        with self.assertRaisesRegex(ValueError, "media_type"):
            publish_instagram.read_back_published_media(
                "tok", "mid", "v24.0", expected_username="frog", expected_caption="Approved caption",
            )

        publish_instagram.api_get = lambda *a, **k: {**base, "permalink": "http://insecure/"}
        with self.assertRaisesRegex(ValueError, "HTTPS URL"):
            publish_instagram.read_back_published_media(
                "tok", "mid", "v24.0", expected_username="frog", expected_caption="Approved caption",
            )

        publish_instagram.api_get = lambda *a, **k: {**base, "timestamp": ""}
        with self.assertRaisesRegex(ValueError, "timestamp"):
            publish_instagram.read_back_published_media(
                "tok", "mid", "v24.0", expected_username="frog", expected_caption="Approved caption",
            )

    def test_verified_record_write_failure_after_readback_is_ambiguous(self):
        import publish_instagram

        originals = {
            "download": publish_instagram.download_remote_media,
            "identity": publish_instagram.verify_registered_identity,
            "create": publish_instagram.create_reels_container,
            "poll": publish_instagram.poll_container_status,
            "publish": publish_instagram.publish_container,
            "readback": publish_instagram.read_back_published_media,
            "write": publish_instagram.write_publish_record_atomic,
            "legacy": publish_instagram.legacy_environment_credentials,
            "resolver": publish_instagram.resolve_host,
        }
        write_calls = 0

        def flaky_write(path, record):
            nonlocal write_calls
            write_calls += 1
            if write_calls == 2:
                raise OSError("disk full")
            return originals["write"](path, record)

        publish_instagram.download_remote_media = lambda *a, **k: (VIDEO_BYTES, "https://cdn.example.com/v.mp4")
        publish_instagram.verify_registered_identity = lambda *a, **k: {"id": "12345", "username": "frog"}
        publish_instagram.create_reels_container = lambda *a, **k: "container-1"
        publish_instagram.poll_container_status = lambda *a, **k: {"status_code": "FINISHED"}
        publish_instagram.publish_container = lambda *a, **k: "media-1"
        publish_instagram.read_back_published_media = lambda *a, **k: {
            "id": "media-1",
            "username": "frog",
            "media_type": "VIDEO",
            "media_product_type": "REELS",
            "permalink": "https://instagram.com/reel/abc/",
            "caption": "Approved caption",
            "timestamp": "2026-01-01T00:00:00+0000",
        }
        publish_instagram.write_publish_record_atomic = flaky_write
        publish_instagram.legacy_environment_credentials = lambda environ=None: {
            "INSTAGRAM_ACCESS_TOKEN": "tok",
            "INSTAGRAM_USER_ID": "12345",
        }
        publish_instagram.resolve_host = lambda host: [PUBLIC_TEST_IP]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _make_package(root)
            argv = [
                "publish_instagram.py",
                "--video", str(paths["video"]),
                "--video-url", "https://cdn.example.com/video.mp4",
                "--verification", str(paths["verification"]),
                "--caption-file", str(paths["caption"]),
                "--approved",
            ]
            try:
                with mock.patch.object(sys, "argv", argv):
                    with self.assertRaises(SystemExit) as ctx:
                        publish_instagram.main()
                payload = json.loads(ctx.exception.args[0])
                self.assertFalse(payload["ok"])
                self.assertTrue(payload["ambiguous"])
                self.assertTrue(payload["published"])
                self.assertEqual(payload["media_id"], "media-1")
            finally:
                for name, value in originals.items():
                    setattr(publish_instagram, {
                        "download": "download_remote_media",
                        "identity": "verify_registered_identity",
                        "create": "create_reels_container",
                        "poll": "poll_container_status",
                        "publish": "publish_container",
                        "readback": "read_back_published_media",
                        "write": "write_publish_record_atomic",
                        "legacy": "legacy_environment_credentials",
                        "resolver": "resolve_host",
                    }[name], value)

    def test_provisional_publish_record_written_after_media_publish(self):
        import publish_instagram

        originals = {
            "download": publish_instagram.download_remote_media,
            "identity": publish_instagram.verify_registered_identity,
            "create": publish_instagram.create_reels_container,
            "poll": publish_instagram.poll_container_status,
            "publish": publish_instagram.publish_container,
            "readback": publish_instagram.read_back_published_media,
            "legacy": publish_instagram.legacy_environment_credentials,
            "resolver": publish_instagram.resolve_host,
        }

        publish_instagram.download_remote_media = lambda *a, **k: (VIDEO_BYTES, "https://cdn.example.com/v.mp4")
        publish_instagram.verify_registered_identity = lambda *a, **k: {"id": "12345", "username": "frog"}
        publish_instagram.create_reels_container = lambda *a, **k: "container-1"
        publish_instagram.poll_container_status = lambda *a, **k: {"status_code": "FINISHED"}
        publish_instagram.publish_container = lambda *a, **k: "media-1"
        publish_instagram.read_back_published_media = lambda *a, **k: (_ for _ in ()).throw(
            ValueError("Instagram read-back caption does not match the approved caption"),
        )
        publish_instagram.legacy_environment_credentials = lambda environ=None: {
            "INSTAGRAM_ACCESS_TOKEN": "tok",
            "INSTAGRAM_USER_ID": "12345",
        }
        publish_instagram.resolve_host = lambda host: [PUBLIC_TEST_IP]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _make_package(root)
            argv = [
                "publish_instagram.py",
                "--video", str(paths["video"]),
                "--video-url", "https://cdn.example.com/video.mp4",
                "--verification", str(paths["verification"]),
                "--caption-file", str(paths["caption"]),
                "--approved",
            ]
            try:
                with mock.patch.object(sys, "argv", argv):
                    with self.assertRaises(SystemExit):
                        publish_instagram.main()
                record_path = root / "instagram-publish.json"
                self.assertTrue(record_path.is_file())
                record = json.loads(record_path.read_text(encoding="utf-8"))
                self.assertEqual(record["platform"], "instagram")
                self.assertEqual(record["media_id"], "media-1")
                self.assertIsNone(record["permalink"])
                self.assertIsNone(record["timestamp"])
                self.assertEqual(record["sha256"], hashlib.sha256(VIDEO_BYTES).hexdigest())
                self.assertEqual(stat.S_IMODE(record_path.stat().st_mode), 0o600)
            finally:
                for name, value in originals.items():
                    setattr(publish_instagram, {
                        "download": "download_remote_media",
                        "identity": "verify_registered_identity",
                        "create": "create_reels_container",
                        "poll": "poll_container_status",
                        "publish": "publish_container",
                        "readback": "read_back_published_media",
                        "legacy": "legacy_environment_credentials",
                        "resolver": "resolve_host",
                    }[name], value)

    def test_readback_failure_after_media_publish_is_ambiguous_without_blind_retry(self):
        import publish_instagram

        originals = {
            "download": publish_instagram.download_remote_media,
            "identity": publish_instagram.verify_registered_identity,
            "create": publish_instagram.create_reels_container,
            "poll": publish_instagram.poll_container_status,
            "publish": publish_instagram.publish_container,
            "readback": publish_instagram.read_back_published_media,
            "legacy": publish_instagram.legacy_environment_credentials,
            "resolver": publish_instagram.resolve_host,
        }

        publish_instagram.download_remote_media = lambda *a, **k: (VIDEO_BYTES, "https://cdn.example.com/v.mp4")
        publish_instagram.verify_registered_identity = lambda *a, **k: {"id": "12345", "username": "frog"}
        publish_instagram.create_reels_container = lambda *a, **k: "container-1"
        publish_instagram.poll_container_status = lambda *a, **k: {"status_code": "FINISHED"}
        publish_instagram.publish_container = lambda *a, **k: "media-1"
        publish_instagram.read_back_published_media = lambda *a, **k: (_ for _ in ()).throw(
            ValueError("Instagram read-back caption does not match the approved caption"),
        )
        publish_instagram.legacy_environment_credentials = lambda environ=None: {
            "INSTAGRAM_ACCESS_TOKEN": "secret-token",
            "INSTAGRAM_USER_ID": "12345",
        }
        publish_instagram.resolve_host = lambda host: [PUBLIC_TEST_IP]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _make_package(root)
            argv = [
                "publish_instagram.py",
                "--video", str(paths["video"]),
                "--video-url", "https://cdn.example.com/video.mp4",
                "--verification", str(paths["verification"]),
                "--caption-file", str(paths["caption"]),
                "--approved",
            ]
            try:
                with mock.patch.object(sys, "argv", argv):
                    with self.assertRaises(SystemExit) as ctx:
                        publish_instagram.main()
                payload = json.loads(ctx.exception.args[0])
                self.assertFalse(payload["ok"])
                self.assertTrue(payload["ambiguous"])
                self.assertTrue(payload["published"])
                self.assertEqual(payload["media_id"], "media-1")
                self.assertNotIn("secret-token", json.dumps(payload))
            finally:
                for name, value in originals.items():
                    setattr(publish_instagram, {
                        "download": "download_remote_media",
                        "identity": "verify_registered_identity",
                        "create": "create_reels_container",
                        "poll": "poll_container_status",
                        "publish": "publish_container",
                        "readback": "read_back_published_media",
                        "legacy": "legacy_environment_credentials",
                        "resolver": "resolve_host",
                    }[name], value)

    def test_ambiguous_failure_emits_safe_json_without_tokens(self):
        import publish_instagram

        originals = {
            "create": publish_instagram.create_reels_container,
            "poll": publish_instagram.poll_container_status,
            "download": publish_instagram.download_remote_media,
            "identity": publish_instagram.verify_registered_identity,
            "legacy": publish_instagram.legacy_environment_credentials,
            "resolver": publish_instagram.resolve_host,
        }

        def fail_poll(*args, **kwargs):
            raise TimeoutError("container not ready before the status timeout")

        publish_instagram.create_reels_container = lambda *a, **k: "container-1"
        publish_instagram.poll_container_status = fail_poll
        publish_instagram.download_remote_media = lambda *a, **k: (VIDEO_BYTES, "https://cdn.example.com/v.mp4")
        publish_instagram.verify_registered_identity = lambda *a, **k: {"id": "12345", "username": "frog"}
        publish_instagram.legacy_environment_credentials = lambda environ=None: {
            "INSTAGRAM_ACCESS_TOKEN": "secret-token",
            "INSTAGRAM_USER_ID": "12345",
        }
        publish_instagram.resolve_host = lambda host: [PUBLIC_TEST_IP]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _make_package(root)
            argv = [
                "publish_instagram.py",
                "--video", str(paths["video"]),
                "--video-url", "https://cdn.example.com/video.mp4",
                "--verification", str(paths["verification"]),
                "--caption-file", str(paths["caption"]),
                "--approved",
            ]
            try:
                with mock.patch.object(sys, "argv", argv):
                    with self.assertRaises(SystemExit) as ctx:
                        publish_instagram.main()
                payload = json.loads(ctx.exception.args[0])
                self.assertFalse(payload["ok"])
                self.assertTrue(payload["ambiguous"])
                self.assertEqual(payload["container_id"], "container-1")
                self.assertNotIn("secret-token", json.dumps(payload))
            finally:
                publish_instagram.create_reels_container = originals["create"]
                publish_instagram.poll_container_status = originals["poll"]
                publish_instagram.download_remote_media = originals["download"]
                publish_instagram.verify_registered_identity = originals["identity"]
                publish_instagram.legacy_environment_credentials = originals["legacy"]
                publish_instagram.resolve_host = originals["resolver"]

    def test_successful_publish_writes_record_and_exact_readback(self):
        import publish_instagram

        calls = []
        originals = {
            "download": publish_instagram.download_remote_media,
            "identity": publish_instagram.verify_registered_identity,
            "create": publish_instagram.create_reels_container,
            "poll": publish_instagram.poll_container_status,
            "publish": publish_instagram.publish_container,
            "readback": publish_instagram.read_back_published_media,
            "legacy": publish_instagram.legacy_environment_credentials,
            "resolver": publish_instagram.resolve_host,
        }

        def track_create(*a, **k):
            calls.append("create")
            return "container-1"

        def track_publish(*a, **k):
            calls.append("publish")
            return "media-1"

        publish_instagram.download_remote_media = lambda *a, **k: (VIDEO_BYTES, "https://cdn.example.com/v.mp4")
        publish_instagram.verify_registered_identity = lambda *a, **k: {"id": "12345", "username": "frog"}
        publish_instagram.create_reels_container = track_create
        publish_instagram.poll_container_status = lambda *a, **k: {"status_code": "FINISHED"}
        publish_instagram.publish_container = track_publish
        publish_instagram.read_back_published_media = lambda *a, **k: {
            "id": "media-1",
            "username": "frog",
            "media_type": "VIDEO",
            "media_product_type": "REELS",
            "permalink": "https://instagram.com/reel/abc/",
            "caption": "Approved caption",
            "timestamp": "2026-01-01T00:00:00+0000",
        }
        publish_instagram.legacy_environment_credentials = lambda environ=None: {
            "INSTAGRAM_ACCESS_TOKEN": "tok",
            "INSTAGRAM_USER_ID": "12345",
        }
        publish_instagram.resolve_host = lambda host: [PUBLIC_TEST_IP]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _make_package(root)
            argv = [
                "publish_instagram.py",
                "--video", str(paths["video"]),
                "--video-url", "https://cdn.example.com/video.mp4",
                "--verification", str(paths["verification"]),
                "--caption-file", str(paths["caption"]),
                "--approved",
            ]
            buffer = io.StringIO()
            try:
                with mock.patch.object(sys, "argv", argv), mock.patch("sys.stdout", buffer):
                    publish_instagram.main()
                payload = json.loads(buffer.getvalue())
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["id"], "media-1")
                self.assertEqual(calls, ["create", "publish"])
                record_path = root / "instagram-publish.json"
                self.assertTrue(record_path.is_file())
                record = json.loads(record_path.read_text(encoding="utf-8"))
                self.assertEqual(record["sha256"], hashlib.sha256(VIDEO_BYTES).hexdigest())
                self.assertEqual(record["platform"], "instagram")
            finally:
                for name, value in originals.items():
                    setattr(publish_instagram, {
                        "download": "download_remote_media",
                        "identity": "verify_registered_identity",
                        "create": "create_reels_container",
                        "poll": "poll_container_status",
                        "publish": "publish_container",
                        "readback": "read_back_published_media",
                        "legacy": "legacy_environment_credentials",
                        "resolver": "resolve_host",
                    }[name], value)

    def test_local_hash_mismatch_fails_before_credentials(self):
        import publish_instagram

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _make_package(root)
            paths["video"].write_bytes(b"tampered")
            credentials_called = []
            network_called = []
            publish_instagram.legacy_environment_credentials = lambda environ=None: credentials_called.append(True)
            publish_instagram.download_remote_media = lambda *a, **k: network_called.append(True)
            argv = [
                "publish_instagram.py",
                "--video", str(paths["video"]),
                "--video-url", "https://cdn.example.com/video.mp4",
                "--verification", str(paths["verification"]),
                "--caption-file", str(paths["caption"]),
                "--approved",
            ]
            with mock.patch.object(sys, "argv", argv):
                with self.assertRaisesRegex(SystemExit, "video hash"):
                    publish_instagram.main()
            self.assertFalse(credentials_called)
            self.assertFalse(network_called)

    def test_legacy_environment_credentials_remain_supported(self):
        from publish_instagram import legacy_environment_credentials

        env = {
            "INSTAGRAM_ACCESS_TOKEN": "tok",
            "INSTAGRAM_USER_ID": "12345",
            "INSTAGRAM_API_VERSION": "v24.0",
        }
        self.assertEqual(legacy_environment_credentials(env)["INSTAGRAM_ACCESS_TOKEN"], "tok")

    def test_approval_gate_runs_before_opener_construction(self):
        import publish_instagram

        args = argparse.Namespace(approved=False)
        with mock.patch.object(
            publish_instagram,
            "build_api_opener",
            side_effect=AssertionError("API opener constructed before approval"),
        ), mock.patch.object(
            publish_instagram,
            "build_media_opener",
            side_effect=AssertionError("media opener constructed before approval"),
        ):
            with self.assertRaisesRegex(SystemExit, "explicit --approved"):
                publish_instagram.publish(args)

    def test_connect_time_resolution_rejects_mixed_public_and_private_answers(self):
        from publish_instagram import select_public_ip

        with self.assertRaisesRegex(ValueError, "private"):
            select_public_ip([PUBLIC_TEST_IP, "127.0.0.1"])

    def test_pinned_handler_parses_host_without_deprecation_warning(self):
        from publish_instagram import PinnedHTTPSHandler

        handler = PinnedHTTPSHandler(resolver=lambda _host: [PUBLIC_TEST_IP])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            connection = handler._make_connection("cdn.example.com:443")
        self.assertEqual(connection._pinned_ip, PUBLIC_TEST_IP)
        self.assertFalse([
            item for item in caught if issubclass(item.category, DeprecationWarning)
        ])

    def test_create_container_failure_is_ambiguous_after_write_attempt(self):
        import publish_instagram

        with tempfile.TemporaryDirectory() as directory:
            paths = _make_package(Path(directory))
            args = argparse.Namespace(
                approved=True,
                video=paths["video"],
                video_url="https://cdn.example.com/video.mp4",
                verification=paths["verification"],
                caption_file=paths["caption"],
                account=None,
                record=None,
                share_to_feed=False,
                status_timeout=1,
                status_interval=0,
            )
            with mock.patch.object(
                publish_instagram,
                "legacy_environment_credentials",
                return_value={
                    "INSTAGRAM_ACCESS_TOKEN": "secret-token",
                    "INSTAGRAM_USER_ID": "12345",
                },
            ), mock.patch.object(
                publish_instagram,
                "download_remote_media",
                return_value=(VIDEO_BYTES, args.video_url),
            ), mock.patch.object(
                publish_instagram,
                "verify_registered_identity",
                return_value={"id": "12345", "username": "frog"},
            ), mock.patch.object(
                publish_instagram,
                "create_reels_container",
                side_effect=ValueError("Instagram API request failed: HTTP 500"),
            ):
                with self.assertRaises(SystemExit) as caught:
                    publish_instagram.publish(
                        args,
                        api_opener=object(),
                        media_opener=object(),
                        resolver=lambda _host: [PUBLIC_TEST_IP],
                    )
            payload = json.loads(caught.exception.args[0])
            self.assertTrue(payload["ambiguous"])
            self.assertFalse(payload["container_created"])
            self.assertNotIn("secret-token", json.dumps(payload))

    def test_record_override_symlink_path_is_not_resolved_to_its_target(self):
        from publish_instagram import resolve_record_path

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "reel-short.mp4"
            target = root / "outside.json"
            target.write_text("outside", encoding="utf-8")
            override = root / "instagram-publish-custom.json"
            override.symlink_to(target)
            selected = resolve_record_path(video, override, None)
            self.assertEqual(selected, override.absolute())
            self.assertNotEqual(selected, target.resolve())

    def test_duplicate_detection_survives_legacy_to_registry_migration(self):
        from publish_instagram import duplicate_record_blocks

        record = {
            "platform": "instagram",
            "target": {"key": "legacy-env", "id": "12345", "username": "frog"},
            "sha256": "video-sha",
        }
        self.assertTrue(duplicate_record_blocks(record, "video-sha", "travel", "12345"))

    def test_graph_api_rejects_non_object_json_and_incomplete_bodies(self):
        from publish_instagram import api_get

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        class ListOpener:
            def open(self, _request, timeout=120):
                return Response(b"[]")

        with self.assertRaisesRegex(ValueError, "JSON object"):
            api_get("https://graph.instagram.com/v24.0/me", "secret", opener=ListOpener())

        class BrokenResponse(Response):
            def read(self, *_args, **_kwargs):
                raise http.client.IncompleteRead(b"{")

        class BrokenOpener:
            def open(self, _request, timeout=120):
                return BrokenResponse()

        with self.assertRaisesRegex(ValueError, "response body"):
            api_get("https://graph.instagram.com/v24.0/me", "secret", opener=BrokenOpener())

    def test_media_url_requires_dns_hostname_not_literal_public_ip(self):
        from publish_instagram import validate_public_https_url

        with self.assertRaisesRegex(ValueError, "DNS hostname"):
            validate_public_https_url(f"https://{PUBLIC_TEST_IP}/video.mp4", resolve=False)
    def test_record_override_must_remain_discoverable_in_package_directory(self):
        from publish_instagram import resolve_record_path

        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as other:
            root = Path(directory)
            video = root / "reel-short.mp4"
            with self.assertRaisesRegex(ValueError, "instagram-publish"):
                resolve_record_path(video, root / "custom-record.json", None)
            with self.assertRaisesRegex(ValueError, "package directory"):
                resolve_record_path(video, Path(other) / "instagram-publish-custom.json", None)


if __name__ == "__main__":
    unittest.main()
