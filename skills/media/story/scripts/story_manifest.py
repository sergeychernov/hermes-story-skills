#!/usr/bin/env python3
"""Validation and normalization for the domain-neutral story manifest."""
from __future__ import annotations

from copy import deepcopy

ROOT_FIELDS = {
    "schema_version", "id", "title", "status", "story_type", "arc", "scenes",
    "context", "publication", "render_ready", "pending_scene_ids",
}
STATUSES = {"collecting", "title-review", "scene-review", "ready-to-render", "rendered", "verified"}
APPROVALS = {"pending", "provisional", "approved", "rejected"}
KINDS = {"image", "video", "group"}
PUBLICATION_STATUSES = {"not-approved", "approved", "published"}


def _required_text(data: dict, field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def validate_story(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("story manifest must be an object")
    unknown = sorted(set(raw) - ROOT_FIELDS)
    if unknown:
        raise ValueError(f"unknown root fields: {', '.join(unknown)}")
    if raw.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    result = deepcopy(raw)
    result["id"] = _required_text(result, "id")
    result["title"] = _required_text(result, "title")
    status = str(result.get("status", "collecting"))
    if status not in STATUSES:
        raise ValueError(f"unsupported story status: {status}")
    result["status"] = status
    result["story_type"] = str(result.get("story_type", "moment")).strip() or "moment"

    arc = result.get("arc", {})
    if not isinstance(arc, dict):
        raise ValueError("arc must be an object")
    beats = arc.get("beats", [])
    if not isinstance(beats, list) or not all(isinstance(beat, str) and beat.strip() for beat in beats):
        raise ValueError("arc.beats must be a list of non-empty strings")
    result["arc"] = {**arc, "beats": [beat.strip() for beat in beats]}

    context = result.get("context", {})
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    context.setdefault("occasion", None)
    context.setdefault("people", [])
    context.setdefault("places", [])
    context.setdefault("source", "conversation")
    context.setdefault("extensions", {})
    for field in ("people", "places"):
        if not isinstance(context[field], list):
            raise ValueError(f"context.{field} must be a list")
    if not isinstance(context["extensions"], dict):
        raise ValueError("context.extensions must be an object")
    result["context"] = context

    scenes = result.get("scenes", [])
    if not isinstance(scenes, list):
        raise ValueError("scenes must be a list")
    seen: set[str] = set()
    pending: list[str] = []
    normalized_scenes: list[dict] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            raise ValueError("each scene must be an object")
        scene = deepcopy(scene)
        scene_id = _required_text(scene, "id")
        scene["id"] = scene_id
        if scene_id in seen:
            raise ValueError(f"duplicate scene id: {scene_id}")
        seen.add(scene_id)
        scene["media_id"] = _required_text(scene, "media_id")
        kind = str(scene.get("kind", ""))
        if kind not in KINDS:
            raise ValueError(f"unsupported scene kind: {kind}")
        scene["kind"] = kind
        if kind == "group":
            members = scene.get("members")
            if (
                not isinstance(members, list)
                or len(members) < 2
                or not all(isinstance(member, str) and member.strip() for member in members)
            ):
                raise ValueError("group scene requires at least two non-empty member ids")
            if not isinstance(scene.get("artifact"), str) or not scene["artifact"].strip():
                raise ValueError("group scene requires a non-empty artifact path")
            scene["members"] = [member.strip() for member in members]
            scene["artifact"] = scene["artifact"].strip()
            if "report" in scene:
                if not isinstance(scene["report"], str) or not scene["report"].strip():
                    raise ValueError("group scene report must be a non-empty string when provided")
                scene["report"] = scene["report"].strip()
        approval = str(scene.get("approval", "pending"))
        if approval not in APPROVALS:
            raise ValueError(f"unsupported scene approval: {approval}")
        scene["approval"] = approval
        if approval != "approved":
            pending.append(scene_id)
        normalized_scenes.append(scene)
    result["scenes"] = normalized_scenes

    all_scene_ids = {scene["id"] for scene in normalized_scenes}
    for scene in normalized_scenes:
        if scene["kind"] != "group":
            continue
        members = scene["members"]
        if len(set(members)) != len(members):
            raise ValueError(f"group scene {scene['id']} member ids must be unique")
        if scene["id"] in members:
            raise ValueError(f"group scene {scene['id']} cannot contain itself")
        unknown_members = sorted(set(members) - all_scene_ids)
        if unknown_members:
            raise ValueError(
                f"group scene {scene['id']} references unknown member ids: {', '.join(unknown_members)}"
            )

    publication = result.get("publication", {})
    if not isinstance(publication, dict):
        raise ValueError("publication must be an object")
    publication_status = str(publication.get("status", "not-approved"))
    if publication_status not in PUBLICATION_STATUSES:
        raise ValueError(f"unsupported publication status: {publication_status}")
    publication["status"] = publication_status
    result["publication"] = publication
    render_ready = bool(scenes) and not pending
    if status in {"ready-to-render", "rendered", "verified"} and not render_ready:
        raise ValueError(f"story status {status} requires a non-empty render-ready scene set")
    if publication_status != "not-approved" and status != "verified":
        raise ValueError("publication approval requires story status verified")
    if "pending_scene_ids" in raw and raw["pending_scene_ids"] != pending:
        raise ValueError("pending_scene_ids contradict scene approvals")
    if "render_ready" in raw and raw["render_ready"] is not render_ready:
        raise ValueError("render_ready contradicts scene approvals")
    result["pending_scene_ids"] = pending
    result["render_ready"] = render_ready
    return result
