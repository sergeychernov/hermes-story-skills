#!/usr/bin/env python3
"""Small fail-closed JSON Schema Draft 2020-12 runtime for local skill schemas."""
from __future__ import annotations

import copy
import re
from datetime import date, datetime
from typing import Any

ANNOTATION_KEYS = {
    "$schema", "$id", "$defs", "title", "description", "default", "examples",
    "x-story-pointer", "x-user-confirmation", "x-question", "x-file-role",
    "x-auto-resolve",
}
VALIDATION_KEYS = {
    "$ref", "type", "properties", "required", "additionalProperties",
    "enum", "const", "pattern", "minLength", "format", "allOf", "if", "then",
}


def assert_supported_schema(schema: object, path: str = "$") -> None:
    if isinstance(schema, list):
        for index, item in enumerate(schema):
            assert_supported_schema(item, f"{path}[{index}]")
        return
    if not isinstance(schema, dict):
        return
    for key, value in schema.items():
        if key not in ANNOTATION_KEYS and key not in VALIDATION_KEYS:
            raise ValueError(f"unsupported JSON Schema keyword at {path}: {key}")
        if key in {"properties", "$defs"}:
            if not isinstance(value, dict):
                raise ValueError(f"{path}.{key} must be an object")
            for name, child in value.items():
                assert_supported_schema(child, f"{path}.{key}.{name}")
        elif key in {"allOf"}:
            assert_supported_schema(value, f"{path}.{key}")
        elif key in {"if", "then"}:
            assert_supported_schema(value, f"{path}.{key}")


def _resolve(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    reference = schema.get("$ref")
    if reference is None:
        return schema
    if not isinstance(reference, str) or not reference.startswith("#/"):
        raise ValueError(f"only local JSON Schema references are supported: {reference!r}")
    current: Any = root
    for raw in reference[2:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise ValueError(f"unresolved JSON Schema reference: {reference}")
        current = current[token]
    if not isinstance(current, dict):
        raise ValueError(f"JSON Schema reference is not an object: {reference}")
    return {**current, **{key: value for key, value in schema.items() if key != "$ref"}}


def _type_matches(instance: object, expected: str) -> bool:
    return {
        "object": isinstance(instance, dict),
        "array": isinstance(instance, list),
        "string": isinstance(instance, str),
        "integer": isinstance(instance, int) and not isinstance(instance, bool),
        "number": isinstance(instance, (int, float)) and not isinstance(instance, bool),
        "boolean": isinstance(instance, bool),
        "null": instance is None,
    }.get(expected, False)


def _valid_datetime(value: str) -> bool:
    if "T" not in value:
        return False
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _valid_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def validation_errors(
    instance: object,
    schema: dict[str, Any],
    *,
    root: dict[str, Any] | None = None,
    path: str = "$",
    enforce_required: bool = True,
) -> list[str]:
    root = schema if root is None else root
    schema = _resolve(schema, root)
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        expected_types = [expected] if isinstance(expected, str) else expected
        if not isinstance(expected_types, list) or not any(
            isinstance(name, str) and _type_matches(instance, name) for name in expected_types
        ):
            return [f"{path}: expected {expected} type"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: value must equal const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value is not in enum {schema['enum']!r}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: string is shorter than minLength {schema['minLength']}")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: string does not match pattern {schema['pattern']!r}")
        if schema.get("format") == "date-time" and not _valid_datetime(instance):
            errors.append(f"{path}: invalid date-time format")
        elif schema.get("format") == "date" and not _valid_date(instance):
            errors.append(f"{path}: invalid date format")
        elif schema.get("format") not in (None, "date-time", "date"):
            errors.append(f"{path}: unsupported format {schema['format']!r}")
    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            errors.append(f"{path}: schema properties must be an object")
            properties = {}
        if enforce_required:
            for name in active_required_fields(schema, instance, root=root):
                if name not in instance:
                    errors.append(f"{path}.{name}: required property is missing")
        if schema.get("additionalProperties") is False:
            for name in instance:
                if name not in properties:
                    errors.append(f"{path}.{name}: additional property is not allowed")
        for name, value in instance.items():
            if name in properties:
                errors.extend(validation_errors(
                    value, properties[name], root=root, path=f"{path}.{name}",
                    enforce_required=enforce_required,
                ))
    for child in schema.get("allOf", []):
        errors.extend(validation_errors(
            instance, child, root=root, path=path, enforce_required=enforce_required,
        ))
    if_schema = schema.get("if")
    then_schema = schema.get("then")
    if isinstance(if_schema, dict) and isinstance(then_schema, dict):
        if matches_schema(instance, if_schema, root):
            errors.extend(validation_errors(
                instance,
                then_schema,
                root=root,
                path=path,
                enforce_required=enforce_required,
            ))
    return errors


def matches_schema(instance: object, schema: dict[str, Any], root: dict[str, Any]) -> bool:
    return not validation_errors(instance, schema, root=root, enforce_required=True)


def active_required_fields(
    schema: dict[str, Any], instance: dict[str, Any], *, root: dict[str, Any]
) -> list[str]:
    schema = _resolve(schema, root)
    result: list[str] = []
    for name in schema.get("required", []):
        if name not in result:
            result.append(name)
    for condition in schema.get("allOf", []):
        condition = _resolve(condition, root)
        if_schema = condition.get("if")
        then_schema = condition.get("then")
        if isinstance(if_schema, dict) and isinstance(then_schema, dict):
            if matches_schema(instance, if_schema, root):
                for name in then_schema.get("required", []):
                    if name not in result:
                        result.append(name)
    return result


def apply_defaults(instance: object, schema: dict[str, Any], *, root=None) -> object:
    root = schema if root is None else root
    schema = _resolve(schema, root)
    result = copy.deepcopy(instance)
    if isinstance(result, dict):
        for name, child in schema.get("properties", {}).items():
            child = _resolve(child, root)
            if name not in result and "default" in child:
                result[name] = copy.deepcopy(child["default"])
            if name in result:
                result[name] = apply_defaults(result[name], child, root=root)
    return result


def validate_or_raise(instance: object, schema: dict[str, Any], *, enforce_required=True) -> None:
    assert_supported_schema(schema)
    errors = list(dict.fromkeys(
        validation_errors(instance, schema, enforce_required=enforce_required)
    ))
    if errors:
        raise ValueError("JSON Schema validation failed: " + "; ".join(errors))
