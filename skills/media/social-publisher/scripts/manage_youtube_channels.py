#!/usr/bin/env python3
"""Register, list, and remove selectable YouTube publication channels."""
from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path

from publish_youtube import api_json, req
from youtube_channel_registry import (
    load_registry,
    read_credentials_file,
    registry_path,
    remove_channel,
    upsert_channel,
)


def access_token(credentials: dict[str, str]) -> str:
    body = urllib.parse.urlencode({
        "client_id": credentials["YOUTUBE_CLIENT_ID"],
        "client_secret": credentials["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": credentials["YOUTUBE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    result = json.load(req(
        "https://oauth2.googleapis.com/token",
        body,
        {"Content-Type": "application/x-www-form-urlencoded"},
    ))
    token = result.get("access_token")
    if not token:
        raise ValueError("Google returned no access token")
    return str(token)


def authorized_channel(token: str) -> dict[str, str]:
    result = api_json("/channels", token, params={"part": "id,snippet", "mine": "true"})
    items = result.get("items") or []
    if len(items) != 1:
        raise ValueError(f"Expected exactly one authorized YouTube channel, got {len(items)}")
    item = items[0]
    channel_id = item.get("id")
    title = (item.get("snippet") or {}).get("title")
    if not channel_id or not title:
        raise ValueError("Authorized YouTube channel has no ID or title")
    return {"channel_id": str(channel_id), "title": str(title)}


def command_list() -> None:
    channels = []
    for item in load_registry()["channels"]:
        channels.append({key: item[key] for key in ("key", "label", "channel_id", "title")})
    print(json.dumps({"ok": True, "registry": str(registry_path()), "channels": channels}, ensure_ascii=False, indent=2))


def command_add(args) -> None:
    credentials = read_credentials_file(args.credentials_file)
    actual = authorized_channel(access_token(credentials))
    entry = upsert_channel(
        args.key,
        args.label or actual["title"],
        actual["channel_id"],
        actual["title"],
        args.credentials_file,
    )
    safe = {key: entry[key] for key in ("key", "label", "channel_id", "title")}
    print(json.dumps({"ok": True, "added": safe}, ensure_ascii=False, indent=2))


def command_remove(args) -> None:
    print(json.dumps({"ok": True, "removed": remove_channel(args.key), "key": args.key}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage selectable YouTube publication channels")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List registered publication channels")
    add = sub.add_parser("add", help="Register the channel authorized by a credentials env file")
    add.add_argument("key")
    add.add_argument("--label")
    add.add_argument("--credentials-file", required=True, type=Path)
    remove = sub.add_parser("remove", help="Remove a channel from the choices (credentials are not deleted)")
    remove.add_argument("key")
    args = parser.parse_args()
    try:
        if args.command == "list":
            command_list()
        elif args.command == "add":
            command_add(args)
        else:
            command_remove(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
