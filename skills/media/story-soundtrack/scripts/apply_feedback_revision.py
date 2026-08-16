#!/usr/bin/env python3
"""Apply feedback and write a new versioned spec without overwriting."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from story_soundtrack_contract import (  # noqa: E402
    ContractError,
    load_and_validate_spec,
    write_feedback_revision,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--feedback", required=True, type=Path)
    ap.add_argument("--output-spec", required=True, type=Path)
    args = ap.parse_args()
    try:
        validated = load_and_validate_spec(args.root.resolve(), args.spec.resolve())
        feedback = json.loads(args.feedback.read_text(encoding="utf-8"))
        output_path = args.output_spec.resolve()
        new_spec = write_feedback_revision(validated, feedback, output_path, root=args.root.resolve())
    except ContractError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({
        "status": "ok",
        "revision": new_spec["revision"],
        "state": new_spec["state"],
        "output_spec": str(args.output_spec),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
