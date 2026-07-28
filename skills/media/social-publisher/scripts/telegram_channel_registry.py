#!/usr/bin/env python3
"""Persistent, non-secret registry of Telegram Story publication channels."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

REGISTRY_VERSION = 1
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def default_registry_path() -> Path:
    base = Path(os.environ.get("TELEGRAM_USER_HOME", "~/.hermes/telegram-user"))
    return base.expanduser().resolve() / "channels.json"


def empty_registry() -> dict:
    return {"version": REGISTRY_VERSION, "channels": []}


def load_registry(path: Path | None = None) -> dict:
    path = path or default_registry_path()
    if not path.is_file():
        return empty_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid Telegram channel registry {path}: {exc}") from exc
    if data.get("version") != REGISTRY_VERSION or not isinstance(data.get("channels"), list):
        raise ValueError(f"Unsupported Telegram channel registry format: {path}")
    seen: set[str] = set()
    for item in data["channels"]:
        if not isinstance(item, dict):
            raise ValueError(f"Invalid channel entry in {path}")
        key = item.get("key")
        channel_id = item.get("channel_id")
        if not isinstance(key, str) or not KEY_RE.fullmatch(key) or key == "self":
            raise ValueError(f"Invalid channel key in {path}: {key!r}")
        if key in seen:
            raise ValueError(f"Duplicate channel key in {path}: {key}")
        if not isinstance(channel_id, int) or channel_id <= 0:
            raise ValueError(f"Invalid channel_id for {key!r} in {path}")
        seen.add(key)
    return data


def save_registry(data: dict, path: Path | None = None) -> Path:
    path = path or default_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    fd, tmp = tempfile.mkstemp(prefix=".channels.", dir=path.parent, text=True)
    try:
        payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        os.write(fd, payload.encode("utf-8"))
        os.close(fd)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        path.chmod(0o600)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        Path(tmp).unlink(missing_ok=True)
        raise
    return path


def upsert_channel(
    key: str,
    channel_id: int,
    label: str,
    username: str | None = None,
    path: Path | None = None,
) -> dict:
    key = key.strip().lower()
    if key == "self" or not KEY_RE.fullmatch(key):
        raise ValueError("Channel key must match [a-z0-9][a-z0-9_-]{0,63} and cannot be 'self'")
    label = label.strip()
    if not label:
        raise ValueError("Channel label cannot be empty")
    if channel_id <= 0:
        raise ValueError("channel_id must be positive")
    username = (username or "").strip().lstrip("@") or None
    data = load_registry(path)
    entry = {"key": key, "label": label, "channel_id": int(channel_id), "username": username}
    channels = [item for item in data["channels"] if item["key"] != key and item["channel_id"] != channel_id]
    channels.append(entry)
    data["channels"] = sorted(channels, key=lambda item: item["key"])
    save_registry(data, path)
    return entry


def remove_channel(key: str, path: Path | None = None) -> bool:
    data = load_registry(path)
    remaining = [item for item in data["channels"] if item["key"] != key]
    if len(remaining) == len(data["channels"]):
        return False
    data["channels"] = remaining
    save_registry(data, path)
    return True


def registered_channel(key: str, path: Path | None = None) -> dict | None:
    if key == "self":
        return {"key": "self", "label": "Личный аккаунт", "channel_id": None, "username": None}
    return next((item for item in load_registry(path)["channels"] if item["key"] == key), None)
