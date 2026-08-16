#!/usr/bin/env python3
"""List owned YouTube playlists for one registered channel without writes."""
from __future__ import annotations

import argparse
import json
import urllib.parse

from publish_youtube import list_owned_playlists, req, verify_authorized_channel
from youtube_channel_registry import credentials_for_channel


def fetch_owned_playlists(channel_key: str) -> dict[str, object]:
    channel, credentials = credentials_for_channel(channel_key)
    token_data = urllib.parse.urlencode({
        "client_id": credentials["YOUTUBE_CLIENT_ID"],
        "client_secret": credentials["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": credentials["YOUTUBE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    token_response = json.load(req(
        "https://oauth2.googleapis.com/token",
        token_data,
        {"Content-Type": "application/x-www-form-urlencoded"},
    ))
    token = token_response.get("access_token")
    if not isinstance(token, str) or not token:
        raise ValueError("OAuth refresh response contains no access token")
    live = verify_authorized_channel(token, channel["channel_id"])
    playlists = []
    for item in list_owned_playlists(token):
        playlist_id = str(item.get("id") or "")
        title = str((item.get("snippet") or {}).get("title") or "")
        if not playlist_id or not title:
            raise ValueError("YouTube returned a playlist without ID or title")
        playlists.append({"id": playlist_id, "title": title})
    playlists.sort(key=lambda item: (item["title"].casefold(), item["id"]))
    return {
        "ok": True,
        "read_only": True,
        "channel": {
            "key": channel_key,
            "id": live["id"],
            "title": live["title"],
        },
        "playlists": playlists,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", required=True, help="Registered YouTube channel key")
    args = parser.parse_args()
    try:
        result = fetch_owned_playlists(args.channel)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
