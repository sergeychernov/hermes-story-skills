#!/usr/bin/env python3
"""Encode and verify a sample-exact audio-only story approval preview."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import wave
from pathlib import Path


def resolve_under(root: Path, value: str) -> Path:
    candidate = (root / value).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path escapes root: {value}")
    return candidate


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(command, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError("command failed: " + " ".join(command) + "\n" + result.stderr)
    return result


def parse_loudnorm(stderr: str) -> dict:
    matches = re.findall(r"\{\s*\"input_i\"[\s\S]*?\}", stderr)
    if not matches:
        raise RuntimeError("loudnorm JSON was not found")
    return json.loads(matches[-1])


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def duration_from_timeline(root: Path, spec: dict) -> float:
    duration = spec.get("duration")
    if not isinstance(duration, dict) or set(duration) != {"timeline"}:
        raise ValueError("duration must contain exactly one timeline path")
    timeline = json.loads(resolve_under(root, duration["timeline"]).read_text(encoding="utf-8"))
    value = float(timeline["total_seconds"])
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeline total_seconds must be positive and finite")
    return value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    root = args.root.resolve(); spec_path = args.spec.resolve()
    if spec_path != root and root not in spec_path.parents:
        raise SystemExit("spec path escapes root")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    allowed = {"schema_version", "input_wav", "duration", "output_m4a", "report", "sample_rate_hz", "bitrate", "target_lufs", "target_true_peak_dbfs", "target_lra_lu"}
    unknown = set(spec) - allowed
    missing = allowed - set(spec)
    if unknown: raise SystemExit("unknown preview spec fields: " + ", ".join(sorted(unknown)))
    if missing: raise SystemExit("missing preview spec fields: " + ", ".join(sorted(missing)))
    if spec.get("schema_version") != 1:
        raise SystemExit("unsupported preview spec")
    try:
        input_wav = resolve_under(root, spec["input_wav"])
        output = resolve_under(root, spec["output_m4a"])
        report_path = resolve_under(root, spec["report"])
        expected_seconds = duration_from_timeline(root, spec)
        if len({input_wav, output, report_path}) != 3: raise ValueError("input, output and report paths must be unique")
        if input_wav.suffix.lower() != ".wav": raise ValueError("input_wav must use .wav")
        if output.suffix.lower() != ".m4a": raise ValueError("output_m4a must use .m4a")
        if report_path.suffix.lower() != ".json": raise ValueError("report must use .json")
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    if not input_wav.is_file():
        raise SystemExit(f"input WAV not found: {input_wav}")
    existing = [str(p) for p in (output, report_path) if p.exists()]
    if existing and not args.overwrite:
        raise SystemExit("refusing to overwrite existing outputs: " + ", ".join(existing))
    sr = int(spec["sample_rate_hz"])
    if sr != 48000:
        raise SystemExit("sample_rate_hz must be 48000")
    bitrate = str(spec["bitrate"])
    if not re.fullmatch(r"(?:128|160|192|224|256|320)k", bitrate):
        raise SystemExit("unsupported AAC bitrate")
    target_i = float(spec["target_lufs"]); target_tp = float(spec["target_true_peak_dbfs"]); target_lra = float(spec["target_lra_lu"])
    if not -30.0 <= target_i <= -10.0: raise SystemExit("target_lufs must be within -30..-10")
    if not -6.0 <= target_tp <= -1.0: raise SystemExit("target_true_peak_dbfs must be within -6..-1")
    if not 1.0 <= target_lra <= 20.0: raise SystemExit("target_lra_lu must be within 1..20")
    with wave.open(str(input_wav), "rb") as inp:
        input_frames = inp.getnframes(); input_sr = inp.getframerate(); channels = inp.getnchannels(); width = inp.getsampwidth()
    expected_frames = int(round(expected_seconds * sr))
    if input_sr != sr or channels != 2 or width != 2:
        raise SystemExit("input must be PCM16 stereo 48 kHz WAV")
    if input_frames != expected_frames:
        raise SystemExit(f"input frame mismatch: expected {expected_frames}, got {input_frames}")
    first_filter = f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json"
    first = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(input_wav), "-af", first_filter, "-f", "null", "-"])
    measured = parse_loudnorm(first.stderr)
    render_filter = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true:print_format=summary,"
        f"aresample=48000,atrim=end_sample={expected_frames},asetpts=PTS-STARTPTS"
    )
    output.parent.mkdir(parents=True, exist_ok=True); report_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.stem + ".tmp" + output.suffix)
    if temp.exists():
        temp.unlink()
    try:
        run(["ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(input_wav), "-af", render_filter,
             "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", bitrate,
             "-t", f"{expected_frames / sr:.9f}", "-movflags", "+faststart", str(temp)])
        run(["ffmpeg", "-v", "error", "-i", str(temp), "-f", "null", "-"])
        probe = json.loads(run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,sample_rate,channels,duration", "-of", "json", str(temp)]).stdout)
        audio = next((s for s in probe["streams"] if s.get("codec_name") == "aac"), None)
        if not audio or int(audio["sample_rate"]) != sr or int(audio["channels"]) != 2:
            raise RuntimeError("encoded stream is not AAC stereo 48 kHz")
        output_duration = float(probe["format"]["duration"])
        tolerance = 1024 / sr + 0.001
        if abs(output_duration - expected_frames / sr) > tolerance:
            raise RuntimeError(f"encoded duration mismatch: {output_duration} vs {expected_frames / sr}")
        final_measure = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(temp), "-af", first_filter, "-f", "null", "-"])
        achieved = parse_loudnorm(final_measure.stderr)
        if float(achieved["input_tp"]) > target_tp + 0.2:
            raise RuntimeError(f"AAC true peak exceeds ceiling: {achieved['input_tp']} dBFS")
        temp.replace(output)
    except Exception:
        if temp.exists(): temp.unlink()
        raise
    ffmpeg_version = run(["ffmpeg", "-version"]).stdout.splitlines()[0]
    report = {
        "schema_version": 1, "kind": "story_audio_approval_preview", "approval": "pending",
        "spec": str(spec_path.relative_to(root)), "implementation_sha256": sha256(Path(__file__).resolve()), "input_wav": str(input_wav.relative_to(root)),
        "input_sha256": sha256(input_wav), "input_pcm_frames": input_frames,
        "expected_duration_seconds": expected_frames / sr, "output_m4a": str(output.relative_to(root)),
        "output_sha256": sha256(output), "output_duration_seconds": output_duration,
        "sample_rate_hz": sr, "channels": 2, "codec": "aac", "bitrate": bitrate,
        "target_lufs": target_i, "target_true_peak_dbfs": target_tp, "target_lra_lu": target_lra,
        "achieved_lufs": float(achieved["input_i"]), "achieved_true_peak_dbfs": float(achieved["input_tp"]),
        "achieved_lra_lu": float(achieved["input_lra"]), "render_filter": render_filter,
        "full_decode_verified": True, "ffmpeg_version": ffmpeg_version,
        "delivery_required": True, "muxed_to_video": False,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output.relative_to(root)), "report": str(report_path.relative_to(root))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
