#!/usr/bin/env python3
"""Register, list, and remove selectable Instagram publication accounts."""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

from instagram_account_registry import (
    DEFAULT_API_VERSION,
    load_registry,
    read_credentials_file,
    remove_account,
    upsert_account,
)
from publish_instagram import fetch_instagram_identity, validate_api_version


def command_list() -> None:
    accounts = []
    for item in load_registry()["accounts"]:
        accounts.append({key: item[key] for key in ("key", "label", "user_id", "username")})
    print(json.dumps({"ok": True, "accounts": accounts}, ensure_ascii=False, indent=2))


def command_add(args) -> None:
    credentials = read_credentials_file(args.credentials_file)
    version = credentials.get("INSTAGRAM_API_VERSION", DEFAULT_API_VERSION)
    validate_api_version(version)
    identity = fetch_instagram_identity(
        credentials["INSTAGRAM_ACCESS_TOKEN"],
        version,
    )
    expected_id = credentials["INSTAGRAM_USER_ID"]
    if str(identity["id"]) != str(expected_id):
        raise ValueError("Instagram identity ID does not match INSTAGRAM_USER_ID in credentials file")
    entry = upsert_account(
        args.key,
        args.label or identity["username"],
        identity["id"],
        identity["username"],
        args.credentials_file,
    )
    safe = {key: entry[key] for key in ("key", "label", "user_id", "username")}
    print(json.dumps({"ok": True, "added": safe}, ensure_ascii=False, indent=2))


def command_remove(args) -> None:
    print(json.dumps({"ok": True, "removed": remove_account(args.key), "key": args.key}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage selectable Instagram publication accounts")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List registered publication accounts")
    add = sub.add_parser("add", help="Register the account authorized by a credentials env file")
    add.add_argument("key")
    add.add_argument("--label")
    add.add_argument("--credentials-file", required=True, type=Path)
    remove = sub.add_parser("remove", help="Remove an account from the choices (credentials are not deleted)")
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
