#!/usr/bin/env python3
"""Validate and normalize a domain-neutral story manifest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from story_manifest import validate_story


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        normalized = validate_story(json.loads(args.manifest.read_text(encoding="utf-8")))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema_version": 1, "status": "error", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2) from exc
    print(json.dumps({
        "schema_version": 1,
        "status": "ok",
        "story_id": normalized["id"],
        "render_ready": normalized["render_ready"],
        "pending_scene_ids": normalized["pending_scene_ids"],
        "output": str(args.output) if args.output else None,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
