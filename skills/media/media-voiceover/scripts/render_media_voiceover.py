#!/usr/bin/env python3
"""Mix approved voiceover onto one scene or rendered group MP4."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_media_voiceover import (  # noqa: E402
    RENDERER_VERSION,
    safe_path,
    validate_spec,
)

SAMPLE_RATE = 48_000
AUDIO_CHANNELS = 2


def run(cmd: list[str], *, capture: bool = False) -> str:
    if capture:
        return subprocess.check_output(cmd, text=True)
    subprocess.run(cmd, check=True)
    return ""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_fps(value: str) -> float:
    if "/" in value:
        return float(Fraction(value))
    return float(value)


def probe_media(path: Path) -> dict[str, Any]:
    raw = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-count_frames",
                "-show_entries",
                "stream=index,codec_type,codec_name,width,height,r_frame_rate,nb_read_frames,nb_frames,channels,sample_rate,duration",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture=True,
        )
    )
    video = next((s for s in raw.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError(f"no video stream: {path}")
    audio = next((s for s in raw.get("streams", []) if s.get("codec_type") == "audio"), None)
    fps = parse_fps(str(video.get("r_frame_rate", "30/1")))
    nb_frames = video.get("nb_read_frames") or video.get("nb_frames")
    if nb_frames in (None, "N/A"):
        raise ValueError(f"could not count decoded video frames: {path}")
    frame_count = int(nb_frames)
    if frame_count <= 0:
        raise ValueError(f"target has no decoded video frames: {path}")
    duration_seconds = frame_count / fps
    has_audio = audio is not None
    return {
        "path": str(path),
        "width": int(video.get("width", 0)),
        "height": int(video.get("height", 0)),
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": duration_seconds,
        "has_audio": has_audio,
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_channels": int(audio["channels"]) if audio and audio.get("channels") else None,
        "audio_sample_rate": int(float(audio["sample_rate"])) if audio and audio.get("sample_rate") else None,
        "probe": raw,
    }


def full_decode_verify(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(f"full-decode verification failed: {completed.stderr.strip()}")
    return {"ok": True, "method": "ffmpeg -f null -"}


def build_filtergraph(
    spec: dict[str, Any],
    probe: dict[str, Any],
) -> tuple[str, str, str]:
    duration = probe["duration_seconds"]
    width = probe["width"]
    height = probe["height"]
    fps = probe["fps"]
    filters: list[str] = []

    filters.append(
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},"
        f"trim=duration={duration:.6f},setpts=PTS-STARTPTS,format=yuv420p[vout]"
    )

    mode = spec["source_audio"]
    use_null = mode == "remove" or not probe["has_audio"] or (mode in {"lower", "boost"} and not probe["has_audio"])
    if use_null:
        filters.append(
            f"anullsrc=channel_layout=stereo:sample_rate={SAMPLE_RATE},atrim=0:{duration:.6f},"
            f"asetpts=PTS-STARTPTS[abase]"
        )
    elif mode == "preserve":
        filters.append(
            f"[0:a]aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"aresample={SAMPLE_RATE},atrim=0:{duration:.6f},asetpts=PTS-STARTPTS[abase]"
        )
    elif mode in {"lower", "boost"}:
        gain_db = float(spec["gain_db"])
        filters.append(
            f"[0:a]aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"aresample={SAMPLE_RATE},volume={gain_db:.3f}dB,"
            f"atrim=0:{duration:.6f},asetpts=PTS-STARTPTS[abase]"
        )
    else:
        raise ValueError(f"unsupported source_audio mode: {mode}")

    voiceover = spec["voiceover"]
    delay_ms = int(round(float(voiceover["start_seconds"]) * 1000))
    vo_gain_db = float(voiceover["gain_db"])
    filters.append(
        f"[1:a]aformat=sample_fmts=fltp:channel_layouts=stereo,"
        f"aresample={SAMPLE_RATE},volume={vo_gain_db:.3f}dB,adelay={delay_ms}|{delay_ms}[vo]"
    )
    filters.append("[abase][vo]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")

    return ";".join(filters), "vout", "aout"


def probe_output(path: Path) -> dict[str, Any]:
    return json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration,size,bit_rate:stream=codec_name,codec_type,width,height,r_frame_rate,pix_fmt,channels,sample_rate,nb_frames",
                "-of",
                "json",
                str(path),
            ],
            capture=True,
        )
    )


def render(root: Path, raw: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    spec = validate_spec(raw, root)
    output = safe_path(root, spec["output"])
    report_rel = spec.get("report", f"{spec['output'].rsplit('.', 1)[0]}-report.json")
    report_path = safe_path(root, report_rel)

    target_path = safe_path(root, spec["target"]["path"], must_exist=True)
    voiceover_path = safe_path(root, spec["voiceover"]["path"], must_exist=True)

    source_paths = [target_path, voiceover_path]
    source_hashes_before = {str(path): sha256(path) for path in source_paths}
    source_mtime_before = {str(path): path.stat().st_mtime_ns for path in source_paths}

    probe = probe_media(target_path)
    authoritative_duration = probe["duration_seconds"]
    authoritative_frames = probe["frame_count"]

    filtergraph, video_map, audio_map = build_filtergraph(spec, probe)

    output.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_name(f".{output.stem}.{os.getpid()}.tmp{output.suffix}")
    temp_output.unlink(missing_ok=True)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(target_path),
        "-i",
        str(voiceover_path),
        "-filter_complex",
        filtergraph,
        "-map",
        f"[{video_map}]",
        "-map",
        f"[{audio_map}]",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        str(SAMPLE_RATE),
        "-ac",
        str(AUDIO_CHANNELS),
        "-movflags",
        "+faststart",
        "-t",
        f"{authoritative_duration:.6f}",
        str(temp_output),
    ]

    try:
        run(cmd)
        decode_info = full_decode_verify(temp_output)
        temp_output.replace(output)
    finally:
        if temp_output.exists():
            temp_output.unlink()

    for path in source_paths:
        if sha256(path) != source_hashes_before[str(path)]:
            raise ValueError(f"source file changed during render: {path}")
        if path.stat().st_mtime_ns != source_mtime_before[str(path)]:
            raise ValueError(f"source file mtime changed during render: {path}")

    output_probe = probe_output(output)
    video_stream = next(s for s in output_probe["streams"] if s["codec_type"] == "video")
    audio_stream = next(s for s in output_probe["streams"] if s["codec_type"] == "audio")

    report = {
        "schema_version": 1,
        "renderer_version": RENDERER_VERSION,
        "status": "ok",
        "output": spec["output"],
        "sha256": sha256(output),
        "target": spec["target"],
        "source_audio": spec["source_audio"],
        "gain_db": spec["gain_db"],
        "voiceover": spec["voiceover"],
        "source_hash": source_hashes_before[str(target_path)],
        "voiceover_hash": source_hashes_before[str(voiceover_path)],
        "source_probe": probe,
        "authoritative_duration_seconds": authoritative_duration,
        "authoritative_frame_count": authoritative_frames,
        "duration_basis": "decoded_video_frames_over_source_fps",
        "output_probe": output_probe,
        "video": {
            "codec": video_stream.get("codec_name"),
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "fps": video_stream.get("r_frame_rate"),
            "pix_fmt": video_stream.get("pix_fmt"),
            "frame_count": video_stream.get("nb_frames"),
        },
        "audio": {
            "codec": audio_stream.get("codec_name"),
            "sample_rate": int(float(audio_stream.get("sample_rate", SAMPLE_RATE))),
            "channels": int(audio_stream.get("channels", AUDIO_CHANNELS)),
            "ducking": False,
        },
        "full_decode_verification": decode_info,
        "normalized_spec": spec,
        "originals_immutable": True,
    }

    temp_report = report_path.with_name(f".{report_path.name}.{os.getpid()}.tmp")
    temp_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_report.replace(report_path)
    report["report"] = report_rel
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Render voiceover mix onto a scene or group MP4.")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    args = parser.parse_args()
    try:
        raw = json.loads(args.spec.read_text(encoding="utf-8"))
        report = render(args.root.resolve(), raw)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(
            json.dumps({"schema_version": 1, "status": "error", "error": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
