#!/usr/bin/env python3
"""Upload a verified Short and add it to the configured YouTube playlist."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_SHORTS_PLAYLIST = "Лягушка-путешественница"
API = "https://www.googleapis.com/youtube/v3"
AUDIENCE_TO_PRIVACY = {
    "contacts": "private",
    "everyone": "public",
    "link": "unlisted",
}


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


def verify_approved_package(video: Path, verification: Path) -> str:
    if not video.is_file():
        raise ValueError(f"video is missing: {video}")
    try:
        report = json.loads(verification.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid verification report: {exc}") from exc
    if report.get("ok") is not True:
        raise ValueError("verification report is not green")
    expected = (report.get("video") or {}).get("sha256")
    actual = file_sha256(video)
    if not expected or expected != actual:
        raise ValueError("video hash does not match verification report")
    return actual


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
            if actual != expected:
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
    parser.add_argument("--video", required=True, type=Path)
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
        approved_sha256 = verify_approved_package(args.video, args.verification)
        title = read_required_text(args.title_file, "title")
        description = read_required_text(args.description_file, "description")
        tags = read_tags(args.tags_file)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    privacy = privacy_for_audience(args.audience)

    names = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise SystemExit("missing environment: " + ", ".join(missing))

    token_data = urllib.parse.urlencode({
        "client_id": os.environ[names[0]],
        "client_secret": os.environ[names[1]],
        "refresh_token": os.environ[names[2]],
        "grant_type": "refresh_token",
    }).encode()
    token = json.load(req(
        "https://oauth2.googleapis.com/token",
        token_data,
        {"Content-Type": "application/x-www-form-urlencoded"},
    ))["access_token"]

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
        "X-Upload-Content-Length": str(args.video.stat().st_size),
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
        args.video.read_bytes(),
        {
            "Authorization": "Bearer " + token,
            "Content-Type": "video/mp4",
            "Content-Length": str(args.video.stat().st_size),
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
            "error": str(exc),
        }
        raise SystemExit(json.dumps(safe, ensure_ascii=False)) from None

    try:
        playlist_item_id = add_to_playlist(token, playlist_id, video_id)
    except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as exc:
        safe = {
            "ok": False,
            "platform": "youtube",
            "video_uploaded": True,
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
        "id": video_id,
        "url": "https://youtu.be/" + video_id,
        "audience": args.audience,
        "privacy": privacy,
        "sha256": approved_sha256,
        "readback_verified": True,
        "processing_status": readback["processing_status"],
        "tags": tags,
        "playlist": {
            "id": playlist_id,
            "title": args.playlist_title,
            "item_id": playlist_item_id,
        },
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
