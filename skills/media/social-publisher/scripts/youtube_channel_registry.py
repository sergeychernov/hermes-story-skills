#!/usr/bin/env python3
"""YouTube publication-channel registry and credential isolation helpers."""
from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from pathlib import Path

KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
CREDENTIAL_KEYS = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")


def youtube_home() -> Path:
    configured = os.environ.get("YOUTUBE_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home())).expanduser().resolve()
    return hermes_home / ".hermes" / "youtube"


def registry_path() -> Path:
    return youtube_home() / "channels.json"


def load_registry(path: Path | None = None) -> dict:
    path = path or registry_path()
    if not path.is_file():
        return {"version": 1, "channels": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid YouTube channel registry {path}: {exc}") from exc
    if data.get("version") != 1 or not isinstance(data.get("channels"), list):
        raise ValueError(f"Unsupported YouTube channel registry format: {path}")
    seen: set[str] = set()
    for item in data["channels"]:
        key = item.get("key") if isinstance(item, dict) else None
        if not isinstance(key, str) or not KEY_RE.fullmatch(key) or key in seen:
            raise ValueError(f"Invalid or duplicate YouTube channel key: {key!r}")
        if not item.get("channel_id") or not item.get("credentials_file"):
            raise ValueError(f"Incomplete YouTube channel entry: {key}")
        seen.add(key)
    return data


def save_registry(data: dict, path: Path | None = None) -> Path:
    path = path or registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    fd, tmp = tempfile.mkstemp(prefix=".channels.", dir=path.parent, text=True)
    try:
        os.write(fd, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode())
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


def upsert_channel(key: str, label: str, channel_id: str, title: str,
                   credentials_file: Path, path: Path | None = None) -> dict:
    key = key.strip().lower()
    if not KEY_RE.fullmatch(key):
        raise ValueError("Channel key must match [a-z0-9][a-z0-9_-]{0,63}")
    label = label.strip()
    if not label or not channel_id:
        raise ValueError("Channel label and ID are required")
    entry = {
        "key": key,
        "label": label,
        "channel_id": str(channel_id),
        "title": str(title),
        "credentials_file": str(credentials_file.expanduser().resolve()),
    }
    data = load_registry(path)
    data["channels"] = sorted(
        [item for item in data["channels"] if item["key"] != key and item["channel_id"] != str(channel_id)] + [entry],
        key=lambda item: item["key"],
    )
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


def get_channel(key: str, path: Path | None = None) -> dict:
    item = next((item for item in load_registry(path)["channels"] if item["key"] == key), None)
    if item is None:
        raise ValueError(f"Unknown YouTube channel {key!r}; list or add channels first")
    return item


def read_credentials_file(path: Path) -> dict[str, str]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"YouTube credentials file is missing: {path}")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError(f"YouTube credentials file must not be accessible by group/others: {path}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    missing = [key for key in CREDENTIAL_KEYS if not values.get(key)]
    if missing:
        raise ValueError("Missing YouTube credentials: " + ", ".join(missing))
    return {key: values[key] for key in CREDENTIAL_KEYS}


def credentials_for_channel(key: str, path: Path | None = None) -> tuple[dict, dict[str, str]]:
    channel = get_channel(key, path)
    return channel, read_credentials_file(Path(channel["credentials_file"]))
