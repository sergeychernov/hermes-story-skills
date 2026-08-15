#!/usr/bin/env python3
"""Revision-scoped serialization for soundtrack render, mix, and approval."""
from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path


def revision_lock_path(validated: dict) -> Path:
    approval_path = validated["resolved_paths"]["approval_json"]
    revision = int(validated["revision"])
    return approval_path.with_name(f".story-soundtrack-r{revision}.lock")


@contextmanager
def revision_lock(validated: dict):
    path = revision_lock_path(validated)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
