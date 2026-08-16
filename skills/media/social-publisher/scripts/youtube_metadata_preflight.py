#!/usr/bin/env python3
"""Schema-driven YouTube publication preflight sourced from story.json."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from jsonschema_runtime import (
    active_required_fields,
    apply_defaults,
    assert_supported_schema,
    validate_or_raise,
)

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = SKILL_DIR / "templates" / "youtube-publication.schema.json"
DEFAULT_MANIFEST_SCHEMA = (
    SKILL_DIR / "templates" / "youtube-publication-preflight.schema.json"
)


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label} JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON must contain an object: {path}")
    return payload


def load_schema_snapshot(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        schema = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read schema JSON {path}: {exc}") from exc
    if not isinstance(schema, dict):
        raise ValueError(f"schema JSON must contain an object: {path}")
    assert_supported_schema(schema)
    return schema, raw


def load_schema(path: Path) -> dict[str, Any]:
    return load_schema_snapshot(path)[0]


def _json_pointer(document: object, pointer: str) -> object:
    if not pointer.startswith("/"):
        raise ValueError("schema x-story-pointer must be an absolute JSON pointer")
    current = document
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            return {}
        current = current[token]
    return current


_MISSING = object()


def _pointer_value(document: object, pointer: str) -> object:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError(f"resolver pointer must be an absolute JSON pointer: {pointer!r}")
    current = document
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            return _MISSING
        current = current[token]
    return current


def _relative_existing_file(root: Path, value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = (root / value).resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return None
    return relative.as_posix() if candidate.is_file() else None


def _resolver_candidates(
    root: Path,
    field: str,
    rule: dict[str, Any],
) -> list[dict[str, Any]]:
    kind = rule.get("kind")
    raw: list[dict[str, Any]] = []
    if kind == "exact-file":
        names = rule.get("candidates")
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise ValueError(f"invalid exact-file resolver for {field}")
        for name in names:
            value = _relative_existing_file(root, name)
            if value is not None:
                raw.append({"value": value, "provenance": [value]})
    elif kind == "json-report-value":
        patterns = rule.get("globs", rule.get("glob"))
        value_pointer = rule.get("value_pointer")
        hash_pointer = rule.get("hash_pointer")
        predicates = rule.get("predicates", [])
        if isinstance(patterns, str):
            patterns = [patterns]
        if (
            not isinstance(patterns, list)
            or not patterns
            or not all(isinstance(pattern, str) for pattern in patterns)
            or not isinstance(value_pointer, str)
            or (hash_pointer is not None and not isinstance(hash_pointer, str))
        ):
            raise ValueError(f"invalid json-report-value resolver for {field}")
        if not isinstance(predicates, list):
            raise ValueError(f"resolver predicates must be an array for {field}")
        report_paths = sorted({
            path for pattern in patterns for path in root.glob(pattern)
        })
        for report_path in report_paths:
            if not report_path.is_file():
                continue
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(report, dict):
                continue
            matched = True
            for predicate in predicates:
                if not isinstance(predicate, dict) or "pointer" not in predicate:
                    raise ValueError(f"invalid resolver predicate for {field}")
                actual = _pointer_value(report, predicate["pointer"])
                if "equals" in predicate:
                    predicate_matches = actual == predicate["equals"]
                elif (
                    isinstance(predicate.get("enum"), list)
                    and predicate["enum"]
                ):
                    predicate_matches = actual in predicate["enum"]
                else:
                    raise ValueError(f"invalid resolver predicate for {field}")
                if not predicate_matches:
                    matched = False
                    break
            if not matched:
                continue
            value = _relative_existing_file(root, _pointer_value(report, value_pointer))
            if value is None:
                continue
            if hash_pointer is not None:
                declared_hash = _pointer_value(report, hash_pointer)
                if (
                    not isinstance(declared_hash, str)
                    or declared_hash != _sha256_file(root / value)
                ):
                    continue
            report_relative = report_path.resolve().relative_to(root).as_posix()
            raw.append({"value": value, "provenance": [report_relative]})
    elif kind == "provenance-report":
        raise ValueError("provenance-report resolver requires source context")
    else:
        raise ValueError(f"unsupported x-auto-resolve kind for {field}: {kind!r}")
    grouped: dict[str, list[str]] = {}
    for item in raw:
        grouped.setdefault(item["value"], []).extend(item["provenance"])
    return [
        {"value": value, "provenance": sorted(set(provenance))}
        for value, provenance in sorted(grouped.items())
    ]


def auto_resolve_config(
    story_path: Path,
    schema: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    root = story_path.resolve().parent
    normalized = dict(config)
    properties = schema.get("properties", {})
    resolved: list[dict[str, Any]] = []
    validated: list[dict[str, Any]] = []
    ambiguities: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    candidate_cache: dict[str, list[dict[str, Any]]] = {}
    for field, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            continue
        rule = field_schema.get("x-auto-resolve")
        if not isinstance(rule, dict):
            continue
        configured = field in normalized
        if rule.get("kind") == "provenance-report":
            source_field = rule.get("source_field")
            if not isinstance(source_field, str):
                raise ValueError(f"invalid provenance-report resolver for {field}")
            source_value = normalized.get(source_field)
            source_candidates = candidate_cache.get(source_field, [])
            matching = [item for item in source_candidates if item["value"] == source_value]
            candidates = []
            if len(matching) == 1:
                candidates = [
                    {"value": report, "provenance": [report]}
                    for report in matching[0]["provenance"]
                    if _relative_existing_file(root, report) is not None
                ]
        else:
            candidates = _resolver_candidates(root, field, rule)
            candidate_cache[field] = candidates
        if configured:
            matching = [item for item in candidates if item["value"] == normalized[field]]
            if len(matching) == 1:
                validated.append({"field": field, **matching[0]})
            else:
                blockers.append({
                    "field": field,
                    "reason": "configured value is not uniquely eligible under x-auto-resolve",
                })
        elif len(candidates) == 1:
            selected = candidates[0]
            normalized[field] = selected["value"]
            resolved.append({"field": field, **selected})
        elif len(candidates) > 1:
            ambiguities.append({"field": field, "candidates": candidates})
        else:
            blockers.append({
                "field": field,
                "reason": "no unique eligible candidate matched x-auto-resolve",
            })
    return normalized, {
        "resolved": resolved,
        "validated": validated,
        "ambiguities": ambiguities,
        "blockers": blockers,
    }


def extract_youtube_config(story: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    pointer = schema.get("x-story-pointer")
    if not isinstance(pointer, str):
        raise ValueError("publication schema must declare x-story-pointer")
    target = _json_pointer(story, pointer)
    if not isinstance(target, dict):
        raise ValueError(f"story value at {pointer} must be an object")
    return target


def _property_schema(schema: dict[str, Any], field: str) -> dict[str, Any]:
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not isinstance(properties.get(field), dict):
        raise ValueError(f"required field is not declared in schema properties: {field}")
    return properties[field]


def _question(field: str, property_schema: dict[str, Any], locale: str) -> dict[str, Any]:
    spec = property_schema.get("x-question")
    if not isinstance(spec, dict):
        raise ValueError(f"user-confirmed schema field lacks x-question: {field}")
    prompt = spec.get(locale) or spec.get("en")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError(f"schema question has no prompt for {field}")
    result: dict[str, Any] = {
        "field": field,
        "prompt": prompt.strip(),
        "kind": spec.get("kind", "text"),
    }
    choices = property_schema.get("enum")
    if isinstance(choices, list):
        result["choices"] = choices
    elif property_schema.get("type") == "boolean":
        result["choices"] = [True, False]
    return result


def _assess_loaded(
    story_path: Path,
    story: dict[str, Any],
    schema: dict[str, Any],
    *,
    locale: str = "ru",
    schema_label: str = "<loaded-schema>",
) -> dict[str, Any]:
    raw = extract_youtube_config(story, schema)
    auto_normalized, auto_resolution = auto_resolve_config(story_path, schema, raw)
    normalized = apply_defaults(auto_normalized, schema)
    if not isinstance(normalized, dict):
        raise ValueError("normalized YouTube publication config must be an object")
    validate_or_raise(normalized, schema, enforce_required=False)
    required = active_required_fields(schema, normalized, root=schema)
    missing = [name for name in required if name not in normalized]
    confirmation_required: list[str] = []
    questions: list[dict[str, Any]] = []
    for field in missing:
        field_schema = _property_schema(schema, field)
        if field_schema.get("x-user-confirmation") is True:
            confirmation_required.append(field)
            questions.append(_question(field, field_schema, locale))
    if not missing:
        validate_or_raise(normalized, schema, enforce_required=True)
    technical_unready = bool(
        auto_resolution["blockers"] or auto_resolution["ambiguities"]
    )
    return {
        "ready": not missing and not technical_unready,
        "story": str(story_path),
        "schema": schema_label,
        "missing_fields": missing,
        "confirmation_required": confirmation_required,
        "questions": questions,
        "auto_resolution": auto_resolution,
        "normalized": normalized,
    }


def assess_story(
    story_path: Path,
    schema_path: Path = DEFAULT_SCHEMA,
    *,
    locale: str = "ru",
) -> dict[str, Any]:
    return _assess_loaded(
        story_path,
        _read_json_object(story_path, "story"),
        load_schema(schema_path),
        locale=locale,
        schema_label=str(schema_path),
    )


def _target_for_write(story: dict[str, Any], pointer: str) -> dict[str, Any]:
    current = story
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        value = current.get(token)
        if value is None:
            value = {}
            current[token] = value
        if not isinstance(value, dict):
            raise ValueError(f"story value at {pointer} cannot be written as an object")
        current = value
    return current


def write_auto_resolved_paths(
    story_path: Path,
    schema_path: Path = DEFAULT_SCHEMA,
    *,
    locale: str = "ru",
) -> dict[str, Any]:
    if story_path.is_symlink():
        raise ValueError("refusing to write story through a symlink")
    result = assess_story(story_path, schema_path, locale=locale)
    resolved = result["auto_resolution"]["resolved"]
    if not resolved:
        return result
    story = _read_json_object(story_path, "story")
    schema = load_schema(schema_path)
    pointer = schema.get("x-story-pointer")
    if not isinstance(pointer, str):
        raise ValueError("publication schema must declare x-story-pointer")
    target = _target_for_write(story, pointer)
    for item in resolved:
        target[item["field"]] = item["value"]
    parent = story_path.resolve().parent
    mode = story_path.stat().st_mode & 0o777
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{story_path.name}.", suffix=".tmp", dir=parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(story, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, story_path)
    finally:
        temporary.unlink(missing_ok=True)
    return assess_story(story_path, schema_path, locale=locale)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_package_paths(
    story_path: Path, schema: dict[str, Any], config: dict[str, Any]
) -> dict[str, Path]:
    root = story_path.resolve().parent
    result: dict[str, Path] = {}
    properties = schema.get("properties", {})
    for field, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            continue
        role = field_schema.get("x-file-role")
        if role is None:
            continue
        if not isinstance(role, str) or not role:
            raise ValueError(f"invalid x-file-role for schema property: {field}")
        value = config.get(field)
        if not isinstance(value, str):
            raise ValueError(f"configured package path is missing: {field}")
        candidate = (root / value).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"configured package path escapes story directory: {field}") from exc
        if not candidate.is_file():
            raise ValueError(f"configured package file is missing: {field}: {candidate}")
        if role in result:
            raise ValueError(f"duplicate x-file-role in publication schema: {role}")
        result[role] = candidate
    if not result:
        raise ValueError("publication schema declares no x-file-role properties")
    return result


def _validate_location_binding(config: dict[str, Any], paths: dict[str, Path]) -> None:
    if config.get("location_decision") != "description":
        return
    location = config.get("location_text")
    description_path = paths.get("description_file")
    if not isinstance(location, str) or description_path is None:
        raise ValueError("location description binding is incomplete")
    try:
        description = description_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read approved description: {exc}") from exc
    if location not in description:
        raise ValueError(
            "location_text must appear exactly in the configured description_file"
        )


def build_approved_manifest(
    story_path: Path,
    schema_path: Path = DEFAULT_SCHEMA,
    manifest_schema_path: Path = DEFAULT_MANIFEST_SCHEMA,
    *,
    approved_at: str,
    approval_note: str,
) -> dict[str, Any]:
    assessed = assess_story(story_path, schema_path)
    if not assessed["ready"]:
        unresolved = list(assessed["missing_fields"])
        unresolved.extend(
            item["field"] for key in ("blockers", "ambiguities")
            for item in assessed["auto_resolution"][key]
            if item["field"] not in unresolved
        )
        raise ValueError(
            "metadata preflight is incomplete: " + ", ".join(unresolved)
        )
    config = assessed["normalized"]
    schema = load_schema(schema_path)
    paths = resolve_package_paths(story_path, schema, config)
    _validate_location_binding(config, paths)
    manifest = {
        "schema_version": 1,
        "platform": "youtube",
        "publication_schema_hash": _sha256_file(schema_path),
        "configuration_hash": _sha256_json(config),
        "package": {role: _sha256_file(path) for role, path in sorted(paths.items())},
        "approval": {
            "approved": True,
            "approved_at": approved_at,
            "note": approval_note,
        },
    }
    validate_or_raise(manifest, load_schema(manifest_schema_path))
    return manifest


def verify_approved_manifest_snapshot(
    manifest_path: Path,
    story_path: Path,
    schema_path: Path = DEFAULT_SCHEMA,
    manifest_schema_path: Path = DEFAULT_MANIFEST_SCHEMA,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Path]]:
    manifest = _read_json_object(manifest_path, "approval manifest")
    manifest_schema, _manifest_schema_bytes = load_schema_snapshot(manifest_schema_path)
    validate_or_raise(manifest, manifest_schema)
    schema, schema_bytes = load_schema_snapshot(schema_path)
    if manifest["publication_schema_hash"] != hashlib.sha256(schema_bytes).hexdigest():
        raise ValueError("publication schema hash does not match approved manifest")
    story = _read_json_object(story_path, "story")
    assessed = _assess_loaded(
        story_path, story, schema, schema_label=str(schema_path)
    )
    if not assessed["ready"]:
        raise ValueError("current story publication configuration is incomplete")
    config = assessed["normalized"]
    if manifest["configuration_hash"] != _sha256_json(config):
        raise ValueError("publication configuration hash does not match approval")
    paths = resolve_package_paths(story_path, schema, config)
    package = manifest["package"]
    if set(package) != set(paths):
        raise ValueError("approval manifest package roles do not match publication schema")
    for role, path in paths.items():
        if package.get(role) != _sha256_file(path):
            raise ValueError(f"metadata preflight {role} hash does not match")
    _validate_location_binding(config, paths)
    return config, manifest, schema, paths


def verify_approved_manifest(
    manifest_path: Path,
    story_path: Path,
    schema_path: Path = DEFAULT_SCHEMA,
    manifest_schema_path: Path = DEFAULT_MANIFEST_SCHEMA,
) -> dict[str, Any]:
    config, _manifest, _schema, _paths = verify_approved_manifest_snapshot(
        manifest_path, story_path, schema_path, manifest_schema_path
    )
    return config


def _write_new_private_json(path: Path, payload: dict[str, Any]) -> None:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError(f"approval manifest already exists: {path}") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    assess_parser = commands.add_parser("assess")
    assess_parser.add_argument("--story", required=True, type=Path)
    assess_parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    assess_parser.add_argument("--locale", default="ru")
    resolve_parser = commands.add_parser("resolve")
    resolve_parser.add_argument("--story", required=True, type=Path)
    resolve_parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    resolve_parser.add_argument("--locale", default="ru")
    resolve_parser.add_argument("--write", action="store_true")
    approve_parser = commands.add_parser("approve")
    approve_parser.add_argument("--story", required=True, type=Path)
    approve_parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    approve_parser.add_argument(
        "--manifest-schema", type=Path, default=DEFAULT_MANIFEST_SCHEMA
    )
    approve_parser.add_argument("--approved-at", required=True)
    approve_parser.add_argument("--approval-note", required=True)
    approve_parser.add_argument("--output", required=True, type=Path)
    approve_parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    if args.command == "approve" and not args.approved:
        raise SystemExit("Refusing manifest creation without explicit --approved")
    try:
        if args.command == "assess":
            result = assess_story(args.story, args.schema, locale=args.locale)
        elif args.command == "resolve":
            result = (
                write_auto_resolved_paths(
                    args.story, args.schema, locale=args.locale
                )
                if args.write
                else assess_story(args.story, args.schema, locale=args.locale)
            )
        else:
            manifest = build_approved_manifest(
                args.story,
                args.schema,
                args.manifest_schema,
                approved_at=args.approved_at,
                approval_note=args.approval_note,
            )
            _write_new_private_json(args.output, manifest)
            result = {"ok": True, "output": str(args.output), "package": manifest["package"]}
    except (OSError, ValueError) as exc:
        raise SystemExit(json.dumps({
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }, ensure_ascii=False)) from None
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
