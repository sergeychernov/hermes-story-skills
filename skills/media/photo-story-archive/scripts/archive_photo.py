#!/usr/bin/env python3
"""Copy an image without transcoding and emit verification metadata as JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dimensions(path: Path) -> tuple[int | None, int | None]:
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:3] == b"GIF" and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    if data.startswith(b"\xff\xd8"):
        i = 2
        sof = set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0))
        while i + 8 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            i += 2
            if marker in (0xD8, 0xD9):
                continue
            if i + 2 > len(data):
                break
            length = int.from_bytes(data[i : i + 2], "big")
            if marker in sof and i + 7 <= len(data):
                height = int.from_bytes(data[i + 3 : i + 5], "big")
                width = int.from_bytes(data[i + 5 : i + 7], "big")
                return width, height
            if length < 2:
                break
            i += length
    return None, None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"source is not a file: {source}")
    if destination.exists():
        raise SystemExit(f"refusing to overwrite: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    source_hash = sha256(source)
    destination_hash = sha256(destination)
    if source_hash != destination_hash:
        destination.unlink(missing_ok=True)
        raise SystemExit("checksum mismatch; destination removed")

    width, height = dimensions(destination)
    print(json.dumps({
        "source": str(source),
        "destination": str(destination),
        "bytes": destination.stat().st_size,
        "width": width,
        "height": height,
        "orientation": "landscape" if width and height and width > height else "portrait" if width and height and height > width else "square" if width and height else "unknown",
        "sha256": destination_hash,
        "verified": True,
        "time_note": "filesystem times are not camera capture time; inspect EXIF separately if needed"
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
