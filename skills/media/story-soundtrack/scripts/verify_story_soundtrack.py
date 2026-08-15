#!/usr/bin/env python3
"""Verify story-soundtrack artifacts and optional approved handoff."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import wave
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from story_soundtrack_contract import ContractError, load_and_validate_spec, resolve_under  # noqa: E402
from mix_story_audio import (  # noqa: E402
    measure_loudness,
    validate_approval_aac_raw_decode,
    _probe_approval_m4a,
)


APPROVAL_REQUIRED_FIELDS = frozenset({
    "schema_version", "kind", "story_id", "revision", "state",
    "approved_at_utc", "approval_note", "approved_audio", "bound_hashes",
    "spec_path", "timeline_path", "report_path",
})
HANDOFF_REQUIRED_FIELDS = frozenset({
    "schema_version", "kind", "story_id", "revision", "state",
    "approved_audio", "timeline", "audio_processing_locked",
    "allowed_short_assembly_operations", "forbidden_operations",
    "approval_path", "approval_sha256",
})
EXACT_ALLOWED_OPS = frozenset({
    "video_concat",
    "video_encode",
    "audio_stream_copy_or_exact_mux",
    "container_faststart",
})
EXACT_FORBIDDEN_OPS = frozenset({
    "loudnorm",
    "denoise",
    "ducking",
    "stem_remix",
    "trim_changing_duration",
})
SOURCE_PADDING_REQUIRED = frozenset({
    "scene_id",
    "decoded_source_frames",
    "padded_tail_frames",
    "trimmed_codec_padding_frames",
    "decoded_source_rms",
})
STEM_FILE_KEYS = (
    ("rhythm", "rhythm_wav"),
    ("melody", "melody_wav"),
    ("full_score", "full_score_wav"),
)
SOURCE_MIX_FILE_KEYS = (
    ("source_mixed_wav", "source_mixed_wav"),
    ("source_mixed_approval_m4a", "source_mixed_approval_m4a"),
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def wav_frames(path: Path) -> int:
    with wave.open(str(path), "rb") as inp:
        return inp.getnframes()


def _load_report(validated: dict) -> dict | None:
    report_path = validated["resolved_paths"]["report_json"]
    if not report_path.is_file():
        return None
    return json.loads(report_path.read_text(encoding="utf-8"))


def verify_phase_artifacts(validated: dict) -> list[str]:
    errors: list[str] = []
    paths = validated["resolved_paths"]
    expected_frames = validated["timeline"]["exact_pcm_frames"]
    wav_keys = ("rhythm_wav", "melody_wav", "full_score_wav", "source_mixed_wav")
    for key in wav_keys:
        path = paths[key]
        if not path.is_file():
            errors.append(f"missing {key}: {path}")
            continue
        frames = wav_frames(path)
        if frames != expected_frames:
            errors.append(f"{key} frame mismatch: expected {expected_frames}, got {frames}")
    m4a_keys = ("rhythm_preview_m4a", "full_preview_m4a", "source_mixed_approval_m4a")
    for key in m4a_keys:
        if not paths[key].is_file():
            errors.append(f"missing {key}: {paths[key]}")
    report = _load_report(validated)
    if report is None:
        errors.append(f"missing report: {paths['report_json']}")
    elif report.get("kind") == "story_soundtrack_aggregate":
        phases = report.get("phases", {})
        if "stems" not in phases or "source_mix" not in phases:
            errors.append("aggregate report missing stems or source_mix phase")
    return errors


def _verify_report_file_hashes(
    validated: dict,
    files: dict,
    key_map: tuple[tuple[str, str], ...],
) -> list[str]:
    errors: list[str] = []
    paths = validated["resolved_paths"]
    for report_key, path_key in key_map:
        entry = files.get(report_key, {})
        expected = entry.get("sha256")
        path = paths[path_key]
        if not path.is_file():
            errors.append(f"missing {path_key} for aggregate hash check")
            continue
        if not expected:
            errors.append(f"missing required sha256 in aggregate report for {path_key}")
            continue
        if sha256_file(path) != expected:
            errors.append(f"aggregate report hash mismatch for {path_key}")
    return errors


def _verify_aggregate_report(validated: dict, report: dict) -> list[str]:
    errors: list[str] = []
    if report.get("kind") != "story_soundtrack_aggregate":
        errors.append("report must be aggregate after source mix")
        return errors
    if report.get("story_id") != validated["story_id"]:
        errors.append("aggregate report story_id mismatch")
    if int(report.get("revision", -1)) != validated["revision"]:
        errors.append("aggregate report revision mismatch")
    phases = report.get("phases", {})
    stems = phases.get("stems")
    source_mix = phases.get("source_mix")
    if not isinstance(stems, dict) or stems.get("kind") != "story_soundtrack_stems":
        errors.append("aggregate report missing valid stems phase")
    if not isinstance(source_mix, dict) or source_mix.get("kind") != "story_soundtrack_source_mix":
        errors.append("aggregate report missing valid source_mix phase")
    elif "source_padding" not in source_mix:
        errors.append("aggregate source_mix missing source_padding report")
    else:
        padding = source_mix.get("source_padding")
        if not isinstance(padding, list):
            errors.append("aggregate source_mix source_padding must be a list")
        else:
            for idx, entry in enumerate(padding):
                if not isinstance(entry, dict):
                    errors.append(f"aggregate source_padding[{idx}] must be an object")
                    continue
                missing = SOURCE_PADDING_REQUIRED - set(entry)
                if missing:
                    errors.append(
                        f"aggregate source_padding[{idx}] missing fields: "
                        f"{', '.join(sorted(missing))}"
                    )
    if isinstance(stems, dict):
        errors.extend(_verify_report_file_hashes(validated, stems.get("files", {}), STEM_FILE_KEYS))
    if isinstance(source_mix, dict):
        errors.extend(
            _verify_report_file_hashes(validated, source_mix.get("files", {}), SOURCE_MIX_FILE_KEYS)
        )
    phase_hashes = report.get("phase_hashes", {})
    if not phase_hashes.get("stems_sha256"):
        errors.append("aggregate report missing required phase_hashes.stems_sha256")
    if not phase_hashes.get("source_mix_sha256"):
        errors.append("aggregate report missing required phase_hashes.source_mix_sha256")
    if stems and phase_hashes.get("stems_sha256"):
        expected = hashlib.sha256(
            json.dumps(stems, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if phase_hashes["stems_sha256"] != expected:
            errors.append("aggregate stems phase hash mismatch")
    if source_mix and phase_hashes.get("source_mix_sha256"):
        expected = hashlib.sha256(
            json.dumps(source_mix, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if phase_hashes["source_mix_sha256"] != expected:
            errors.append("aggregate source_mix phase hash mismatch")
    return errors


def verify_approval_handoff(validated: dict) -> list[str]:
    errors: list[str] = []
    root = validated["root"]
    paths = validated["resolved_paths"]
    approval_path = paths["approval_json"]
    handoff_path = paths["handoff_json"]
    if not approval_path.is_file():
        errors.append("missing approval_json")
        return errors
    if not handoff_path.is_file():
        errors.append("missing handoff_json")
        return errors

    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))

    unknown_approval = set(approval) - APPROVAL_REQUIRED_FIELDS
    if unknown_approval:
        errors.append(f"approval has unknown fields: {', '.join(sorted(unknown_approval))}")
    missing_approval = APPROVAL_REQUIRED_FIELDS - set(approval)
    if missing_approval:
        errors.append(f"approval missing fields: {', '.join(sorted(missing_approval))}")

    unknown_handoff = set(handoff) - HANDOFF_REQUIRED_FIELDS
    if unknown_handoff:
        errors.append(f"handoff has unknown fields: {', '.join(sorted(unknown_handoff))}")
    missing_handoff = HANDOFF_REQUIRED_FIELDS - set(handoff)
    if missing_handoff:
        errors.append(f"handoff missing fields: {', '.join(sorted(missing_handoff))}")

    if approval.get("story_id") != validated["story_id"]:
        errors.append("approval story_id mismatch")
    if handoff.get("story_id") != validated["story_id"]:
        errors.append("handoff story_id mismatch")
    if int(approval.get("revision", -1)) != validated["revision"]:
        errors.append("approval revision mismatch")
    if int(handoff.get("revision", -1)) != validated["revision"]:
        errors.append("handoff revision mismatch")
    if approval.get("state") != "USER_APPROVED":
        errors.append("approval state must be USER_APPROVED")
    if handoff.get("state") != "HANDED_OFF_TO_SHORTS":
        errors.append("handoff state must be HANDED_OFF_TO_SHORTS")

    if handoff.get("approval_sha256") != sha256_file(approval_path):
        errors.append("handoff approval_sha256 mismatch")

    m4a_path = paths["source_mixed_approval_m4a"]
    actual_hash = sha256_file(m4a_path)
    approved_audio = approval.get("approved_audio", {})
    if approved_audio.get("sha256") != actual_hash:
        errors.append("approval audio hash mismatch with current M4A")
    if handoff.get("approved_audio", {}).get("sha256") != actual_hash:
        errors.append("handoff audio hash mismatch with current M4A")

    if approved_audio.get("exact_pcm_frames") != validated["timeline"]["exact_pcm_frames"]:
        errors.append("approval exact_pcm_frames mismatch")
    if approved_audio.get("sample_rate_hz") != validated["timeline"]["sample_rate_hz"]:
        errors.append("approval sample_rate_hz mismatch")
    if approved_audio.get("channels") != 2:
        errors.append("approval channels must be 2")

    spec_path = validated["spec_path"]
    timeline_path = resolve_under(root, validated["timeline"]["path"])
    bound = approval.get("bound_hashes", {})
    if bound.get("spec_sha256") != sha256_file(spec_path):
        errors.append("approval spec hash mismatch")
    if bound.get("timeline_sha256") != sha256_file(timeline_path):
        errors.append("approval timeline hash mismatch")
    report_path = paths["report_json"]
    if bound.get("report_sha256") != sha256_file(report_path):
        errors.append("approval report hash mismatch")
    if bound.get("source_mixed_wav_sha256") != sha256_file(paths["source_mixed_wav"]):
        errors.append("approval source_mixed_wav hash mismatch")

    report = _load_report(validated)
    if report is None:
        errors.append("missing aggregate report for approval verification")
    else:
        errors.extend(_verify_aggregate_report(validated, report))
        if report.get("kind") == "story_soundtrack_aggregate":
            phase_hashes = report.get("phase_hashes", {})
            if bound.get("stems_phase_sha256") != phase_hashes.get("stems_sha256"):
                errors.append("approval stems phase hash mismatch")
            if bound.get("source_mix_phase_sha256") != phase_hashes.get("source_mix_sha256"):
                errors.append("approval source_mix phase hash mismatch")

    handoff_timeline = handoff.get("timeline", {})
    if handoff_timeline.get("total_frames") != validated["timeline"]["total_frames"]:
        errors.append("handoff timeline total_frames mismatch")
    if float(handoff_timeline.get("fps", -1)) != validated["timeline"]["fps"]:
        errors.append("handoff timeline fps mismatch")
    if handoff_timeline.get("sha256") != sha256_file(timeline_path):
        errors.append("handoff timeline hash mismatch")

    if not handoff.get("audio_processing_locked"):
        errors.append("handoff audio_processing_locked must be true")

    allowed = set(handoff.get("allowed_short_assembly_operations", []))
    if allowed != EXACT_ALLOWED_OPS:
        errors.append("handoff allowed_short_assembly_operations must match exact contract set")
    forbidden = set(handoff.get("forbidden_operations", []))
    if forbidden != EXACT_FORBIDDEN_OPS:
        errors.append("handoff forbidden_operations must match exact contract set")

    sr = validated["timeline"]["sample_rate_hz"]
    expected_frames = validated["timeline"]["exact_pcm_frames"]
    qa = validated["qa"]
    try:
        probe_meta = _probe_approval_m4a(m4a_path, expected_frames, sr)
        if abs(
            probe_meta["probe_duration_seconds"] - probe_meta["expected_duration_seconds"]
        ) > qa["duration_tolerance_seconds"]:
            errors.append("approval M4A duration out of tolerance")
        validate_approval_aac_raw_decode(m4a_path, expected_frames, sr)
        loudness = measure_loudness(m4a_path)
        lufs = loudness["integrated_lufs"]
        true_peak = loudness["true_peak_dbfs"]
        lufs_min = qa["final_lufs_min"] - qa["encoded_lufs_tolerance_db"]
        lufs_max = qa["final_lufs_max"] + qa["encoded_lufs_tolerance_db"]
        peak_ceiling = qa["final_true_peak_dbfs"] + qa["encoded_true_peak_tolerance_db"]
        if not (lufs_min <= lufs <= lufs_max):
            errors.append(
                f"approval M4A LUFS {lufs:.2f} outside tolerant range "
                f"[{lufs_min:.2f}, {lufs_max:.2f}]"
            )
        if true_peak > peak_ceiling:
            errors.append(
                f"approval M4A true peak {true_peak:.2f} exceeds tolerant ceiling {peak_ceiling:.2f}"
            )
    except (RuntimeError, ValueError) as exc:
        errors.append(f"approval M4A QA failed: {exc}")

    return errors


def verify(validated: dict, require_approved_handoff: bool = False) -> dict:
    errors = verify_phase_artifacts(validated)
    report = _load_report(validated)
    paths = validated["resolved_paths"]
    if not require_approved_handoff:
        if (
            report is not None
            and report.get("kind") == "story_soundtrack_aggregate"
            and paths["source_mixed_wav"].is_file()
        ):
            errors.extend(_verify_aggregate_report(validated, report))
            m4a_path = paths["source_mixed_approval_m4a"]
            if m4a_path.is_file():
                sr = validated["timeline"]["sample_rate_hz"]
                expected_frames = validated["timeline"]["exact_pcm_frames"]
                qa = validated["qa"]
                try:
                    probe_meta = _probe_approval_m4a(m4a_path, expected_frames, sr)
                    if abs(
                        probe_meta["probe_duration_seconds"] - probe_meta["expected_duration_seconds"]
                    ) > qa["duration_tolerance_seconds"]:
                        errors.append("approval M4A duration out of tolerance")
                    validate_approval_aac_raw_decode(m4a_path, expected_frames, sr)
                except (RuntimeError, ValueError) as exc:
                    errors.append(f"approval M4A QA failed: {exc}")
    if require_approved_handoff:
        errors.extend(verify_approval_handoff(validated))
    return {"ok": not errors, "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--require-approved-handoff", action="store_true")
    args = ap.parse_args()
    try:
        validated = load_and_validate_spec(args.root.resolve(), args.spec.resolve())
        result = verify(validated, require_approved_handoff=args.require_approved_handoff)
    except ContractError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
