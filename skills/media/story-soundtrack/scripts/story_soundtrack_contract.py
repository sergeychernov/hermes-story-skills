"""Strict JSON contract validation for story-soundtrack skill."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
AUDIO_CLASSES = frozenset({"voice", "source_music", "silent"})
REVISION_TOKEN_BOUNDARY_RE = re.compile(r"(?:^|[/_.\-])v(\d+)(?:[/_.\-]|\.|$)")

SUPPORTED_INSTRUMENTS = frozenset({"guzheng", "dizi", "bass", "drums"})
PENTATONIC_TONAL_CENTER = "D"
PENTATONIC_PITCH_COLLECTION = ("D", "E", "F#", "A", "B")
RHYTHM_INSTRUMENTS = frozenset({"guzheng", "bass", "drums"})

LAYER_INSTRUMENT_MAP = {
    "guzheng_pluck": "guzheng",
    "guzheng_pad": "guzheng",
    "guzheng_comping": "guzheng",
    "bass": "bass",
    "low_drum": "drums",
    "woodblock": "drums",
    "shaker": "drums",
    "dizi_melody": "dizi",
}

OUTPUT_KEYS = (
    "rhythm_wav",
    "melody_wav",
    "full_score_wav",
    "source_mixed_wav",
    "rhythm_preview_m4a",
    "full_preview_m4a",
    "source_mixed_approval_m4a",
    "report_json",
    "approval_json",
    "handoff_json",
)

FEEDBACK_CHANGE_KEYS: dict[str, frozenset[str]] = {
    "style": frozenset({
        "preset", "brief", "bpm", "meter", "tonal_center",
        "pitch_collection", "instrumentation", "seed",
    }),
    "theme": frozenset({"id", "role", "scene_ids", "energy"}),
    "rhythm": frozenset({"rhythm_gain"}),
    "melody": frozenset({"melody_gain"}),
    "routing": frozenset({"scene_id", "source_gain", "rhythm_gain", "melody_gain"}),
    "source_mix": frozenset({"scene_id", "source_gain"}),
    "loudness": frozenset({
        "final_lufs_min", "final_lufs_max", "final_true_peak_dbfs",
        "transition_ms", "duration_tolerance_seconds",
        "encoded_lufs_tolerance_db", "encoded_true_peak_tolerance_db",
    }),
}


class ContractError(ValueError):
    """Raised when a contract or timeline JSON is invalid."""


def resolve_under(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ContractError("path must be a non-empty string")
    candidate = (root / value).resolve()
    if candidate != root.resolve() and root.resolve() not in candidate.parents:
        raise ContractError(f"path escapes root: {value}")
    return candidate


def replace_revision_token(path: str, from_revision: int, to_revision: int) -> str:
    out: list[str] = []
    pos = 0
    found = False
    for match in REVISION_TOKEN_BOUNDARY_RE.finditer(path):
        out.append(path[pos:match.start()])
        token = match.group(0)
        num = int(match.group(1))
        if num == from_revision:
            out.append(token.replace(f"v{from_revision}", f"v{to_revision}", 1))
            found = True
        else:
            out.append(token)
        pos = match.end()
    out.append(path[pos:])
    if not found:
        raise ContractError(f"output path missing revision token v{from_revision}: {path}")
    return "".join(out)


def resolve_layer_mapping(instrumentation: list[str]) -> dict[str, bool]:
    enabled = set(instrumentation)
    return {layer: controller in enabled for layer, controller in LAYER_INSTRUMENT_MAP.items()}


def revision_token_matches(path: str, revision: int) -> bool:
    for match in REVISION_TOKEN_BOUNDARY_RE.finditer(path):
        if int(match.group(1)) == revision:
            return True
    return False


def _reject_unknown(obj: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(obj) - allowed
    if unknown:
        raise ContractError(f"unknown {label} fields: {', '.join(sorted(unknown))}")
    missing = allowed - set(obj)
    if missing:
        raise ContractError(f"missing {label} fields: {', '.join(sorted(missing))}")


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ContractError(f"{path} must be a JSON object")
    return data


def exact_pcm_frames(total_frames: int, fps: float, sample_rate_hz: int) -> int:
    if total_frames <= 0:
        raise ContractError("total_frames must be positive")
    if fps <= 0:
        raise ContractError("fps must be positive")
    exact = total_frames * sample_rate_hz / fps
    if not math.isclose(exact, round(exact), rel_tol=0, abs_tol=1e-9):
        raise ContractError(
            f"non-integral sample mapping: {total_frames} frames @ {fps} fps -> {exact} samples"
        )
    return int(round(exact))


def _validate_timeline_block(timeline: dict[str, Any]) -> dict[str, Any]:
    allowed = {"path", "fps", "total_frames", "sample_rate_hz"}
    _reject_unknown(timeline, allowed, "timeline")
    sr = int(timeline["sample_rate_hz"])
    if sr != 48000:
        raise ContractError("timeline.sample_rate_hz must be 48000")
    fps = float(timeline["fps"])
    total_frames = int(timeline["total_frames"])
    exact_frames = exact_pcm_frames(total_frames, fps, sr)
    return {
        "path": str(timeline["path"]),
        "fps": fps,
        "total_frames": total_frames,
        "sample_rate_hz": sr,
        "exact_pcm_frames": exact_frames,
        "exact_duration_seconds": exact_frames / sr,
    }


def _validate_style(style: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "preset", "brief", "bpm", "meter", "tonal_center",
        "pitch_collection", "instrumentation", "seed",
    }
    _reject_unknown(style, allowed, "style")
    preset = str(style["preset"])
    if preset != "procedural_pentatonic_v1":
        raise ContractError(f"unsupported style preset: {preset}")
    bpm = float(style["bpm"])
    if not 40.0 <= bpm <= 180.0:
        raise ContractError("style.bpm must be within 40..180")
    seed = int(style["seed"])
    if not 0 <= seed <= 4294967295:
        raise ContractError("style.seed must be within 0..4294967295")
    pitch = style["pitch_collection"]
    if not isinstance(pitch, list) or not pitch or not all(isinstance(p, str) for p in pitch):
        raise ContractError("style.pitch_collection must be a non-empty string list")
    pitch_norm = [str(p) for p in pitch]
    if pitch_norm != list(PENTATONIC_PITCH_COLLECTION):
        raise ContractError(
            "procedural_pentatonic_v1 requires pitch_collection "
            + str(list(PENTATONIC_PITCH_COLLECTION))
        )
    tonal_center = str(style["tonal_center"])
    if tonal_center != PENTATONIC_TONAL_CENTER:
        raise ContractError(
            f"procedural_pentatonic_v1 requires tonal_center {PENTATONIC_TONAL_CENTER}, got {tonal_center}"
        )
    inst = style["instrumentation"]
    if not isinstance(inst, list) or not inst:
        raise ContractError("style.instrumentation must be a non-empty list")
    inst_norm = [str(name) for name in inst]
    unsupported = [name for name in inst_norm if name not in SUPPORTED_INSTRUMENTS]
    if unsupported:
        raise ContractError(
            "unsupported instrumentation for procedural_pentatonic_v1: "
            + ", ".join(sorted(unsupported))
        )
    if "dizi" not in inst_norm:
        raise ContractError("instrumentation must include dizi for melody")
    if not set(inst_norm) & RHYTHM_INSTRUMENTS:
        raise ContractError(
            "instrumentation must include at least one rhythm instrument: guzheng, bass, or drums"
        )
    return {
        "preset": preset,
        "brief": str(style["brief"]),
        "bpm": bpm,
        "meter": str(style["meter"]),
        "tonal_center": tonal_center,
        "pitch_collection": pitch_norm,
        "instrumentation": inst_norm,
        "seed": seed,
    }


def _validate_dramaturgy(dramaturgy: dict[str, Any]) -> dict[str, Any]:
    allowed = {"opening", "development", "climax_scene_id", "resolution"}
    _reject_unknown(dramaturgy, allowed, "dramaturgy")
    return {
        "opening": str(dramaturgy["opening"]),
        "development": str(dramaturgy["development"]),
        "climax_scene_id": str(dramaturgy["climax_scene_id"]),
        "resolution": str(dramaturgy["resolution"]),
    }


def _validate_theme(theme: dict[str, Any], scene_ids: set[str]) -> dict[str, Any]:
    allowed = {"id", "role", "scene_ids", "energy"}
    _reject_unknown(theme, allowed, "theme")
    tid = str(theme["id"])
    t_scenes = theme["scene_ids"]
    if not isinstance(t_scenes, list) or not t_scenes:
        raise ContractError(f"theme {tid} scene_ids must be a non-empty list")
    for sid in t_scenes:
        if sid not in scene_ids:
            raise ContractError(f"theme {tid} references unknown scene {sid}")
    energy = float(theme["energy"])
    if not 0.0 <= energy <= 1.0:
        raise ContractError(f"theme {tid} energy must be within 0..1")
    return {
        "id": tid,
        "role": str(theme["role"]),
        "scene_ids": list(t_scenes),
        "energy": energy,
    }


def _validate_scene(scene: dict[str, Any], index: int) -> dict[str, Any]:
    allowed = {
        "id", "frames", "audio_class", "source_audio", "theme_ids", "routing",
    }
    _reject_unknown(scene, allowed, "scene")
    sid = str(scene["id"])
    frames = scene["frames"]
    if (
        not isinstance(frames, list)
        or len(frames) != 2
        or not all(isinstance(f, int) for f in frames)
        or frames[0] < 0
        or frames[1] <= frames[0]
    ):
        raise ContractError(f"scene {sid} frames must be [start, end) with end > start")
    audio_class = str(scene["audio_class"])
    if audio_class not in AUDIO_CLASSES:
        raise ContractError(f"scene {sid} has invalid audio_class: {audio_class}")
    source_audio = scene["source_audio"]
    if audio_class == "silent":
        if source_audio is not None:
            raise ContractError(f"scene {sid} silent class forbids source_audio")
    else:
        if not isinstance(source_audio, str) or not source_audio:
            raise ContractError(f"scene {sid} requires source_audio for {audio_class}")
    routing = scene["routing"]
    routing_allowed = {"source_gain", "rhythm_gain", "melody_gain"}
    if not isinstance(routing, dict):
        raise ContractError(f"scene {sid} routing must be an object")
    _reject_unknown(routing, routing_allowed, f"scene {sid} routing")
    theme_ids = scene["theme_ids"]
    if not isinstance(theme_ids, list):
        raise ContractError(f"scene {sid} theme_ids must be a list")
    return {
        "id": sid,
        "frames": [int(frames[0]), int(frames[1])],
        "audio_class": audio_class,
        "source_audio": source_audio,
        "theme_ids": list(theme_ids),
        "routing": {
            "source_gain": float(routing["source_gain"]),
            "rhythm_gain": float(routing["rhythm_gain"]),
            "melody_gain": float(routing["melody_gain"]),
        },
        "_index": index,
    }


def _validate_scenes(scenes: list[Any], total_frames: int) -> list[dict[str, Any]]:
    if not isinstance(scenes, list) or not scenes:
        raise ContractError("scenes must be a non-empty list")
    validated: list[dict[str, Any]] = []
    expected_start = 0
    seen_ids: set[str] = set()
    for index, raw in enumerate(scenes):
        scene = _validate_scene(raw, index)
        sid = scene["id"]
        if sid in seen_ids:
            raise ContractError(f"duplicate scene id: {sid}")
        seen_ids.add(sid)
        start, end = scene["frames"]
        if start != expected_start:
            raise ContractError(
                f"scene order/frame gap: expected start {expected_start}, got {start} in {sid}"
            )
        expected_start = end
        validated.append(scene)
    if expected_start != total_frames:
        raise ContractError(
            f"scene coverage mismatch: scenes end at {expected_start}, timeline has {total_frames}"
        )
    return validated


def _validate_outputs(outputs: dict[str, Any], revision: int) -> dict[str, str]:
    _reject_unknown(outputs, set(OUTPUT_KEYS), "outputs")
    rev_token = f"v{revision}"
    values = {k: str(outputs[k]) for k in OUTPUT_KEYS}
    paths = list(values.values())
    if len(set(paths)) != len(paths):
        raise ContractError("output paths must be unique")
    for key, path in values.items():
        if not revision_token_matches(path, revision):
            raise ContractError(f"output {key} must include revision token {rev_token}")
    return values


def _validate_qa(qa: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "final_lufs_min", "final_lufs_max", "final_true_peak_dbfs",
        "transition_ms", "duration_tolerance_seconds",
        "encoded_lufs_tolerance_db", "encoded_true_peak_tolerance_db",
    }
    _reject_unknown(qa, allowed, "qa")
    lufs_min = float(qa["final_lufs_min"])
    lufs_max = float(qa["final_lufs_max"])
    if lufs_min > lufs_max:
        raise ContractError("qa.final_lufs_min must be <= final_lufs_max")
    encoded_lufs_tol = float(qa["encoded_lufs_tolerance_db"])
    encoded_tp_tol = float(qa["encoded_true_peak_tolerance_db"])
    if not 0.0 <= encoded_lufs_tol <= 2.0:
        raise ContractError("qa.encoded_lufs_tolerance_db must be within 0..2")
    if not 0.0 <= encoded_tp_tol <= 3.0:
        raise ContractError("qa.encoded_true_peak_tolerance_db must be within 0..3")
    return {
        "final_lufs_min": lufs_min,
        "final_lufs_max": lufs_max,
        "final_true_peak_dbfs": float(qa["final_true_peak_dbfs"]),
        "transition_ms": int(qa["transition_ms"]),
        "duration_tolerance_seconds": float(qa["duration_tolerance_seconds"]),
        "encoded_lufs_tolerance_db": encoded_lufs_tol,
        "encoded_true_peak_tolerance_db": encoded_tp_tol,
    }


def _validate_root_confinement(spec: dict[str, Any], root: Path) -> None:
    root = root.resolve()
    resolve_under(root, str(spec["timeline"]["path"]))
    for scene in spec["scenes"]:
        src = scene.get("source_audio")
        if isinstance(src, str) and src:
            resolve_under(root, src)
    for path in spec["outputs"].values():
        resolve_under(root, str(path))


def _validate_no_output_input_alias(spec: dict[str, Any], root: Path) -> None:
    root = root.resolve()
    outputs = {resolve_under(root, str(v)).resolve() for v in spec["outputs"].values()}
    inputs: set[Path] = {resolve_under(root, str(spec["timeline"]["path"])).resolve()}
    for scene in spec["scenes"]:
        src = scene.get("source_audio")
        if isinstance(src, str) and src:
            inputs.add(resolve_under(root, src).resolve())
    overlap = outputs & inputs
    if overlap:
        rel = sorted(str(p.relative_to(root)) if root in p.parents else str(p) for p in overlap)
        raise ContractError(f"output cannot alias input: {', '.join(rel)}")


def validate_spec_dict(spec: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    allowed = {
        "schema_version", "story_id", "revision", "state", "timeline", "style",
        "dramaturgy", "themes", "scenes", "outputs", "qa",
    }
    _reject_unknown(spec, allowed, "spec")
    if int(spec["schema_version"]) != SCHEMA_VERSION:
        raise ContractError("unsupported schema_version")
    revision = int(spec["revision"])
    if revision < 1:
        raise ContractError("revision must be a positive integer")
    state = str(spec["state"])
    if state != "PLANNED":
        raise ContractError(
            "versioned spec must remain PLANNED; state transitions live in hash-bound artifacts "
            f"(STEMS_RENDERED, SOURCE_MIX_REVIEW, USER_APPROVED, HANDED_OFF_TO_SHORTS), got {state}"
        )
    timeline = _validate_timeline_block(spec["timeline"])
    style = _validate_style(spec["style"])
    dramaturgy = _validate_dramaturgy(spec["dramaturgy"])
    scenes = _validate_scenes(spec["scenes"], timeline["total_frames"])
    scene_ids = {s["id"] for s in scenes}
    if dramaturgy["climax_scene_id"] not in scene_ids:
        raise ContractError("dramaturgy.climax_scene_id not found in scenes")
    themes_raw = spec["themes"]
    if not isinstance(themes_raw, list) or not themes_raw:
        raise ContractError("themes must be a non-empty list")
    theme_ids: set[str] = set()
    themes: list[dict[str, Any]] = []
    for raw in themes_raw:
        theme = _validate_theme(raw, scene_ids)
        if theme["id"] in theme_ids:
            raise ContractError(f"duplicate theme id: {theme['id']}")
        theme_ids.add(theme["id"])
        themes.append(theme)
    for scene in scenes:
        for tid in scene["theme_ids"]:
            if tid not in theme_ids:
                raise ContractError(f"scene {scene['id']} references unknown theme {tid}")
    outputs = _validate_outputs(spec["outputs"], revision)
    qa = _validate_qa(spec["qa"])
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "story_id": str(spec["story_id"]),
        "revision": revision,
        "state": state,
        "timeline": timeline,
        "style": style,
        "dramaturgy": dramaturgy,
        "themes": themes,
        "scenes": scenes,
        "outputs": outputs,
        "qa": qa,
    }
    if root is not None:
        _validate_root_confinement(spec, root)
        result["resolved_paths"] = {k: resolve_under(root, v) for k, v in outputs.items()}
        result["timeline_path"] = resolve_under(root, timeline["path"])
        _validate_no_output_input_alias(spec, root)
    return result


def load_and_validate_spec(root: Path, spec_path: Path) -> dict[str, Any]:
    root = root.resolve()
    spec_path = spec_path.resolve()
    if spec_path != root and root not in spec_path.parents:
        raise ContractError("spec path escapes root")
    spec = _load_json(spec_path)
    validated = validate_spec_dict(spec, root=root)
    validated["spec_path"] = spec_path
    validated["root"] = root
    return validated


def load_timeline(root: Path, timeline_rel: str) -> dict[str, Any]:
    timeline_path = resolve_under(root, timeline_rel)
    timeline = _load_json(timeline_path)
    allowed = {"schema_version", "story_id", "fps", "total_frames", "scenes"}
    _reject_unknown(timeline, allowed, "timeline file")
    if int(timeline["schema_version"]) != SCHEMA_VERSION:
        raise ContractError("unsupported timeline schema_version")
    return timeline


def validate_timeline_agreement(validated: dict[str, Any], timeline: dict[str, Any]) -> None:
    tl = validated["timeline"]
    if float(timeline["fps"]) != tl["fps"]:
        raise ContractError("timeline fps mismatch between spec and timeline file")
    if int(timeline["total_frames"]) != tl["total_frames"]:
        raise ContractError("timeline total_frames mismatch between spec and timeline file")
    if str(timeline["story_id"]) != validated["story_id"]:
        raise ContractError("timeline story_id mismatch")
    tl_scenes = timeline["scenes"]
    if not isinstance(tl_scenes, list):
        raise ContractError("timeline scenes must be a list")
    spec_scenes = validated["scenes"]
    if len(tl_scenes) != len(spec_scenes):
        raise ContractError("timeline scene count mismatch")
    for tl_scene, spec_scene in zip(tl_scenes, spec_scenes):
        allowed = {"id", "frames"}
        if not isinstance(tl_scene, dict):
            raise ContractError("timeline scene must be an object")
        _reject_unknown(tl_scene, allowed, "timeline scene")
        if tl_scene["id"] != spec_scene["id"]:
            raise ContractError("timeline scene id order mismatch")
        if tl_scene["frames"] != spec_scene["frames"]:
            raise ContractError(f"timeline scene frames mismatch for {spec_scene['id']}")


def default_routing_for_class(audio_class: str) -> dict[str, float]:
    if audio_class == "voice":
        return {"source_gain": 1.0, "rhythm_gain": 0.456, "melody_gain": 0.0}
    if audio_class == "source_music":
        return {"source_gain": 1.0, "rhythm_gain": 0.0, "melody_gain": 0.0}
    if audio_class == "silent":
        return {"source_gain": 0.0, "rhythm_gain": 1.0, "melody_gain": 1.0}
    raise ContractError(f"unknown audio_class: {audio_class}")


def _validate_feedback_change(target: str, payload: dict[str, Any]) -> None:
    allowed = FEEDBACK_CHANGE_KEYS.get(target)
    if allowed is None:
        raise ContractError(f"unknown change target: {target}")
    unknown = set(payload) - allowed
    if unknown:
        raise ContractError(
            f"unknown fields for feedback target {target}: {', '.join(sorted(unknown))}"
        )


def _spec_payload(spec: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "schema_version", "story_id", "revision", "state", "timeline", "style",
        "dramaturgy", "themes", "scenes", "outputs", "qa",
    }
    result = {key: spec[key] for key in allowed if key in spec}
    timeline = result.get("timeline")
    if isinstance(timeline, dict):
        result["timeline"] = {
            k: timeline[k]
            for k in ("path", "fps", "total_frames", "sample_rate_hz")
            if k in timeline
        }
    scenes = result.get("scenes")
    if isinstance(scenes, list):
        scene_keys = ("id", "frames", "audio_class", "source_audio", "theme_ids", "routing")
        result["scenes"] = [
            {k: scene[k] for k in scene_keys if k in scene}
            for scene in scenes
        ]
    return result


def apply_feedback_revision(
    spec: dict[str, Any],
    feedback: dict[str, Any],
) -> dict[str, Any]:
    spec = _spec_payload(spec)
    allowed = {
        "schema_version", "story_id", "from_revision", "requested_revision",
        "user_feedback", "requested_changes",
    }
    _reject_unknown(feedback, allowed, "feedback")
    if int(feedback["schema_version"]) != SCHEMA_VERSION:
        raise ContractError("unsupported feedback schema_version")
    if feedback["story_id"] != spec["story_id"]:
        raise ContractError("feedback story_id mismatch")
    from_rev = int(feedback["from_revision"])
    req_rev = int(feedback["requested_revision"])
    if from_rev != int(spec["revision"]):
        raise ContractError("feedback from_revision does not match current spec revision")
    if req_rev != from_rev + 1:
        raise ContractError("requested_revision must be from_revision + 1")
    changes = feedback["requested_changes"]
    if not isinstance(changes, list) or not changes:
        raise ContractError("requested_changes must be a non-empty list")
    new_spec = json.loads(json.dumps(spec))
    new_spec["revision"] = req_rev
    new_spec["state"] = "PLANNED"
    for change in changes:
        allowed_change = {"target", "change"}
        if not isinstance(change, dict):
            raise ContractError("requested_changes entries must be objects")
        _reject_unknown(change, allowed_change, "requested_change")
        target = str(change["target"])
        payload = change["change"]
        if not isinstance(payload, dict):
            raise ContractError(f"{target} change must be an object")
        _validate_feedback_change(target, payload)
        if target == "style":
            new_spec["style"].update(payload)
        elif target == "theme":
            if "id" not in payload:
                raise ContractError("theme change requires id")
            tid = payload["id"]
            for theme in new_spec["themes"]:
                if theme["id"] == tid:
                    theme.update({k: v for k, v in payload.items() if k != "id"})
                    break
            else:
                raise ContractError(f"theme not found: {tid}")
        elif target == "rhythm":
            for scene in new_spec["scenes"]:
                if "rhythm_gain" in payload:
                    scene["routing"]["rhythm_gain"] = float(payload["rhythm_gain"])
        elif target == "melody":
            for scene in new_spec["scenes"]:
                if "melody_gain" in payload:
                    scene["routing"]["melody_gain"] = float(payload["melody_gain"])
        elif target == "routing":
            sid = payload.get("scene_id")
            if not sid:
                raise ContractError("routing change requires scene_id")
            for scene in new_spec["scenes"]:
                if scene["id"] == sid:
                    scene["routing"].update(
                        {k: float(v) for k, v in payload.items() if k != "scene_id"}
                    )
                    break
            else:
                raise ContractError(f"scene not found: {sid}")
        elif target == "source_mix":
            sid = payload.get("scene_id")
            if not sid:
                raise ContractError("source_mix change requires scene_id")
            if "source_gain" not in payload:
                raise ContractError("source_mix change requires source_gain")
            for scene in new_spec["scenes"]:
                if scene["id"] == sid:
                    new_gain = float(payload["source_gain"])
                    if new_gain == float(scene["routing"]["source_gain"]):
                        raise ContractError(f"source_mix change is a no-op for scene {sid}")
                    scene["routing"]["source_gain"] = new_gain
                    break
            else:
                raise ContractError(f"scene not found: {sid}")
        elif target == "loudness":
            new_spec["qa"].update(payload)
        else:
            raise ContractError(f"unknown change target: {target}")
    rev_token = f"v{req_rev}"
    for key, path in list(new_spec["outputs"].items()):
        new_spec["outputs"][key] = replace_revision_token(str(path), from_rev, req_rev)
    validate_spec_dict(new_spec)
    new_spec["feedback_record"] = {
        "from_revision": from_rev,
        "requested_revision": req_rev,
        "user_feedback": str(feedback["user_feedback"]),
    }
    return new_spec


def write_feedback_revision(
    spec: dict[str, Any],
    feedback: dict[str, Any],
    output_path: Path,
    *,
    root: Path,
) -> dict[str, Any]:
    root = root.resolve()
    output_path = output_path.resolve()
    if output_path != root and root not in output_path.parents:
        raise ContractError("output spec escapes root")
    resolve_under(root, str(output_path.relative_to(root)))
    new_spec = apply_feedback_revision(spec, feedback)
    if output_path.exists():
        raise ContractError(f"refusing to overwrite existing spec: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_spec = _spec_payload(new_spec)
    output_path.write_text(json.dumps(file_spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    feedback_record_path = output_path.with_suffix(".feedback.json")
    if feedback_record_path != root and root not in feedback_record_path.parents:
        raise ContractError("feedback record escapes root")
    resolve_under(root, str(feedback_record_path.relative_to(root)))
    if feedback_record_path.exists():
        raise ContractError(f"refusing to overwrite existing feedback record: {feedback_record_path}")
    feedback_record_path.write_text(
        json.dumps({
            "schema_version": SCHEMA_VERSION,
            "story_id": feedback["story_id"],
            "from_revision": feedback["from_revision"],
            "requested_revision": feedback["requested_revision"],
            "user_feedback": feedback["user_feedback"],
            "requested_changes": feedback["requested_changes"],
            "output_spec": str(output_path.relative_to(root)),
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return new_spec
