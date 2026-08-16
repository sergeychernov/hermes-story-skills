#!/usr/bin/env python3
"""Upload a verified Short and add it to the configured YouTube playlist."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

from youtube_channel_registry import credentials_for_channel
from youtube_metadata_preflight import (
    DEFAULT_MANIFEST_SCHEMA,
    DEFAULT_SCHEMA,
    verify_approved_manifest_snapshot,
)

API = "https://www.googleapis.com/youtube/v3"
THUMBNAIL_UPLOAD = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
COVER_MAX_BYTES = 2 * 1024 * 1024
JPEG_SOI = b"\xff\xd8\xff"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
AUDIENCE_TO_PRIVACY = {
    "contacts": "private",
    "everyone": "public",
    "link": "unlisted",
}


def _write_new_private_json(path: Path, payload: dict) -> Path:
    """Create a private JSON file atomically without ever replacing an existing name."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def write_publish_record(story_path: Path, record: dict) -> Path:
    """Atomically write one immutable record named by the returned video ID."""
    video_id = str(record.get("video_id") or "")
    allowed = "-_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    if not video_id or any(character not in allowed for character in video_id):
        raise ValueError("invalid video_id for publish record")
    root = story_path.parent.resolve()
    path = root / f"publish-record-{video_id}.json"
    return _write_new_private_json(path, record)


def refuse_existing_publication(story_path: Path, media_sha256: str) -> None:
    for record_path in sorted(story_path.parent.glob("publish-record-*.json")):
        if record_path.is_symlink() or not record_path.is_file():
            continue
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError(f"invalid existing publish record: {record_path.name}") from None
        if not isinstance(record, dict):
            raise ValueError(f"invalid existing publish record: {record_path.name}")
        if record.get("platform") == "youtube" and record.get("media_sha256") == media_sha256:
            raise ValueError(
                f"video bytes already have a YouTube publish record: {record_path.name}"
            )


def reserve_upload_attempt(
    story_path: Path,
    *,
    media_sha256: str,
    manifest_sha256: str,
    channel_key: str,
) -> Path:
    identity = hashlib.sha256(
        f"youtube\0{media_sha256}\0{channel_key}".encode("utf-8")
    ).hexdigest()
    path = story_path.parent.resolve() / f"youtube-upload-attempt-{identity}.json"
    payload = {
        "schema_version": 1,
        "platform": "youtube",
        "state": "upload_session_may_have_started",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "media_sha256": media_sha256,
        "manifest_sha256": manifest_sha256,
        "channel_key": channel_key,
        "do_not_retry_blindly": True,
    }
    try:
        return _write_new_private_json(path, payload)
    except FileExistsError:
        raise ValueError(
            f"an upload attempt already exists for this approved package: {path.name}; "
            "resolve it through YouTube API readback before any retry"
        ) from None


def write_upload_result(attempt_path: Path, video_id: str) -> Path:
    return _write_new_private_json(
        attempt_path.with_name(attempt_path.name.replace("attempt", "result", 1)),
        {
            "schema_version": 1,
            "platform": "youtube",
            "state": "video_id_returned",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "video_id": video_id,
            "attempt_record": attempt_path.name,
            "do_not_retry_video_upload": True,
        },
    )


def legacy_environment_credentials(environ=None) -> dict[str, str]:
    environ = os.environ if environ is None else environ
    names = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
    missing = [name for name in names if not environ.get(name)]
    if missing:
        raise ValueError("missing environment: " + ", ".join(missing))
    return {name: str(environ[name]) for name in names}


def read_tags_bytes(data: bytes) -> list[str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("YouTube tags file must be UTF-8") from exc
    tags = [line.strip() for line in text.splitlines() if line.strip()]
    tags = list(dict.fromkeys(tags))
    if not tags:
        raise ValueError("YouTube tags file is empty")
    if len(",".join(tags)) > 500:
        raise ValueError("YouTube tags exceed the 500-character limit")
    return tags


def read_tags(path: Path) -> list[str]:
    """Read one accurate YouTube tag per line."""
    return read_tags_bytes(path.read_bytes())


def read_required_text_bytes(data: bytes, label: str) -> str:
    try:
        text = data.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must be UTF-8") from exc
    if not text:
        raise ValueError(f"{label} must be non-empty")
    return text


def read_required_text(path: Path, label: str) -> str:
    return read_required_text_bytes(path.read_bytes(), label)


def req(url, data=None, headers=None, method=None):
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    return urllib.request.urlopen(request, timeout=120)


def api_json(path: str, token: str, params: dict[str, object] | None = None,
             data: dict[str, object] | None = None, method: str | None = None) -> dict:
    query = "?" + urllib.parse.urlencode(params or {}) if params else ""
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = {"Authorization": "Bearer " + token}
    if body is not None:
        headers["Content-Type"] = "application/json; charset=UTF-8"
    return json.load(req(API + path + query, body, headers, method))


def select_playlist_id(items: list[dict], title: str) -> str:
    matches = [item for item in items if (item.get("snippet") or {}).get("title") == title]
    if not matches:
        raise ValueError(f'playlist not found: exact title "{title}"')
    if len(matches) > 1:
        raise ValueError(f'multiple playlists have exact title "{title}"')
    playlist_id = matches[0].get("id")
    if not playlist_id:
        raise ValueError(f'playlist has no ID: "{title}"')
    return str(playlist_id)


def list_owned_playlists(token: str) -> list[dict]:
    items: list[dict] = []
    page_token: str | None = None
    while True:
        params: dict[str, object] = {
            "part": "id,snippet",
            "mine": "true",
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token
        page = api_json("/playlists", token, params=params)
        items.extend(page.get("items") or [])
        page_token = page.get("nextPageToken")
        if not page_token:
            return items


def verify_authorized_channel(token: str, expected_channel_id: str | None) -> dict[str, str]:
    result = api_json("/channels", token, params={"part": "id,snippet", "mine": "true"})
    items = result.get("items") or []
    if len(items) != 1:
        raise ValueError(f"expected exactly one authorized YouTube channel, got {len(items)}")
    item = items[0]
    actual_id = str(item.get("id") or "")
    title = str((item.get("snippet") or {}).get("title") or "")
    if expected_channel_id is not None and actual_id != str(expected_channel_id):
        raise ValueError("OAuth credentials do not match the selected YouTube channel")
    if not title:
        raise ValueError("authorized YouTube channel has no title")
    return {"id": actual_id, "title": title}


def add_to_playlist(token: str, playlist_id: str, video_id: str) -> str:
    result = api_json(
        "/playlistItems",
        token,
        params={"part": "snippet"},
        data={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id,
                },
            },
        },
        method="POST",
    )
    item_id = result.get("id")
    if not item_id:
        raise RuntimeError("YouTube returned no playlist item ID")
    return str(item_id)


def privacy_for_audience(audience: str) -> str:
    try:
        return AUDIENCE_TO_PRIVACY[audience]
    except KeyError:
        raise ValueError(f"unsupported audience: {audience}") from None


def build_youtube_api_metadata(
    *,
    title: str,
    description: str,
    tags: list[str],
    privacy: str,
    decisions: dict[str, object],
) -> tuple[dict[str, object], str]:
    """Build only officially writable YouTube video fields."""
    metadata: dict[str, object] = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": decisions["category_id"],
            "defaultLanguage": decisions["default_language"],
            "tags": tags,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": decisions["made_for_kids"],
            "containsSyntheticMedia": decisions["contains_synthetic_media"],
            "embeddable": decisions["embeddable"],
            "license": decisions["license"],
            "publicStatsViewable": decisions["public_stats_viewable"],
        },
    }
    parts = ["snippet", "status"]
    if decisions.get("recording_date_decision") == "set":
        recording_date = str(decisions["recording_date"])
        metadata["recordingDetails"] = {
            "recordingDate": recording_date + "T00:00:00Z",
        }
        parts.append("recordingDetails")
    return metadata, ",".join(parts)


def build_youtube_upload_url(parts: str, notify_subscribers: bool) -> str:
    return "https://www.googleapis.com/upload/youtube/v3/videos?" + urllib.parse.urlencode({
        "uploadType": "resumable",
        "part": parts,
        "notifySubscribers": str(notify_subscribers).lower(),
    })


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _png_chunk_crc(chunk_type: bytes, data: bytes) -> int:
    return zlib.crc32(chunk_type + data) & 0xFFFFFFFF


def _validate_png(data: bytes) -> None:
    if len(data) < 8 + 4 + 4 + 4:
        raise ValueError("corrupt cover image: PNG is truncated")
    offset = 8
    chunk_length = struct.unpack(">I", data[offset:offset + 4])[0]
    chunk_type = data[offset + 4:offset + 8]
    if chunk_type != b"IHDR":
        raise ValueError("corrupt cover image: PNG is missing IHDR")
    ihdr_end = offset + 8 + chunk_length + 4
    if ihdr_end > len(data):
        raise ValueError("corrupt cover image: PNG IHDR is truncated")
    ihdr_data = data[offset + 8:ihdr_end - 4]
    ihdr_crc = struct.unpack(">I", data[ihdr_end - 4:ihdr_end])[0]
    if ihdr_crc != _png_chunk_crc(b"IHDR", ihdr_data):
        raise ValueError("corrupt cover image: PNG IHDR checksum is invalid")


def _validate_jpeg(data: bytes) -> None:
    if not data.endswith(b"\xff\xd9"):
        raise ValueError("corrupt cover image: JPEG is missing EOI marker")


def validate_cover_bytes(data: bytes) -> tuple[str, bytes]:
    if len(data) > COVER_MAX_BYTES:
        raise ValueError("cover exceeds the 2 MiB limit")
    if data.startswith(JPEG_SOI):
        _validate_jpeg(data)
        return "image/jpeg", data
    if data.startswith(PNG_SIGNATURE):
        _validate_png(data)
        return "image/png", data
    raise ValueError("unsupported cover image: must be JPEG or PNG")


def validate_cover(path: Path) -> tuple[str, bytes]:
    if not path.is_file():
        raise ValueError(f"cover is missing: {path}")
    return validate_cover_bytes(path.read_bytes())


def snapshot_approved_artifacts(
    manifest_source: Path | dict[str, object],
    paths: dict[str, Path],
) -> dict[str, bytes]:
    if isinstance(manifest_source, Path):
        try:
            manifest = json.loads(manifest_source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid approval manifest: {exc}") from exc
    else:
        manifest = manifest_source
    package = manifest.get("package") if isinstance(manifest, dict) else None
    if not isinstance(package, dict):
        raise ValueError("approval manifest package must be an object")
    if set(package) != set(paths):
        raise ValueError("approval manifest package roles do not match resolved artifacts")
    snapshots: dict[str, bytes] = {}
    for role, path in paths.items():
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != package.get(role):
            raise ValueError(f"metadata preflight {role} hash does not match snapshot")
        snapshots[role] = data
    return snapshots


def require_trusted_schema(candidate: Path, trusted: Path, label: str) -> None:
    try:
        candidate_hash = hashlib.sha256(candidate.read_bytes()).digest()
        trusted_hash = hashlib.sha256(trusted.read_bytes()).digest()
    except OSError as exc:
        raise ValueError(f"cannot read {label}: {exc}") from exc
    if candidate_hash != trusted_hash:
        raise ValueError(f"untrusted {label}: content differs from installed schema")


def _snapshot_pointer(document: object, pointer: object) -> object:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError(f"invalid resolver JSON pointer: {pointer!r}")
    current = document
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise ValueError(f"resolver JSON pointer is missing in report snapshot: {pointer}")
        current = current[token]
    return current


def validate_snapshot_eligibility(
    config: dict[str, object],
    schema: dict[str, object],
    snapshots: dict[str, bytes],
) -> None:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("publication schema properties must be an object")
    provenance_fields: dict[str, tuple[str, str]] = {}
    for field, raw_schema in properties.items():
        if not isinstance(raw_schema, dict):
            continue
        rule = raw_schema.get("x-auto-resolve")
        role = raw_schema.get("x-file-role")
        if isinstance(rule, dict) and rule.get("kind") == "provenance-report":
            source = rule.get("source_field")
            if not isinstance(source, str) or not isinstance(role, str):
                raise ValueError(f"invalid provenance resolver for {field}")
            provenance_fields[source] = (field, role)
    for field, raw_schema in properties.items():
        if not isinstance(raw_schema, dict):
            continue
        rule = raw_schema.get("x-auto-resolve")
        source_role = raw_schema.get("x-file-role")
        if not isinstance(rule, dict) or rule.get("kind") != "json-report-value":
            continue
        if not isinstance(source_role, str) or field not in provenance_fields:
            raise ValueError(f"report-backed resolver lacks snapshot roles: {field}")
        _report_field, report_role = provenance_fields[field]
        try:
            report = json.loads(snapshots[report_role].decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid {report_role} snapshot: {exc}") from exc
        if not isinstance(report, dict):
            raise ValueError(f"{report_role} snapshot must contain an object")
        for predicate in rule.get("predicates", []):
            if not isinstance(predicate, dict):
                raise ValueError(f"invalid resolver predicate for {field}")
            actual = _snapshot_pointer(report, predicate.get("pointer"))
            if "equals" in predicate:
                matched = actual == predicate["equals"]
            elif isinstance(predicate.get("enum"), list):
                matched = actual in predicate["enum"]
            else:
                raise ValueError(f"invalid resolver predicate for {field}")
            if not matched:
                raise ValueError(f"{report_role} snapshot is no longer eligible")
        if _snapshot_pointer(report, rule.get("value_pointer")) != config.get(field):
            raise ValueError(f"{report_role} snapshot does not prove configured {field}")
        declared_hash = _snapshot_pointer(report, rule.get("hash_pointer"))
        actual_hash = hashlib.sha256(snapshots[source_role]).hexdigest()
        if declared_hash != actual_hash:
            raise ValueError(f"{report_role} snapshot hash does not prove {source_role}")


def verify_four_frame_cover_bytes(video_bytes: bytes) -> dict[str, object]:
    """Decode frames 0..4 and prove the four-frame Shorts cover contract."""
    try:
        with tempfile.TemporaryDirectory(prefix="youtube-cover-gate-") as directory:
            root = Path(directory)
            video = root / "snapshot.mp4"
            video.write_bytes(video_bytes)
            probe = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height,r_frame_rate,avg_frame_rate,start_time",
                    "-of", "json", str(video),
                ],
                check=True, capture_output=True, text=True, timeout=60,
            )
            streams = json.loads(probe.stdout).get("streams") or []
            if len(streams) != 1:
                raise ValueError("approved video snapshot must contain exactly one video stream")
            stream = streams[0]
            if stream.get("r_frame_rate") != "30/1" or stream.get("avg_frame_rate") != "30/1":
                raise ValueError("approved video snapshot must be exact CFR 30/1")
            if float(stream.get("start_time", "0")) != 0.0:
                raise ValueError("approved video snapshot must start at video PTS zero")
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
                    "-vf", r"select=lte(n\,4)", "-vsync", "0", "-frames:v", "5",
                    str(root / "frame-%d.png"),
                ],
                check=True, capture_output=True, timeout=120,
            )
            frames = [root / f"frame-{index}.png" for index in range(1, 6)]
            if not all(frame.is_file() for frame in frames):
                raise ValueError("approved video snapshot has fewer than five decoded frames")

            def ssim(left: Path, right: Path) -> float:
                result = subprocess.run(
                    [
                        "ffmpeg", "-hide_banner", "-i", str(left), "-i", str(right),
                        "-lavfi", "ssim", "-f", "null", "-",
                    ],
                    check=True, capture_output=True, text=True, timeout=60,
                )
                matches = re.findall(r"All:([0-9.]+)", result.stderr)
                if not matches:
                    raise ValueError("ffmpeg did not report SSIM for opening frames")
                return float(matches[-1])

            cover_ssim = [ssim(frames[0], frames[index]) for index in range(1, 4)]
            first_live_ssim = ssim(frames[0], frames[4])
            if min(cover_ssim) < 0.995:
                raise ValueError("decoded frames 0..3 are not the same approved cover")
            if first_live_ssim >= 0.995:
                raise ValueError("decoded frame 4 is still the cover, not the first live frame")
            return {
                "cover_frames": 4,
                "first_live_frame": 4,
                "cover_ssim": cover_ssim,
                "first_live_ssim": first_live_ssim,
            }
    except FileNotFoundError as exc:
        raise ValueError(f"required media verifier is unavailable: {exc.filename}") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot verify four-frame cover from approved video bytes: {exc}") from exc


def verify_approved_package(video: Path, cover: Path, verification: Path) -> dict[str, object]:
    if not video.is_file():
        raise ValueError(f"video is missing: {video}")
    try:
        report = json.loads(verification.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid verification report: {exc}") from exc
    if report.get("ok") is not True:
        raise ValueError("verification report is not green")
    expected_video = (report.get("video") or {}).get("sha256")
    video_bytes = video.read_bytes()
    actual_video = hashlib.sha256(video_bytes).hexdigest()
    if not expected_video or expected_video != actual_video:
        raise ValueError("video hash does not match verification report")
    cover_mime, cover_bytes = validate_cover(cover)
    expected_cover = (report.get("cover") or {}).get("sha256")
    actual_cover = hashlib.sha256(cover_bytes).hexdigest()
    if not expected_cover or expected_cover != actual_cover:
        raise ValueError("cover hash does not match verification report")
    return {
        "video_sha256": actual_video,
        "video_bytes": video_bytes,
        "cover_sha256": actual_cover,
        "cover_mime": cover_mime,
        "cover_bytes": cover_bytes,
    }


def upload_thumbnail(token: str, video_id: str, cover: bytes, content_type: str) -> dict:
    url = THUMBNAIL_UPLOAD + "?" + urllib.parse.urlencode({
        "videoId": video_id,
        "uploadType": "media",
    })
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": content_type,
        "Content-Length": str(len(cover)),
    }
    result = json.load(req(url, cover, headers, "POST"))
    if result.get("kind") != "youtube#thumbnailSetResponse" or not result.get("items"):
        raise RuntimeError("YouTube thumbnail upload returned an invalid response")
    return result


def _same_recording_date(left: object, right: object) -> bool:
    if left is None or right is None:
        return left is right
    def parse(value: object) -> datetime:
        text = str(value)
        return datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    try:
        return parse(left).date() == parse(right).date()
    except ValueError:
        return False


def wait_for_verified_upload(
    token: str,
    video_id: str,
    expected: dict[str, object],
    privacy: str,
    *,
    timeout: float = 600,
    interval: float = 5,
) -> dict[str, str]:
    """Poll processing and read back the exact public metadata we submitted."""
    deadline = time.monotonic() + max(0, timeout)
    while True:
        response = api_json(
            "/videos",
            token,
            params={
                "part": "snippet,status,recordingDetails,processingDetails",
                "id": video_id,
            },
        )
        items = response.get("items") or []
        if len(items) != 1:
            raise ValueError("uploaded video is not readable by ID")
        item = items[0]
        processing = (item.get("processingDetails") or {}).get("processingStatus")
        upload_status = (item.get("status") or {}).get("uploadStatus")
        if processing in {"failed", "terminated"} or upload_status in {"failed", "rejected", "deleted"}:
            raise ValueError(f"YouTube processing failed: {processing or upload_status}")
        if processing == "succeeded" and upload_status == "processed":
            snippet = item.get("snippet") or {}
            status = item.get("status") or {}
            actual = {
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "tags": snippet.get("tags") or [],
            }
            if (
                actual["title"] != expected["title"]
                or actual["description"] != expected["description"]
                or sorted(set(actual["tags"])) != sorted(set(expected["tags"]))
            ):
                raise ValueError("YouTube read-back metadata does not match the approved metadata")
            if status.get("privacyStatus") != privacy:
                raise ValueError("YouTube read-back privacy does not match the approved audience")
            extended_actual = {
                "category_id": snippet.get("categoryId"),
                "default_language": snippet.get("defaultLanguage"),
                "made_for_kids": status.get("selfDeclaredMadeForKids"),
                "contains_synthetic_media": status.get("containsSyntheticMedia") is True,
                "embeddable": status.get("embeddable"),
                "license": status.get("license"),
                "public_stats_viewable": status.get("publicStatsViewable"),
                "recording_date": (item.get("recordingDetails") or {}).get("recordingDate"),
            }
            for field, actual_value in extended_actual.items():
                if field not in expected:
                    continue
                expected_value = expected[field]
                matches = (
                    _same_recording_date(actual_value, expected_value)
                    if field == "recording_date"
                    else actual_value == expected_value
                )
                if not matches:
                    raise ValueError(
                        "YouTube read-back extended metadata does not match "
                        f"approved field: {field}"
                    )
            return {
                "processing_status": str(processing or upload_status),
                "privacy": str(status.get("privacyStatus")),
            }
        if time.monotonic() >= deadline:
            raise TimeoutError("YouTube processing did not finish before the verification timeout")
        time.sleep(max(0, interval))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--story",
        type=Path,
        help="story.json containing publication.targets.youtube validated by JSON Schema",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA,
        help="YouTube publication JSON Schema",
    )
    parser.add_argument(
        "--manifest-schema",
        type=Path,
        default=DEFAULT_MANIFEST_SCHEMA,
        help="Approved preflight manifest JSON Schema",
    )
    parser.add_argument(
        "--metadata-preflight",
        type=Path,
        help="User-approved, schema/config/file-hash-bound YouTube manifest",
    )
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--processing-timeout", type=float, default=600)
    args = parser.parse_args()
    if not args.approved:
        raise SystemExit("Refusing publication without explicit --approved after the user command")
    if args.story is None:
        raise SystemExit("Refusing publication without --story configuration")
    if args.metadata_preflight is None:
        raise SystemExit(
            "Refusing publication without --metadata-preflight after resolving "
            "schema-derived questions and showing the exact normalized config"
        )
    try:
        require_trusted_schema(args.schema, DEFAULT_SCHEMA, "publication schema")
        require_trusted_schema(
            args.manifest_schema, DEFAULT_MANIFEST_SCHEMA, "approval manifest schema"
        )
        decisions, manifest, schema, paths = verify_approved_manifest_snapshot(
            args.metadata_preflight,
            args.story,
            args.schema,
            args.manifest_schema,
        )
        snapshots = snapshot_approved_artifacts(manifest, paths)
        validate_snapshot_eligibility(decisions, schema, snapshots)
        title = read_required_text_bytes(snapshots["title_file"], "title")
        description = read_required_text_bytes(snapshots["description_file"], "description")
        tags = read_tags_bytes(snapshots["tags_file"])
        if (
            decisions.get("location_decision") == "description"
            and decisions.get("location_text") not in description
        ):
            raise ValueError(
                "location_text must appear exactly in the snapshotted description_file"
            )
        cover_mime, cover_bytes = validate_cover_bytes(snapshots["cover"])
        timeline_evidence = verify_four_frame_cover_bytes(snapshots["video"])
        video_sha256 = hashlib.sha256(snapshots["video"]).hexdigest()
        refuse_existing_publication(args.story, video_sha256)
        manifest_sha256 = hashlib.sha256(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        approved = {
            "video_bytes": snapshots["video"],
            "video_sha256": video_sha256,
            "cover_bytes": cover_bytes,
            "cover_mime": cover_mime,
            "cover_sha256": hashlib.sha256(cover_bytes).hexdigest(),
            "timeline_evidence": timeline_evidence,
        }
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    privacy = privacy_for_audience(str(decisions["audience"]))
    channel_key = str(decisions["channel_key"])
    playlist_title = str(decisions["playlist_title"])

    try:
        if channel_key == "legacy-env":
            credentials = legacy_environment_credentials()
            expected_channel_id = None
        else:
            selected_channel, credentials = credentials_for_channel(channel_key)
            expected_channel_id = selected_channel["channel_id"]
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    token_data = urllib.parse.urlencode({
        "client_id": credentials["YOUTUBE_CLIENT_ID"],
        "client_secret": credentials["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": credentials["YOUTUBE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    token = json.load(req(
        "https://oauth2.googleapis.com/token",
        token_data,
        {"Content-Type": "application/x-www-form-urlencoded"},
    ))["access_token"]

    try:
        live_channel = verify_authorized_channel(token, expected_channel_id)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    # Resolve before upload so a missing/duplicate playlist cannot leave a Short
    # outside the required playlist.
    try:
        playlist_id = select_playlist_id(list_owned_playlists(token), playlist_title)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    meta, write_parts = build_youtube_api_metadata(
        title=title,
        description=description,
        tags=tags,
        privacy=privacy,
        decisions=decisions,
    )
    body = json.dumps(meta).encode()
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(len(approved["video_bytes"])),
    }
    try:
        attempt_path = reserve_upload_attempt(
            args.story,
            media_sha256=approved["video_sha256"],
            manifest_sha256=manifest_sha256,
            channel_key=channel_key,
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    video_id = None
    try:
        start = req(
            build_youtube_upload_url(write_parts, decisions["notify_subscribers"]),
            body,
            headers,
            "POST",
        )
        location = start.headers["Location"]
        result = json.load(req(
            location,
            approved["video_bytes"],
            {
                "Authorization": "Bearer " + token,
                "Content-Type": "video/mp4",
                "Content-Length": str(len(approved["video_bytes"])),
            },
            "PUT",
        ))
        video_id = result.get("id")
        if not isinstance(video_id, str) or not video_id:
            raise ValueError("YouTube upload response did not contain a video ID")
        upload_result_path = write_upload_result(attempt_path, video_id)
    except Exception as exc:
        safe = {
            "ok": False,
            "platform": "youtube",
            "video_upload_state": "video_id_returned" if video_id else "ambiguous",
            "video_uploaded": True if video_id else None,
            "id": video_id,
            "upload_attempt_record": str(attempt_path),
            "do_not_retry": True,
            "error_type": type(exc).__name__,
        }
        raise SystemExit(json.dumps(safe, ensure_ascii=False)) from None

    approved_metadata = {
        "title": meta["snippet"]["title"],
        "description": meta["snippet"]["description"],
        "tags": tags,
        "category_id": decisions["category_id"],
        "default_language": decisions["default_language"],
        "made_for_kids": decisions["made_for_kids"],
        "contains_synthetic_media": decisions["contains_synthetic_media"],
        "embeddable": decisions["embeddable"],
        "license": decisions["license"],
        "public_stats_viewable": decisions["public_stats_viewable"],
        "recording_date": decisions.get("recording_date"),
    }
    try:
        readback = wait_for_verified_upload(
            token,
            video_id,
            approved_metadata,
            privacy,
            timeout=args.processing_timeout,
        )
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError, TimeoutError) as exc:
        safe = {
            "ok": False,
            "platform": "youtube",
            "video_uploaded": True,
            "id": video_id,
            "url": "https://youtu.be/" + video_id,
            "readback_verified": False,
            "error_type": type(exc).__name__,
        }
        raise SystemExit(json.dumps(safe, ensure_ascii=False)) from None

    try:
        thumb_response = upload_thumbnail(
            token,
            video_id,
            approved["cover_bytes"],
            approved["cover_mime"],
        )
    except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, ValueError) as exc:
        safe = {
            "ok": False,
            "platform": "youtube",
            "video_uploaded": True,
            "thumbnail_uploaded": False,
            "id": video_id,
            "url": "https://youtu.be/" + video_id,
            "readback_verified": True,
            "error_type": type(exc).__name__,
        }
        raise SystemExit(json.dumps(safe, ensure_ascii=False)) from None

    try:
        playlist_item_id = add_to_playlist(token, playlist_id, video_id)
    except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, ValueError) as exc:
        safe = {
            "ok": False,
            "platform": "youtube",
            "video_uploaded": True,
            "thumbnail_uploaded": True,
            "id": video_id,
            "url": "https://youtu.be/" + video_id,
            "playlist_added": False,
            "playlist_title": playlist_title,
            "error_type": type(exc).__name__,
        }
        raise SystemExit(json.dumps(safe, ensure_ascii=False)) from None

    publish_record = {
        "schema_version": 1,
        "platform": "youtube",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "channel": {
            "key": channel_key,
            "id": live_channel["id"],
            "title": live_channel["title"],
        },
        "video_id": video_id,
        "url": "https://youtu.be/" + video_id,
        "visibility": privacy,
        "media_sha256": approved["video_sha256"],
        "upload_attempt_record": attempt_path.name,
        "upload_result_record": upload_result_path.name,
        "timeline_evidence": approved["timeline_evidence"],
        "processing": {
            "upload_status": "processed",
            "processing_status": readback["processing_status"],
            "metadata_readback_verified": True,
        },
        "thumbnail": {
            "uploaded": True,
            "api_kind": thumb_response["kind"],
            "source_path": decisions["cover_path"],
            "source_sha256": approved["cover_sha256"],
        },
        "playlist": {
            "id": playlist_id,
            "title": playlist_title,
            "item_id": playlist_item_id,
        },
        "telegram_url_released": False,
    }
    try:
        record_path = write_publish_record(args.story, publish_record)
    except (OSError, ValueError) as exc:
        safe = {
            "ok": False,
            "platform": "youtube",
            "video_uploaded": True,
            "thumbnail_uploaded": True,
            "playlist_added": True,
            "id": video_id,
            "url": "https://youtu.be/" + video_id,
            "readback_verified": True,
            "record_written": False,
            "error_type": type(exc).__name__,
        }
        raise SystemExit(json.dumps(safe, ensure_ascii=False)) from None

    print(json.dumps({
        "ok": True,
        "platform": "youtube",
        "channel": {
            "key": channel_key,
            "id": live_channel["id"],
            "title": live_channel["title"],
        },
        "id": video_id,
        "url": "https://youtu.be/" + video_id,
        "audience": decisions["audience"],
        "privacy": privacy,
        "sha256": approved["video_sha256"],
        "readback_verified": True,
        "processing_status": readback["processing_status"],
        "tags": tags,
        "thumbnail": {
            "uploaded": True,
            "path": str(paths["cover"]),
            "sha256": approved["cover_sha256"],
            "api_kind": thumb_response["kind"],
        },
        "playlist": {
            "id": playlist_id,
            "title": playlist_title,
            "item_id": playlist_item_id,
        },
        "record": str(record_path),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
