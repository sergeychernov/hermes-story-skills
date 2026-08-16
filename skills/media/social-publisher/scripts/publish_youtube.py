#!/usr/bin/env python3
"""Upload a verified Short and add it to the configured YouTube playlist."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

from youtube_channel_registry import credentials_for_channel

DEFAULT_SHORTS_PLAYLIST = "Лягушка-путешественница"
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


def legacy_environment_credentials(environ=None) -> dict[str, str]:
    environ = os.environ if environ is None else environ
    names = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
    missing = [name for name in names if not environ.get(name)]
    if missing:
        raise ValueError("missing environment: " + ", ".join(missing))
    return {name: str(environ[name]) for name in names}


def read_tags(path: Path) -> list[str]:
    """Read one accurate YouTube tag per line."""
    tags = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    tags = list(dict.fromkeys(tags))
    if not tags:
        raise ValueError("YouTube tags file is empty")
    if len(",".join(tags)) > 500:
        raise ValueError("YouTube tags exceed the 500-character limit")
    return tags


def read_required_text(path: Path, label: str) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{label} must be non-empty")
    return text


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


def validate_cover(path: Path) -> tuple[str, bytes]:
    if not path.is_file():
        raise ValueError(f"cover is missing: {path}")
    size = path.stat().st_size
    if size > COVER_MAX_BYTES:
        raise ValueError("cover exceeds the 2 MiB limit")
    data = path.read_bytes()
    if len(data) > COVER_MAX_BYTES:
        raise ValueError("cover exceeds the 2 MiB limit")
    if data.startswith(JPEG_SOI):
        _validate_jpeg(data)
        return "image/jpeg", data
    if data.startswith(PNG_SIGNATURE):
        _validate_png(data)
        return "image/png", data
    raise ValueError("unsupported cover image: must be JPEG or PNG")


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
            params={"part": "snippet,status,processingDetails", "id": video_id},
        )
        items = response.get("items") or []
        if len(items) != 1:
            raise ValueError("uploaded video is not readable by ID")
        item = items[0]
        processing = (item.get("processingDetails") or {}).get("processingStatus")
        upload_status = (item.get("status") or {}).get("uploadStatus")
        if processing in {"failed", "terminated"} or upload_status in {"failed", "rejected", "deleted"}:
            raise ValueError(f"YouTube processing failed: {processing or upload_status}")
        if processing == "succeeded" or upload_status == "processed":
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
            return {
                "processing_status": str(processing or upload_status),
                "privacy": str(status.get("privacyStatus")),
            }
        if time.monotonic() >= deadline:
            raise TimeoutError("YouTube processing did not finish before the verification timeout")
        time.sleep(max(0, interval))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", help="Key from manage_youtube_channels.py list; omitted only for legacy environment credentials")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--cover", required=True, type=Path, help="Approved JPEG or PNG cover (max 2 MiB)")
    parser.add_argument("--title-file", required=True, type=Path)
    parser.add_argument("--description-file", required=True, type=Path)
    parser.add_argument(
        "--tags-file",
        required=True,
        type=Path,
        help="UTF-8 file containing one accurate YouTube tag per line",
    )
    parser.add_argument(
        "--audience",
        choices=["contacts", "everyone", "link"],
        required=True,
        help="contacts=private, everyone=public, link=unlisted",
    )
    parser.add_argument(
        "--playlist-title",
        default=os.environ.get("YOUTUBE_SHORTS_PLAYLIST", DEFAULT_SHORTS_PLAYLIST),
        help="Required exact owned playlist title",
    )
    parser.add_argument("--verification", required=True, type=Path)
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--processing-timeout", type=float, default=600)
    args = parser.parse_args()
    if not args.approved:
        raise SystemExit("Refusing publication without explicit --approved after the user command")
    try:
        approved = verify_approved_package(args.video, args.cover, args.verification)
        title = read_required_text(args.title_file, "title")
        description = read_required_text(args.description_file, "description")
        tags = read_tags(args.tags_file)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    privacy = privacy_for_audience(args.audience)

    try:
        if args.channel:
            selected_channel, credentials = credentials_for_channel(args.channel)
            expected_channel_id = selected_channel["channel_id"]
        else:
            credentials = legacy_environment_credentials()
            expected_channel_id = None
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
        playlist_id = select_playlist_id(list_owned_playlists(token), args.playlist_title)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    meta = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "19",
            "tags": tags,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    body = json.dumps(meta).encode()
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(len(approved["video_bytes"])),
    }
    start = req(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
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
    video_id = result["id"]

    approved_metadata = {
        "title": meta["snippet"]["title"],
        "description": meta["snippet"]["description"],
        "tags": tags,
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
            "playlist_title": args.playlist_title,
            "error_type": type(exc).__name__,
        }
        raise SystemExit(json.dumps(safe, ensure_ascii=False)) from None

    print(json.dumps({
        "ok": True,
        "platform": "youtube",
        "channel": {
            "key": args.channel or "legacy-env",
            "id": live_channel["id"],
            "title": live_channel["title"],
        },
        "id": video_id,
        "url": "https://youtu.be/" + video_id,
        "audience": args.audience,
        "privacy": privacy,
        "sha256": approved["video_sha256"],
        "readback_verified": True,
        "processing_status": readback["processing_status"],
        "tags": tags,
        "thumbnail": {
            "uploaded": True,
            "path": str(args.cover),
            "sha256": approved["cover_sha256"],
            "api_kind": thumb_response["kind"],
        },
        "playlist": {
            "id": playlist_id,
            "title": args.playlist_title,
            "item_id": playlist_item_id,
        },
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
