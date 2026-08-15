#!/usr/bin/env python3
"""Record explicit user approval and create hash-bound handoff manifest."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from story_soundtrack_contract import ContractError, load_and_validate_spec, resolve_under  # noqa: E402
from verify_story_soundtrack import _verify_aggregate_report  # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write_synced(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _replace_transaction_file(source: Path, destination: Path) -> None:
    source.replace(destination)


def _transaction_paths(approval_path: Path, handoff_path: Path) -> tuple[Path, Path, Path]:
    approval_temp = approval_path.with_name(f".{approval_path.name}.transaction.tmp")
    handoff_temp = handoff_path.with_name(f".{handoff_path.name}.transaction.tmp")
    marker = approval_path.with_name(f".{approval_path.name}.transaction.json")
    return approval_temp, handoff_temp, marker


def _recover_approval_transaction(approval_path: Path, handoff_path: Path) -> bool:
    approval_temp, handoff_temp, marker = _transaction_paths(approval_path, handoff_path)
    if not marker.is_file():
        return False
    transaction = json.loads(marker.read_text(encoding="utf-8"))
    if transaction.get("schema_version") != 1:
        raise SystemExit("invalid approval transaction marker")
    items = (
        (approval_temp, approval_path, transaction.get("approval_sha256")),
        (handoff_temp, handoff_path, transaction.get("handoff_sha256")),
    )
    for temp, final, expected in items:
        if not isinstance(expected, str) or len(expected) != 64:
            raise SystemExit("invalid approval transaction hash")
        if final.is_file():
            if sha256_file(final) != expected:
                raise SystemExit(f"approval transaction final hash mismatch: {final}")
            continue
        if not temp.is_file() or sha256_file(temp) != expected:
            raise SystemExit(f"approval transaction cannot recover missing artifact: {final}")
        final.parent.mkdir(parents=True, exist_ok=True)
        _replace_transaction_file(temp, final)
        _fsync_directory(final.parent)
    marker.unlink()
    _fsync_directory(marker.parent)
    approval_temp.unlink(missing_ok=True)
    handoff_temp.unlink(missing_ok=True)
    return True


def _commit_approval_transaction(
    approval_path: Path,
    approval_bytes: bytes,
    handoff_path: Path,
    handoff_bytes: bytes,
) -> None:
    approval_temp, handoff_temp, marker = _transaction_paths(approval_path, handoff_path)
    marker_temp = marker.with_name(f".{marker.name}.tmp")
    marker_written = False
    try:
        _write_synced(approval_temp, approval_bytes)
        _write_synced(handoff_temp, handoff_bytes)
        _fsync_directory(approval_temp.parent)
        if handoff_temp.parent != approval_temp.parent:
            _fsync_directory(handoff_temp.parent)
        transaction = {
            "schema_version": 1,
            "approval_sha256": hashlib.sha256(approval_bytes).hexdigest(),
            "handoff_sha256": hashlib.sha256(handoff_bytes).hexdigest(),
        }
        _write_synced(marker_temp, _json_bytes(transaction))
        marker_temp.replace(marker)
        _fsync_directory(marker.parent)
        marker_written = True
        _recover_approval_transaction(approval_path, handoff_path)
    finally:
        marker_temp.unlink(missing_ok=True)
        if not marker_written:
            approval_temp.unlink(missing_ok=True)
            handoff_temp.unlink(missing_ok=True)


@contextmanager
def _approval_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _load_aggregate_report(report_path: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("kind") != "story_soundtrack_aggregate":
        raise SystemExit("approval requires aggregate report with stems and source_mix phases")
    if report.get("state") != "SOURCE_MIX_REVIEW":
        raise SystemExit(f"approval requires SOURCE_MIX_REVIEW report, got {report.get('state')}")
    phases = report.get("phases", {})
    stems = phases.get("stems")
    source_mix = phases.get("source_mix")
    if not isinstance(stems, dict) or not isinstance(source_mix, dict):
        raise SystemExit("aggregate report missing stems or source_mix phase")
    return report


def _verify_aggregate_hashes(validated: dict, aggregate: dict) -> None:
    paths = validated["resolved_paths"]
    stems = aggregate["phases"]["stems"]
    source_mix = aggregate["phases"]["source_mix"]
    file_map = {
        "rhythm": "rhythm_wav",
        "melody": "melody_wav",
        "full_score": "full_score_wav",
    }
    for report_key, path_key in file_map.items():
        entry = stems.get("files", {}).get(report_key, {})
        expected = entry.get("sha256")
        actual_path = paths[path_key]
        if not actual_path.is_file():
            raise SystemExit(f"missing stem artifact for approval: {path_key}")
        if not expected:
            raise SystemExit(f"missing required sha256 in aggregate stems report for {path_key}")
        if sha256_file(actual_path) != expected:
            raise SystemExit(f"aggregate stems hash mismatch for {path_key}")
    for report_key, path_key in (
        ("source_mixed_wav", "source_mixed_wav"),
        ("source_mixed_approval_m4a", "source_mixed_approval_m4a"),
    ):
        entry = source_mix.get("files", {}).get(report_key, {})
        expected = entry.get("sha256")
        actual_path = paths[path_key]
        if not actual_path.is_file():
            raise SystemExit(f"missing source mix artifact for approval: {path_key}")
        if not expected:
            raise SystemExit(f"missing required sha256 in aggregate source_mix report for {path_key}")
        if sha256_file(actual_path) != expected:
            raise SystemExit(f"aggregate source_mix hash mismatch for {path_key}")


def approve_soundtrack(
    validated: dict,
    approval_note: str,
) -> dict:
    paths = validated["resolved_paths"]
    approval_path = paths["approval_json"]
    handoff_path = paths["handoff_json"]
    lock_path = approval_path.with_name(f".{approval_path.name}.lock")
    with _approval_lock(lock_path):
        if _recover_approval_transaction(approval_path, handoff_path):
            return {
                "approval": json.loads(approval_path.read_text(encoding="utf-8")),
                "handoff": json.loads(handoff_path.read_text(encoding="utf-8")),
            }
        return _approve_soundtrack_locked(validated, approval_note)


def _approve_soundtrack_locked(
    validated: dict,
    approval_note: str,
) -> dict:
    root = validated["root"]
    paths = validated["resolved_paths"]
    approval_path = paths["approval_json"]
    handoff_path = paths["handoff_json"]
    if approval_path.exists() or handoff_path.exists():
        raise SystemExit("refusing to overwrite existing approval/handoff artifacts")

    m4a_path = paths["source_mixed_approval_m4a"]
    report_path = paths["report_json"]
    spec_path = validated["spec_path"]
    timeline_path = resolve_under(root, validated["timeline"]["path"])
    for required in (m4a_path, report_path, spec_path, timeline_path):
        if not required.is_file():
            raise SystemExit(f"missing required artifact: {required}")

    aggregate = _load_aggregate_report(report_path)
    aggregate_errors = _verify_aggregate_report(validated, aggregate)
    if aggregate_errors:
        raise SystemExit("aggregate validation failed: " + "; ".join(aggregate_errors))
    _verify_aggregate_hashes(validated, aggregate)

    approved_audio_hash = sha256_file(m4a_path)
    approval = {
        "schema_version": 1,
        "kind": "story_soundtrack_approval",
        "story_id": validated["story_id"],
        "revision": validated["revision"],
        "state": "USER_APPROVED",
        "approved_at_utc": datetime.now(timezone.utc).isoformat(),
        "approval_note": approval_note,
        "approved_audio": {
            "path": str(m4a_path.relative_to(root)),
            "sha256": approved_audio_hash,
            "exact_pcm_frames": validated["timeline"]["exact_pcm_frames"],
            "sample_rate_hz": validated["timeline"]["sample_rate_hz"],
            "channels": 2,
            "duration_seconds": validated["timeline"]["exact_duration_seconds"],
        },
        "bound_hashes": {
            "spec_sha256": sha256_file(spec_path),
            "timeline_sha256": sha256_file(timeline_path),
            "report_sha256": sha256_file(report_path),
            "source_mixed_wav_sha256": sha256_file(paths["source_mixed_wav"]),
            "stems_phase_sha256": aggregate["phase_hashes"]["stems_sha256"],
            "source_mix_phase_sha256": aggregate["phase_hashes"]["source_mix_sha256"],
        },
        "spec_path": str(spec_path.relative_to(root)),
        "timeline_path": validated["timeline"]["path"],
        "report_path": validated["outputs"]["report_json"],
    }
    approval_bytes = _json_bytes(approval)

    handoff = {
        "schema_version": 1,
        "kind": "story_soundtrack_handoff",
        "story_id": validated["story_id"],
        "revision": validated["revision"],
        "state": "HANDED_OFF_TO_SHORTS",
        "approved_audio": approval["approved_audio"],
        "timeline": {
            "path": validated["timeline"]["path"],
            "sha256": approval["bound_hashes"]["timeline_sha256"],
            "total_frames": validated["timeline"]["total_frames"],
            "fps": validated["timeline"]["fps"],
        },
        "audio_processing_locked": True,
        "allowed_short_assembly_operations": [
            "video_concat",
            "video_encode",
            "audio_stream_copy_or_exact_mux",
            "container_faststart",
        ],
        "forbidden_operations": [
            "loudnorm",
            "denoise",
            "ducking",
            "stem_remix",
            "trim_changing_duration",
        ],
        "approval_path": str(approval_path.relative_to(root)),
        "approval_sha256": hashlib.sha256(approval_bytes).hexdigest(),
    }
    handoff_bytes = _json_bytes(handoff)
    _commit_approval_transaction(approval_path, approval_bytes, handoff_path, handoff_bytes)
    return {"approval": approval, "handoff": handoff}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--approval-note", required=True)
    args = ap.parse_args()
    try:
        validated = load_and_validate_spec(args.root.resolve(), args.spec.resolve())
        result = approve_soundtrack(validated, args.approval_note)
    except ContractError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({
        "status": "ok",
        "approval": validated["outputs"]["approval_json"],
        "handoff": validated["outputs"]["handoff_json"],
        "approved_audio_sha256": result["approval"]["approved_audio"]["sha256"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
