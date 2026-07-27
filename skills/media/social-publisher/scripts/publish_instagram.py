#!/usr/bin/env python3
"""Publish a verified Reel whose exact MP4 is reachable at an approved HTTPS URL."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path


def post(url: str, fields: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(url, data=data, method="POST")
    return json.load(urllib.request.urlopen(request, timeout=60))


def get_json(url: str, fields: dict[str, str]) -> dict:
    return json.load(urllib.request.urlopen(url + "?" + urllib.parse.urlencode(fields), timeout=60))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_url(url: str) -> str:
    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": "Hermes-Social-Publisher/1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        for block in iter(lambda: response.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_local_package(video: Path, verification: Path) -> str:
    if not video.is_file():
        raise ValueError(f"video is missing: {video}")
    try:
        report = json.loads(verification.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid verification report: {exc}") from exc
    if report.get("ok") is not True:
        raise ValueError("verification report is not green")
    expected = (report.get("video") or {}).get("sha256")
    actual = sha256_file(video)
    if not expected or expected != actual:
        raise ValueError("video hash does not match verification report")
    return actual


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--video-url", required=True)
    parser.add_argument("--verification", required=True, type=Path)
    parser.add_argument("--caption-file", required=True, type=Path)
    parser.add_argument("--share-to-feed", action="store_true")
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()

    if not args.approved:
        raise SystemExit("Refusing publication without explicit --approved after the user command")
    if not args.video_url.startswith("https://"):
        raise SystemExit("video-url must be public HTTPS")
    try:
        approved_sha256 = verify_local_package(args.video, args.verification)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if sha256_url(args.video_url) != approved_sha256:
        raise SystemExit("remote HTTPS media hash does not match the verified local video")

    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    user = os.environ.get("INSTAGRAM_USER_ID")
    version = os.environ.get("INSTAGRAM_API_VERSION", "v24.0")
    if not token or not user:
        raise SystemExit("missing INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_USER_ID")

    caption = args.caption_file.read_text(encoding="utf-8").strip()
    base = f"https://graph.instagram.com/{version}"
    container = post(f"{base}/{user}/media", {
        "media_type": "REELS",
        "video_url": args.video_url,
        "caption": caption,
        "share_to_feed": str(args.share_to_feed).lower(),
        "access_token": token,
    })["id"]
    for _ in range(60):
        status = get_json(f"{base}/{container}", {
            "fields": "status_code,status",
            "access_token": token,
        })
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") in {"ERROR", "EXPIRED"}:
            safe_status = {key: value for key, value in status.items() if key != "access_token"}
            raise SystemExit("container failed: " + json.dumps(safe_status))
        time.sleep(5)
    else:
        raise SystemExit("container not ready after 5 minutes")

    published = post(f"{base}/{user}/media_publish", {
        "creation_id": container,
        "access_token": token,
    })
    print(json.dumps({
        "ok": True,
        "platform": "instagram",
        "id": published["id"],
        "container_id": container,
        "sha256": approved_sha256,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
