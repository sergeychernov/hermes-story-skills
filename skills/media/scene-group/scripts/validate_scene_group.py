#!/usr/bin/env python3
"""Validate a scene-group JSON contract before rendering."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

MEMBER_TYPES = frozenset({"scene", "group"})
SCHEMA_VERSION = 1
RENDERER_VERSION = "1.0.0"
FORBIDDEN_AUDIO_FIELDS = frozenset(
    {
        "audio_mode",
        "audio_default",
        "source_audio",
        "voiceover",
        "gain_db",
        "ducking",
        "audio_policy",
    }
)


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


def _reject_audio_policy_fields(raw: dict[str, Any]) -> None:
    for key in raw:
        if key in FORBIDDEN_AUDIO_FIELDS:
            raise ValueError(f"audio-policy field is not allowed in scene-group spec: {key}")


def _normalize_member(member: Any, index: int) -> dict[str, Any]:
    if not isinstance(member, dict):
        raise ValueError(f"members[{index}] must be an object")
    for key in member:
        if key in FORBIDDEN_AUDIO_FIELDS:
            raise ValueError(f"audio-policy field is not allowed on members[{index}]: {key}")
    ref = member.get("ref")
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError(f"members[{index}].ref must be a non-empty string")
    member_type = str(member.get("type", "scene"))
    if member_type not in MEMBER_TYPES:
        raise ValueError(
            f"members[{index}].type must be one of {sorted(MEMBER_TYPES)}; got {member_type!r}"
        )
    path = member.get("path")
    if member_type == "scene":
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"members[{index}].path must be a non-empty string for type scene")
    elif member_type == "group":
        if path is None or (isinstance(path, str) and not path.strip()):
            normalized_path: str | None = None
        elif not isinstance(path, str):
            raise ValueError(f"members[{index}].path must be a string when provided for type group")
        else:
            normalized_path = path
        return {"ref": ref, "type": member_type, "path": normalized_path}
    return {"ref": ref, "path": path, "type": member_type}


def validate_spec(raw: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("spec must be a JSON object")
    _reject_audio_policy_fields(raw)
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")

    group_id = raw.get("id")
    if not isinstance(group_id, str) or not group_id.strip():
        raise ValueError("id must be a non-empty string")

    title = raw.get("title")
    if title is not None and not isinstance(title, str):
        raise ValueError("title must be a string when provided")

    members_raw = raw.get("members")
    if not isinstance(members_raw, list):
        raise ValueError("members must be an array")
    if len(members_raw) < 2:
        raise ValueError("members must contain at least 2 entries")

    output = raw.get("output")
    if not isinstance(output, str) or not output.strip():
        raise ValueError("output must be a non-empty string")

    target_raw = raw.get("target", {})
    if not isinstance(target_raw, dict):
        raise ValueError("target must be an object")
    width = int(target_raw.get("width", 1080))
    height = int(target_raw.get("height", 1920))
    fps = float(target_raw.get("fps", 30))
    if width <= 0 or height <= 0:
        raise ValueError("target.width and target.height must be positive")
    if fps <= 0:
        raise ValueError("target.fps must be positive")

    overwrite = bool(raw.get("overwrite", False))
    members = [_normalize_member(member, i) for i, member in enumerate(members_raw)]

    report = raw.get("report")
    if report is not None and (not isinstance(report, str) or not report.strip()):
        raise ValueError("report must be a non-empty string when provided")

    normalized: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": group_id,
        "members": members,
        "output": output,
        "target": {"width": width, "height": height, "fps": fps},
        "overwrite": overwrite,
    }
    if title is not None:
        normalized["title"] = title
    if report:
        normalized["report"] = report

    if root is not None:
        root = root.resolve()
        output_path = safe_path(root, output)
        report_rel = report or f"{output.rsplit('.', 1)[0]}-report.json"
        report_path = safe_path(root, report_rel)
        member_paths: list[Path] = []
        for member in members:
            if member["type"] == "scene":
                member_paths.append(safe_path(root, member["path"]))
            elif member["path"]:
                member_paths.append(safe_path(root, member["path"]))

        if output_path in member_paths:
            raise ValueError("output must not alias a member path")
        if report_path == output_path:
            raise ValueError("report must not alias output path")
        if report_path in member_paths:
            raise ValueError("report must not alias a member path")
        if output_path.exists() and not overwrite:
            raise ValueError(f"output exists and overwrite=false: {output}")
        for member in members:
            if member["type"] == "scene":
                safe_path(root, member["path"], must_exist=True)
            elif member["path"]:
                safe_path(root, member["path"], must_exist=True)

    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a scene-group spec.")
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
