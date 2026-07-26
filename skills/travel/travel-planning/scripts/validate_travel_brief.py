#!/usr/bin/env python3
"""Validate and normalize a travel brief JSON file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from travel_brief import validate_travel_brief


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a versioned travel brief")
    parser.add_argument("brief", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        normalized = validate_travel_brief(json.loads(args.brief.read_text(encoding="utf-8")))
        payload = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
