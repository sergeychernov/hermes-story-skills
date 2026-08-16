#!/usr/bin/env python3
"""Mix generated stems with scene source audio into approval master."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from story_soundtrack_contract import (  # noqa: E402
    ContractError,
    load_and_validate_spec,
    load_timeline,
    resolve_under,
    validate_timeline_agreement,
)
from story_soundtrack_lock import revision_lock  # noqa: E402

MEDIA_SUFFIXES = {".wav", ".m4a", ".mp4", ".aac", ".mov", ".mkv"}
CODEC_PADDING_MAX_SAMPLES = 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_pcm16_stereo(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as inp:
        if inp.getnchannels() != 2 or inp.getsampwidth() != 2 or inp.getframerate() != 48000:
            raise ValueError(f"expected PCM16 stereo 48kHz: {path}")
        frames = inp.getnframes()
        data = np.frombuffer(inp.readframes(frames), dtype="<i2").reshape(-1, 2).astype(np.float64) / 32767.0
        return data, inp.getframerate()


def write_pcm16(path: Path, audio: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.round(audio * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(sr)
        out.writeframes(pcm.tobytes())


def ffprobe_json(path: Path) -> dict:
    cmd = [
        "ffprobe", "-hide_banner", "-v", "error",
        "-show_format", "-show_streams",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr}")
    return json.loads(result.stdout)


def has_audio_stream(probe: dict) -> bool:
    return any(stream.get("codec_type") == "audio" for stream in probe.get("streams", []))


def decode_media_to_pcm(path: Path, length: int, sr: int = 48000) -> np.ndarray:
    pcm, _meta = decode_source_for_scene(path, length, sr)
    return pcm


def decode_aac_raw_full(path: Path, sr: int = 48000) -> np.ndarray:
    """Decode an entire AAC stream to PCM without apad/atrim scene padding."""
    suffix = path.suffix.lower()
    if suffix not in MEDIA_SUFFIXES:
        raise ValueError(f"unsupported AAC container format: {path}")
    probe = ffprobe_json(path)
    if not has_audio_stream(probe):
        raise ValueError(f"media has no audio stream: {path}")
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-v", "error",
        "-i", str(path),
        "-af", f"aresample={sr}",
        "-ac", "2", "-ar", str(sr),
        "-f", "f32le", "-acodec", "pcm_f32le",
        "pipe:1",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg decode failed for {path}: {result.stderr.decode('utf-8', 'replace')}")
    if len(result.stdout) == 0:
        raise RuntimeError(f"decoded audio empty for {path}")
    sample_count = len(result.stdout) // (2 * 4)
    return np.frombuffer(result.stdout, dtype="<f4").reshape(-1, 2).astype(np.float64)


def validate_approval_aac_raw_decode(path: Path, expected_frames: int, sr: int = 48000) -> dict:
    raw = decode_aac_raw_full(path, sr)
    raw_count = len(raw)
    if raw_count < expected_frames:
        raise RuntimeError(
            f"approval AAC raw decode too short: {raw_count} frames, expected at least {expected_frames}"
        )
    tail_padding = raw_count - expected_frames
    if tail_padding > CODEC_PADDING_MAX_SAMPLES:
        raise RuntimeError(
            f"approval AAC codec tail padding {tail_padding} frames exceeds max {CODEC_PADDING_MAX_SAMPLES}"
        )
    return {
        "raw_decoded_frames": raw_count,
        "codec_tail_padding_frames": tail_padding,
        "expected_pcm_frames": expected_frames,
    }


def decode_source_for_scene(path: Path, scene_length: int, sr: int = 48000) -> tuple[np.ndarray, dict]:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        data, file_sr = read_pcm16_stereo(path)
        if file_sr != sr:
            raise ValueError(f"expected {sr} Hz WAV: {path}")
        decoded_len = len(data)
    elif suffix in MEDIA_SUFFIXES:
        probe = ffprobe_json(path)
        if not has_audio_stream(probe):
            raise ValueError(f"source media has no audio stream: {path}")
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-v", "error",
            "-i", str(path),
            "-af", f"aresample={sr}",
            "-ac", "2", "-ar", str(sr),
            "-f", "f32le", "-acodec", "pcm_f32le",
            "pipe:1",
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg decode failed for {path}: {result.stderr.decode('utf-8', 'replace')}")
        if len(result.stdout) == 0:
            raise RuntimeError(f"decoded audio empty for {path}")
        sample_count = len(result.stdout) // (2 * 4)
        data = np.frombuffer(result.stdout, dtype="<f4").reshape(-1, 2).astype(np.float64)
        decoded_len = sample_count
    else:
        raise ValueError(f"unsupported source audio format: {path}")

    if decoded_len > scene_length:
        excess = decoded_len - scene_length
        if excess > CODEC_PADDING_MAX_SAMPLES:
            raise ValueError(
                f"source longer than scene for {path}: decoded {decoded_len} frames, "
                f"scene allows {scene_length} (+{CODEC_PADDING_MAX_SAMPLES} codec padding max)"
            )
        pcm = data[:scene_length]
        meta = {
            "decoded_source_frames": decoded_len,
            "padded_tail_frames": 0,
            "trimmed_codec_padding_frames": excess,
        }
        return pcm, meta

    if decoded_len < scene_length:
        pcm = np.zeros((scene_length, 2), dtype=np.float64)
        pcm[:decoded_len] = data
        meta = {
            "decoded_source_frames": decoded_len,
            "padded_tail_frames": scene_length - decoded_len,
            "trimmed_codec_padding_frames": 0,
        }
        return pcm, meta

    meta = {
        "decoded_source_frames": decoded_len,
        "padded_tail_frames": 0,
        "trimmed_codec_padding_frames": 0,
    }
    return data, meta


def measure_loudness(path: Path) -> dict[str, float]:
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "info",
        "-i", str(path),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"loudness measurement failed: {result.stderr}")
    match = re.search(r"\{[\s\S]*?\}", result.stderr)
    if not match:
        raise RuntimeError("loudness measurement produced no JSON")
    payload = json.loads(match.group(0))
    return {
        "integrated_lufs": float(payload["input_i"]),
        "true_peak_dbfs": float(payload["input_tp"]),
    }


def decode_m4a_to_pcm(path: Path, expected_frames: int, sr: int = 48000) -> np.ndarray:
    raw_meta = validate_approval_aac_raw_decode(path, expected_frames, sr)
    raw = decode_aac_raw_full(path, sr)
    return raw[:expected_frames]


def smooth_envelope(length: int, sr: int, transition_ms: int, gains: list[tuple[int, int, float]]) -> np.ndarray:
    env = np.zeros(length, dtype=np.float64)
    trans = max(1, int(round(transition_ms / 1000.0 * sr)))
    for start, end, gain in gains:
        env[start:end] = gain
    smoothed = env.copy()
    for i in range(1, length):
        if env[i] != env[i - 1]:
            ramp_start = max(0, i - trans)
            ramp_end = min(length, i + trans)
            left = env[i - 1]
            right = env[i]
            span = ramp_end - ramp_start
            if span > 0:
                ramp = np.linspace(left, right, span, endpoint=False)
                smoothed[ramp_start:ramp_end] = ramp
    return smoothed


def build_gain_envelope(validated: dict, gain_key: str) -> np.ndarray:
    sr = validated["timeline"]["sample_rate_hz"]
    fps = validated["timeline"]["fps"]
    total = validated["timeline"]["exact_pcm_frames"]
    segments: list[tuple[int, int, float]] = []
    for scene in validated["scenes"]:
        start_frame = int(round(scene["frames"][0] * sr / fps))
        end_frame = int(round(scene["frames"][1] * sr / fps))
        gain = float(scene["routing"][gain_key])
        segments.append((start_frame, end_frame, gain))
    return smooth_envelope(total, sr, validated["qa"]["transition_ms"], segments)


def build_source_timeline(validated: dict, root: Path) -> tuple[np.ndarray, list[dict]]:
    sr = validated["timeline"]["sample_rate_hz"]
    fps = validated["timeline"]["fps"]
    total = validated["timeline"]["exact_pcm_frames"]
    out = np.zeros((total, 2), dtype=np.float64)
    padding_report: list[dict] = []
    fade = max(1, int(round(0.025 * sr)))
    for scene in validated["scenes"]:
        start = int(round(scene["frames"][0] * sr / fps))
        end = int(round(scene["frames"][1] * sr / fps))
        length = end - start
        entry = {
            "scene_id": scene["id"],
            "audio_class": scene["audio_class"],
            "decoded_source_frames": 0,
            "padded_tail_frames": 0,
            "trimmed_codec_padding_frames": 0,
            "decoded_source_rms": 0.0,
        }
        if scene["audio_class"] == "silent":
            padding_report.append(entry)
            continue
        src_path = resolve_under(root, scene["source_audio"])
        src, meta = decode_source_for_scene(src_path, length, sr)
        entry.update(meta)
        entry["decoded_source_rms"] = float(np.sqrt(np.mean(np.square(src))))
        gain = float(scene["routing"]["source_gain"])
        src *= gain
        if fade > 0 and len(src) > fade * 2:
            src[:fade] *= np.linspace(0.0, 1.0, fade)[:, None]
            src[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
        out[start:end] += src
        padding_report.append(entry)
    return out, padding_report


def _load_stems_report(validated: dict) -> dict:
    report_path = validated["resolved_paths"]["report_json"]
    if not report_path.is_file():
        raise SystemExit("STEMS_RENDERED report_json must exist before mixing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    kind = report.get("kind")
    if kind == "story_soundtrack_aggregate":
        phases = report.get("phases", {})
        if not isinstance(phases, dict):
            raise SystemExit("aggregate report phases must be an object")
        stems = phases.get("stems")
        if not isinstance(stems, dict):
            raise SystemExit("aggregate report missing stems phase")
        report = stems
        kind = report.get("kind")
    if kind != "story_soundtrack_stems":
        raise SystemExit(f"expected STEMS_RENDERED stems report, got kind={kind}")
    if report.get("state") != "STEMS_RENDERED":
        raise SystemExit(f"report state must be STEMS_RENDERED, got {report.get('state')}")
    if report.get("story_id") != validated["story_id"]:
        raise SystemExit("stems phase story_id mismatch")
    if int(report.get("revision", -1)) != validated["revision"]:
        raise SystemExit("stems phase revision mismatch")
    if int(report.get("exact_pcm_frames", -1)) != validated["timeline"]["exact_pcm_frames"]:
        raise SystemExit("stems phase exact_pcm_frames mismatch")
    if int(report.get("sample_rate_hz", -1)) != validated["timeline"]["sample_rate_hz"]:
        raise SystemExit("stems phase sample_rate_hz mismatch")
    if int(report.get("channels", -1)) != 2:
        raise SystemExit("stems phase channels mismatch")
    return report


def _validate_stem_artifacts(validated: dict, stems_report: dict) -> None:
    paths = validated["resolved_paths"]
    expected_frames = validated["timeline"]["exact_pcm_frames"]
    file_map = {
        "rhythm_wav": "rhythm",
        "melody_wav": "melody",
        "full_score_wav": "full_score",
    }
    for path_key, report_key in file_map.items():
        path = paths[path_key]
        if not path.is_file():
            raise SystemExit(f"missing stem artifact before mix: {path_key}")
        with wave.open(str(path), "rb") as inp:
            if inp.getnframes() != expected_frames:
                raise SystemExit(f"{path_key} frame count mismatch with timeline")
        entry = stems_report.get("files", {}).get(report_key, {})
        expected_path = str(path.relative_to(validated["root"]))
        if entry.get("path") != expected_path:
            raise SystemExit(f"stem path mismatch for {path_key}")
        expected_hash = entry.get("sha256")
        if not expected_hash:
            raise SystemExit(f"missing required sha256 in stems report for {path_key}")
        if sha256_file(path) != expected_hash:
            raise SystemExit(f"stem hash mismatch for {path_key}")


def _probe_approval_m4a(path: Path, expected_frames: int, sr: int) -> dict:
    probe = ffprobe_json(path)
    if path.stat().st_size <= 0:
        raise RuntimeError(f"approval M4A is empty: {path}")
    audio_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]
    if len(audio_streams) != 1:
        raise RuntimeError(f"approval M4A must have exactly one audio stream: {path}")
    stream = audio_streams[0]
    if stream.get("codec_name") != "aac":
        raise RuntimeError(f"approval M4A must be AAC: {path}")
    channels = int(stream.get("channels", 0))
    sample_rate = int(stream.get("sample_rate", 0))
    if channels != 2 or sample_rate != sr:
        raise RuntimeError(f"approval M4A must be stereo {sr} Hz: {path}")
    duration = float(probe.get("format", {}).get("duration", 0.0))
    expected_duration = expected_frames / sr
    return {
        "codec": stream.get("codec_name"),
        "channels": channels,
        "sample_rate_hz": sample_rate,
        "probe_duration_seconds": duration,
        "expected_duration_seconds": expected_duration,
    }


def _qa_check_encoded_master(
    wav_path: Path,
    m4a_path: Path,
    validated: dict,
    expected_frames: int,
    sr: int,
) -> dict:
    qa = validated["qa"]
    tolerance = qa["duration_tolerance_seconds"]
    probe_meta = _probe_approval_m4a(m4a_path, expected_frames, sr)
    if abs(probe_meta["probe_duration_seconds"] - probe_meta["expected_duration_seconds"]) > tolerance:
        raise RuntimeError(
            "approval M4A duration out of tolerance: "
            f"{probe_meta['probe_duration_seconds']:.6f}s vs "
            f"{probe_meta['expected_duration_seconds']:.6f}s"
        )

    raw_meta = validate_approval_aac_raw_decode(m4a_path, expected_frames, sr)
    decoded = decode_aac_raw_full(m4a_path, sr)[:expected_frames]
    wav_pcm, _ = read_pcm16_stereo(wav_path)
    if len(decoded) != len(wav_pcm):
        raise RuntimeError("decoded M4A frame count mismatch with source_mixed WAV")

    loudness = measure_loudness(m4a_path)
    lufs = loudness["integrated_lufs"]
    true_peak = loudness["true_peak_dbfs"]
    lufs_min = qa["final_lufs_min"] - qa["encoded_lufs_tolerance_db"]
    lufs_max = qa["final_lufs_max"] + qa["encoded_lufs_tolerance_db"]
    peak_ceiling = qa["final_true_peak_dbfs"] + qa["encoded_true_peak_tolerance_db"]
    if not (lufs_min <= lufs <= lufs_max):
        raise RuntimeError(
            f"encoded LUFS {lufs:.2f} outside [{lufs_min:.2f}, {lufs_max:.2f}] "
            f"(contract [{qa['final_lufs_min']}, {qa['final_lufs_max']}], "
            f"encoded_lufs_tolerance_db {qa['encoded_lufs_tolerance_db']})"
        )
    if true_peak > peak_ceiling:
        raise RuntimeError(
            f"encoded true peak {true_peak:.2f} dBFS exceeds ceiling {peak_ceiling:.2f} "
            f"(contract {qa['final_true_peak_dbfs']}, "
            f"encoded_true_peak_tolerance_db {qa['encoded_true_peak_tolerance_db']})"
        )

    return {
        **probe_meta,
        **raw_meta,
        "decoded_frames": len(decoded),
        "source_mixed_wav_frames": len(wav_pcm),
        "encoded_lufs": lufs,
        "encoded_true_peak_dbfs": true_peak,
        "encoded_lufs_tolerance_db": qa["encoded_lufs_tolerance_db"],
        "encoded_true_peak_tolerance_db": qa["encoded_true_peak_tolerance_db"],
        "qa_contract": {
            "final_lufs_min": qa["final_lufs_min"],
            "final_lufs_max": qa["final_lufs_max"],
            "final_true_peak_dbfs": qa["final_true_peak_dbfs"],
        },
        "source_of_truth": str(wav_path.name),
    }


def _refuse_if_approval_locked(validated: dict) -> None:
    paths = validated["resolved_paths"]
    if paths["approval_json"].exists() or paths["handoff_json"].exists():
        raise SystemExit(
            "refusing overwrite: approval_json or handoff_json exists; create a new revision"
        )


def _stems_report_only(validated: dict) -> bool:
    report_path = validated["resolved_paths"]["report_json"]
    if not report_path.is_file():
        return False
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return (
        report.get("kind") == "story_soundtrack_stems"
        and report.get("state") == "STEMS_RENDERED"
    )


def _refuse_mix_overwrite_without_flag(validated: dict, overwrite: bool) -> None:
    paths = validated["resolved_paths"]
    mix_artifacts = (
        paths["source_mixed_wav"],
        paths["source_mixed_approval_m4a"],
    )
    existing_mix = [str(p) for p in mix_artifacts if p.exists()]
    if existing_mix and not overwrite:
        raise SystemExit("refusing to overwrite existing outputs: " + ", ".join(existing_mix))

    report_path = paths["report_json"]
    if not report_path.is_file() or overwrite:
        return
    if _stems_report_only(validated):
        return
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise SystemExit(f"refusing to overwrite invalid report_json: {report_path}") from None
    if report.get("kind") == "story_soundtrack_aggregate":
        raise SystemExit(
            "refusing to overwrite existing aggregate report_json without --overwrite: "
            + str(report_path)
        )
    raise SystemExit("refusing to overwrite existing report_json without --overwrite: " + str(report_path))


def mix_audio(validated: dict, overwrite: bool = False) -> dict:
    with revision_lock(validated):
        return _mix_audio_locked(validated, overwrite)


def _mix_audio_locked(validated: dict, overwrite: bool = False) -> dict:
    _refuse_if_approval_locked(validated)
    _refuse_mix_overwrite_without_flag(validated, overwrite)
    root = validated["root"]
    paths = validated["resolved_paths"]

    timeline = load_timeline(root, validated["timeline"]["path"])
    try:
        validate_timeline_agreement(validated, timeline)
    except ContractError as exc:
        raise SystemExit(str(exc)) from exc

    stems_report = _load_stems_report(validated)
    _validate_stem_artifacts(validated, stems_report)

    rhythm_path = paths["rhythm_wav"]
    melody_path = paths["melody_wav"]
    if not rhythm_path.is_file() or not melody_path.is_file():
        raise SystemExit("rhythm and melody WAV stems must exist before mixing")

    sr = validated["timeline"]["sample_rate_hz"]
    total = validated["timeline"]["exact_pcm_frames"]
    rhythm, _ = read_pcm16_stereo(rhythm_path)
    melody, _ = read_pcm16_stereo(melody_path)
    if len(rhythm) != total or len(melody) != total:
        raise SystemExit("stem frame count mismatch with timeline")

    rhythm_env = build_gain_envelope(validated, "rhythm_gain")[:, None]
    melody_env = build_gain_envelope(validated, "melody_gain")[:, None]
    source, source_padding = build_source_timeline(validated, root)
    mixed = source + rhythm * rhythm_env + melody * melody_env

    peak = float(np.max(np.abs(mixed)))
    ceiling = 10 ** (validated["qa"]["final_true_peak_dbfs"] / 20.0)
    if peak > ceiling and peak > 0:
        mixed *= ceiling / peak

    write_pcm16(paths["source_mixed_wav"], mixed, sr)

    temp = paths["source_mixed_approval_m4a"].with_suffix(".tmp.m4a")
    if temp.exists():
        temp.unlink()
    duration = total / sr
    qa = validated["qa"]
    target_lufs = (qa["final_lufs_min"] + qa["final_lufs_max"]) / 2.0
    filter_chain = (
        f"loudnorm=I={target_lufs}:TP={qa['final_true_peak_dbfs']}:LRA=11,"
        "alimiter=level=false,aresample=48000,asetpts=PTS-STARTPTS"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostats",
        "-i", str(paths["source_mixed_wav"]),
        "-af", filter_chain,
        "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "192k",
        "-t", f"{duration:.9f}",
        "-movflags", "+faststart",
        str(temp),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("ffmpeg encode failed: " + result.stderr)
    temp.replace(paths["source_mixed_approval_m4a"])

    qa_report = _qa_check_encoded_master(
        paths["source_mixed_wav"],
        paths["source_mixed_approval_m4a"],
        validated,
        total,
        sr,
    )

    routing_report = []
    fps = validated["timeline"]["fps"]
    for scene in validated["scenes"]:
        s0, s1 = scene["frames"]
        mid = int(round(((s0 + s1) / 2.0) * sr / fps))
        routing_report.append({
            "scene_id": scene["id"],
            "audio_class": scene["audio_class"],
            "routing": scene["routing"],
            "midpoint_rhythm_rms": float(np.sqrt(np.mean(np.square(rhythm[mid - sr // 20:mid + sr // 20] * rhythm_env[mid])))),
            "midpoint_melody_rms": float(np.sqrt(np.mean(np.square(melody[mid - sr // 20:mid + sr // 20] * melody_env[mid])))),
            "midpoint_source_rms": float(np.sqrt(np.mean(np.square(source[mid - sr // 20:mid + sr // 20])))),
        })

    source_mix_report = {
        "schema_version": 1,
        "kind": "story_soundtrack_source_mix",
        "state": "SOURCE_MIX_REVIEW",
        "story_id": validated["story_id"],
        "revision": validated["revision"],
        "implementation_sha256": sha256_file(Path(__file__).resolve()),
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "ffmpeg_version": subprocess.run(
            ["ffmpeg", "-version"], text=True, capture_output=True
        ).stdout.splitlines()[0],
        "exact_pcm_frames": total,
        "sample_rate_hz": sr,
        "channels": 2,
        "mixing": {
            "combine_method": "numpy_sum",
            "automatic_normalization": False,
            "semantic_normalize": False,
            "limiter_level_false": True,
            "automatic_ducking": False,
            "stem_restart": False,
            "shortest_truncation": False,
        },
        "source_padding": source_padding,
        "routing_windows": routing_report,
        "qa": qa_report,
        "files": {
            "source_mixed_wav": {
                "path": str(paths["source_mixed_wav"].relative_to(root)),
                "sha256": sha256_file(paths["source_mixed_wav"]),
            },
            "source_mixed_approval_m4a": {
                "path": str(paths["source_mixed_approval_m4a"].relative_to(root)),
                "sha256": sha256_file(paths["source_mixed_approval_m4a"]),
            },
        },
    }

    aggregate = {
        "schema_version": 1,
        "kind": "story_soundtrack_aggregate",
        "state": "SOURCE_MIX_REVIEW",
        "story_id": validated["story_id"],
        "revision": validated["revision"],
        "phases": {
            "stems": stems_report,
            "source_mix": source_mix_report,
        },
        "files": {
            "stems": stems_report.get("files", {}),
            "source_mix": source_mix_report["files"],
        },
        "phase_hashes": {
            "stems_sha256": hashlib.sha256(
                json.dumps(stems_report, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "source_mix_sha256": hashlib.sha256(
                json.dumps(source_mix_report, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        },
    }
    paths["report_json"].parent.mkdir(parents=True, exist_ok=True)
    paths["report_json"].write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return aggregate


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    try:
        validated = load_and_validate_spec(args.root.resolve(), args.spec.resolve())
        report = mix_audio(validated, overwrite=args.overwrite)
    except ContractError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({
        "status": "ok",
        "state": report["state"],
        "report": validated["outputs"]["report_json"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
