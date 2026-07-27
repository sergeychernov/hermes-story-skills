#!/usr/bin/env python3
"""Render one still-image animation from a versioned JSON specification."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from still_image_animation import render


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    args = parser.parse_args()
    try:
        raw = json.loads(args.spec.read_text(encoding="utf-8"))
        report = render(args.root, raw)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema_version": 1, "status": "error", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
