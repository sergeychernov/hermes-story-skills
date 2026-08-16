#!/usr/bin/env python3
"""Instagram publication-account registry and credential isolation helpers."""
from __future__ import annotations

import json
import fcntl
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
REQUIRED_CREDENTIAL_KEYS = ("INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID")
OPTIONAL_CREDENTIAL_KEYS = ("INSTAGRAM_API_VERSION",)
DEFAULT_API_VERSION = "v24.0"


def instagram_home() -> Path:
    configured = os.environ.get("INSTAGRAM_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser().resolve()
    return hermes_home / "instagram"


def registry_path() -> Path:
    return instagram_home() / "accounts.json"


def load_registry(path: Path | None = None) -> dict:
    path = path or registry_path()
    if not path.is_file():
        return {"version": 1, "accounts": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid Instagram account registry {path}: {exc}") from exc
    if data.get("version") != 1 or not isinstance(data.get("accounts"), list):
        raise ValueError(f"Unsupported Instagram account registry format: {path}")
    seen_keys: set[str] = set()
    seen_user_ids: set[str] = set()
    for item in data["accounts"]:
        key = item.get("key") if isinstance(item, dict) else None
        user_id = item.get("user_id") if isinstance(item, dict) else None
        if not isinstance(key, str) or not KEY_RE.fullmatch(key) or key in seen_keys:
            raise ValueError(f"Invalid or duplicate Instagram account key: {key!r}")
        if not user_id or not item.get("credentials_file") or not item.get("username"):
            raise ValueError(f"Incomplete Instagram account entry: {key}")
        user_id_str = str(user_id)
        if user_id_str in seen_user_ids:
            raise ValueError(f"Duplicate Instagram user ID in registry: {user_id_str}")
        seen_keys.add(key)
        seen_user_ids.add(user_id_str)
    return data


def save_registry(data: dict, path: Path | None = None) -> Path:
    path = path or registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    fd, tmp = tempfile.mkstemp(prefix=".accounts.", dir=path.parent, text=True)
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


@contextmanager
def registry_transaction(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    lock_path = path.with_name(f".{path.name}.lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock_path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def upsert_account(
    key: str,
    label: str,
    user_id: str,
    username: str,
    credentials_file: Path,
    path: Path | None = None,
) -> dict:
    key = key.strip().lower()
    if not KEY_RE.fullmatch(key):
        raise ValueError("Account key must match [a-z0-9][a-z0-9_-]{0,63}")
    label = label.strip()
    username = username.strip().lstrip("@")
    if not label or not user_id or not username:
        raise ValueError("Account label, user ID, and username are required")
    user_id_str = str(user_id)
    entry = {
        "key": key,
        "label": label,
        "user_id": user_id_str,
        "username": username,
        "credentials_file": str(credentials_file.expanduser().resolve()),
    }
    registry = path or registry_path()
    with registry_transaction(registry):
        data = load_registry(registry)
        for item in data["accounts"]:
            if item["user_id"] == user_id_str and item["key"] != key:
                raise ValueError(f"Duplicate Instagram user ID in registry: {user_id_str}")
        data["accounts"] = sorted(
            [item for item in data["accounts"] if item["key"] != key] + [entry],
            key=lambda item: item["key"],
        )
        save_registry(data, registry)
    return entry


def remove_account(key: str, path: Path | None = None) -> bool:
    registry = path or registry_path()
    with registry_transaction(registry):
        data = load_registry(registry)
        remaining = [item for item in data["accounts"] if item["key"] != key]
        if len(remaining) == len(data["accounts"]):
            return False
        data["accounts"] = remaining
        save_registry(data, registry)
        return True


def get_account(key: str, path: Path | None = None) -> dict:
    item = next((item for item in load_registry(path)["accounts"] if item["key"] == key), None)
    if item is None:
        raise ValueError(f"Unknown Instagram account {key!r}; list or add accounts first")
    return item


def read_credentials_file(path: Path) -> dict[str, str]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Instagram credentials file is missing: {path}")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError(f"Instagram credentials file must not be accessible by group/others: {path}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    missing = [key for key in REQUIRED_CREDENTIAL_KEYS if not values.get(key)]
    if missing:
        raise ValueError("Missing Instagram credentials: " + ", ".join(missing))
    result = {key: values[key] for key in REQUIRED_CREDENTIAL_KEYS}
    for key in OPTIONAL_CREDENTIAL_KEYS:
        if values.get(key):
            result[key] = values[key]
    return result


def credentials_for_account(key: str, path: Path | None = None) -> tuple[dict, dict[str, str]]:
    account = get_account(key, path)
    return account, read_credentials_file(Path(account["credentials_file"]))
