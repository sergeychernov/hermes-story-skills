#!/usr/bin/env python3
"""Validation and Story-context projection for a versioned travel brief."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from urllib.parse import urlparse

ROOT_FIELDS = {
    "schema_version", "id", "title", "status", "travelers", "constraints",
    "route", "capture_suggestions", "sources",
}
STATUSES = {"draft", "validated"}


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return [item.strip() for item in value]


def validate_travel_brief(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("travel brief must be an object")
    unknown = sorted(set(raw) - ROOT_FIELDS)
    if unknown:
        raise ValueError("unknown root fields: " + ", ".join(unknown))
    if raw.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    result = deepcopy(raw)
    result["id"] = _text(result.get("id"), "id")
    result["title"] = _text(result.get("title"), "title")
    status = result.get("status", "draft")
    if status not in STATUSES:
        raise ValueError(f"unsupported status: {status}")
    result["status"] = status
    result["travelers"] = _string_list(result.get("travelers", []), "travelers")

    constraints = result.get("constraints", {})
    if not isinstance(constraints, dict):
        raise ValueError("constraints must be an object")
    avoid = [mode.casefold() for mode in _string_list(
        constraints.get("avoid_modes", []), "constraints.avoid_modes"
    )]
    accessibility = _string_list(constraints.get("accessibility", []), "constraints.accessibility")
    constraints["avoid_modes"] = avoid
    constraints["accessibility"] = accessibility
    result["constraints"] = constraints

    route = result.get("route")
    if not isinstance(route, dict):
        raise ValueError("route must be an object")
    route["origin"] = _text(route.get("origin"), "route.origin")
    route["destination"] = _text(route.get("destination"), "route.destination")
    legs = route.get("legs")
    if not isinstance(legs, list) or not legs:
        raise ValueError("route.legs must be a non-empty list")
    for index, leg in enumerate(legs):
        if not isinstance(leg, dict):
            raise ValueError(f"route.legs[{index}] must be an object")
        for field in ("mode", "from", "to"):
            leg[field] = _text(leg.get(field), f"route.legs[{index}].{field}")
        leg["mode"] = leg["mode"].casefold()
        if leg["mode"] in avoid:
            raise ValueError(f"route.legs[{index}].mode violates constraints.avoid_modes")
    result["route"] = route

    captures = result.get("capture_suggestions", [])
    if not isinstance(captures, list):
        raise ValueError("capture_suggestions must be a list")
    for index, capture in enumerate(captures):
        if not isinstance(capture, dict):
            raise ValueError(f"capture_suggestions[{index}] must be an object")
        for field in ("when", "subject", "story_hint"):
            capture[field] = _text(capture.get(field), f"capture_suggestions[{index}].{field}")
    result["capture_suggestions"] = captures

    sources = result.get("sources", [])
    if not isinstance(sources, list) or (status == "validated" and not sources):
        raise ValueError("validated travel brief requires a non-empty sources list")
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"sources[{index}] must be an object")
        for field in ("kind", "url", "observed_at"):
            source[field] = _text(source.get(field), f"sources[{index}].{field}")
        parsed = urlparse(source["url"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"sources[{index}].url must be an absolute HTTPS URL")
        try:
            observed = datetime.fromisoformat(source["observed_at"].replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"sources[{index}].observed_at must be an ISO-8601 timestamp") from None
        if observed.tzinfo is None:
            raise ValueError(f"sources[{index}].observed_at must include a timezone")
    result["sources"] = sources
    return result


def to_story_context(brief: dict) -> dict:
    brief = validate_travel_brief(brief)
    route = brief["route"]
    return {
        "occasion": brief["title"],
        "people": list(brief["travelers"]),
        "places": [route["origin"], route["destination"]],
        "source": "travel-planning",
        "extensions": {
            "travel": {
                "brief_id": brief["id"],
                "status": brief["status"],
                "route": deepcopy(route),
                "capture_suggestions": deepcopy(brief["capture_suggestions"]),
                "sources": deepcopy(brief["sources"]),
            }
        },
    }
