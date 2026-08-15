#!/usr/bin/env python3
"""Validate a media-voiceover JSON contract before rendering."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SOURCE_AUDIO_MODES = frozenset({"preserve", "remove", "lower", "boost"})
TARGET_KINDS = frozenset({"scene", "group"})
SCHEMA_VERSION = 1
RENDERER_VERSION = "1.0.0"


def safe_path(root: Path, rel: str, *, must_exist: bool = False) -> Path:
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError("path must be a non-empty string")
    if Path(rel).is_absolute():
        raise ValueError(f"absolute paths are not allowed: {rel}")
    if ".." in Path(rel).parts:
        raise ValueError(f"path traversal is not allowed: {rel}")
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes root: {rel}") from exc
    if must_exist and not path.is_file():
        raise ValueError(f"missing file: {rel}")
    return path


def _normalize_voiceover(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("voiceover must be an object")
    path = raw.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("voiceover.path must be a non-empty string")
    gain_db = float(raw.get("gain_db", 0.0))
    start_seconds = float(raw.get("start_seconds", 0.0))
    if start_seconds < 0:
        raise ValueError("voiceover.start_seconds must be >= 0")
    return {
        "path": path,
        "gain_db": gain_db,
        "start_seconds": start_seconds,
    }


def _normalize_target(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("target must be an object")
    kind = str(raw.get("kind", "scene"))
    if kind not in TARGET_KINDS:
        raise ValueError(f"target.kind must be one of {sorted(TARGET_KINDS)}; got {kind!r}")
    path = raw.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("target.path must be a non-empty string")
    return {"kind": kind, "path": path}


def validate_spec(raw: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("spec must be a JSON object")
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")

    target = _normalize_target(raw.get("target"))
    source_audio = str(raw.get("source_audio", "preserve"))
    if source_audio not in SOURCE_AUDIO_MODES:
        raise ValueError(
            f"source_audio must be one of {sorted(SOURCE_AUDIO_MODES)}; got {source_audio!r}"
        )

    gain_db = float(raw.get("gain_db", 0.0))
    if source_audio in {"lower", "boost"} and "gain_db" not in raw:
        raise ValueError(f"gain_db is required when source_audio is {source_audio}")
    if source_audio == "lower" and gain_db > 0:
        raise ValueError("gain_db must be <= 0 when source_audio is lower")
    if source_audio == "boost" and gain_db <= 0:
        raise ValueError("gain_db must be > 0 when source_audio is boost")

    voiceover = _normalize_voiceover(raw.get("voiceover"))

    output = raw.get("output")
    if not isinstance(output, str) or not output.strip():
        raise ValueError("output must be a non-empty string")

    overwrite = bool(raw.get("overwrite", False))

    report = raw.get("report")
    if report is not None and (not isinstance(report, str) or not report.strip()):
        raise ValueError("report must be a non-empty string when provided")

    normalized: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "target": target,
        "source_audio": source_audio,
        "gain_db": gain_db,
        "voiceover": voiceover,
        "output": output,
        "overwrite": overwrite,
    }
    if report:
        normalized["report"] = report

    if root is not None:
        root = root.resolve()
        output_path = safe_path(root, output)
        report_rel = report or f"{output.rsplit('.', 1)[0]}-report.json"
        report_path = safe_path(root, report_rel)
        target_path = safe_path(root, target["path"])
        voiceover_path = safe_path(root, voiceover["path"])
        input_paths = {target_path, voiceover_path}
        if output_path in input_paths:
            raise ValueError("output must not alias an input path")
        if report_path == output_path:
            raise ValueError("report must not alias output path")
        if report_path in input_paths:
            raise ValueError("report must not alias an input path")
        if output_path.exists() and not overwrite:
            raise ValueError(f"output exists and overwrite=false: {output}")
        safe_path(root, target["path"], must_exist=True)
        safe_path(root, voiceover["path"], must_exist=True)

    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a media-voiceover spec.")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        raw = json.loads(args.spec.read_text(encoding="utf-8"))
        normalized = validate_spec(raw, root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"status": "ok", "normalized_spec": normalized}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
