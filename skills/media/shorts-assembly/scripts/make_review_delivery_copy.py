#!/usr/bin/env python3
"""Create a bounded review-only MP4 without mutating the publication master."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
    )


def probe(path: Path, count_frames: bool = True) -> dict:
    cmd = ["ffprobe", "-v", "error"]
    if count_frames:
        cmd.append("-count_frames")
    cmd += ["-show_streams", "-show_format", "-of", "json", str(path)]
    return json.loads(run(cmd, capture=True).stdout)


def stream(data: dict, kind: str) -> dict | None:
    return next((s for s in data["streams"] if s.get("codec_type") == kind), None)


def frame_count(video: dict) -> int:
    value = video.get("nb_read_frames") or video.get("nb_frames")
    if not value or value == "N/A":
        raise ValueError("video frame count unavailable")
    return int(value)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audio_payload_hash(path: Path) -> str:
    result = run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-c", "copy", "-f", "hash", "-hash", "sha256", "-"],
        capture=True,
    ).stdout.strip()
    if not result.startswith("SHA256="):
        raise RuntimeError("audio payload hash unavailable")
    return result.split("=", 1)[1]


def full_decode(path: Path, selector: str) -> None:
    run(["ffmpeg", "-v", "error", "-i", str(path), "-map", selector, "-f", "null", "-"])


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path, help="canonical publication/review master")
    p.add_argument("--output", required=True, type=Path, help="new versioned review-only MP4")
    p.add_argument("--width", type=int, default=720)
    p.add_argument("--height", type=int, default=1280)
    p.add_argument("--max-mib", type=float, default=18.0)
    p.add_argument("--crf", type=int, default=24)
    p.add_argument("--preset", default="veryfast")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    source = args.input.resolve()
    output = args.output.resolve()
    report_path = Path(str(output) + ".report.json")
    if not source.is_file():
        raise SystemExit(f"input not found: {source}")
    if source == output:
        raise SystemExit("output must differ from publication master")
    if output.exists() or report_path.exists():
        raise SystemExit("refusing to overwrite output or report")
    if args.width < 2 or args.height < 2 or args.width % 2 or args.height % 2:
        raise SystemExit("width and height must be positive even integers")
    if not 0.5 <= args.max_mib <= 200:
        raise SystemExit("max-mib must be between 0.5 and 200")
    if not 18 <= args.crf <= 32:
        raise SystemExit("crf must be between 18 and 32")
    for binary in ("ffmpeg", "ffprobe"):
        if not shutil.which(binary):
            raise SystemExit(f"missing required command: {binary}")

    source_probe = probe(source)
    sv = stream(source_probe, "video")
    sa = stream(source_probe, "audio")
    if not sv:
        raise SystemExit("input has no video stream")
    source_ratio = int(sv["width"]) / int(sv["height"])
    target_ratio = args.width / args.height
    if abs(source_ratio - target_ratio) > 0.002:
        raise SystemExit("target aspect ratio differs from source; refuse implicit crop/pad/stretch")
    source_frames = frame_count(sv)
    fps = Fraction(sv.get("avg_frame_rate") or sv["r_frame_rate"])
    if fps <= 0:
        raise SystemExit("invalid source frame rate")
    fps_text = f"{fps.numerator}/{fps.denominator}"
    max_bytes = int(args.max_mib * 1024 * 1024)
    output.parent.mkdir(parents=True, exist_ok=True)

    attempts: list[dict] = []
    chosen_crf: int | None = None
    for crf in sorted(set(min(32, args.crf + step) for step in (0, 3, 6, 8))):
        tmp = output.with_name(f".{output.name}.crf{crf}.tmp.mp4")
        tmp.unlink(missing_ok=True)
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-map", "0:v:0", "-map", "0:a:0?",
            "-vf", f"scale={args.width}:{args.height}:flags=lanczos,setsar=1",
            "-c:v", "libx264", "-preset", args.preset, "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-r", fps_text, "-fps_mode", "cfr",
            "-c:a", "copy", "-movflags", "+faststart", str(tmp),
        ]
        try:
            run(cmd)
            size = tmp.stat().st_size
            attempts.append({"crf": crf, "bytes": size})
            if size <= max_bytes:
                os.replace(tmp, output)
                chosen_crf = crf
                break
        finally:
            tmp.unlink(missing_ok=True)
    if chosen_crf is None:
        raise SystemExit(f"no derivative fit within {args.max_mib} MiB; attempts={attempts}")

    try:
        output_probe = probe(output)
        ov = stream(output_probe, "video")
        oa = stream(output_probe, "audio")
        if not ov:
            raise RuntimeError("output video stream missing")
        output_frames = frame_count(ov)
        if output_frames != source_frames:
            raise RuntimeError(f"frame count changed: {output_frames} != {source_frames}")
        if (int(ov["width"]), int(ov["height"])) != (args.width, args.height):
            raise RuntimeError("output dimensions mismatch")
        if Fraction(ov.get("avg_frame_rate") or ov["r_frame_rate"]) != fps:
            raise RuntimeError("output frame rate mismatch")
        source_duration = source_frames / float(fps)
        output_duration = float(ov["duration"])
        if abs(output_duration - source_duration) > 1 / float(fps):
            raise RuntimeError("output duration drift exceeds one frame")
        full_decode(output, "0:v:0")
        audio_identity = None
        audio_hash = None
        if sa:
            if not oa:
                raise RuntimeError("output audio stream missing")
            source_audio_hash = audio_payload_hash(source)
            audio_hash = audio_payload_hash(output)
            audio_identity = source_audio_hash == audio_hash
            if not audio_identity:
                raise RuntimeError("stream-copied audio payload changed")
            full_decode(output, "0:a:0")
        elif oa:
            raise RuntimeError("unexpected output audio stream")

        report = {
            "schema_version": 1,
            "status": "ok",
            "review_only": True,
            "publication_eligible": False,
            "source": {
                "path": str(source),
                "sha256": sha256(source),
                "width": int(sv["width"]),
                "height": int(sv["height"]),
                "frame_count": source_frames,
                "fps": fps_text,
            },
            "output": {
                "path": str(output),
                "sha256": sha256(output),
                "bytes": output.stat().st_size,
                "max_bytes": max_bytes,
                "max_mib_policy": args.max_mib,
            },
            "video": {
                "width": args.width,
                "height": args.height,
                "frame_count": output_frames,
                "fps": fps_text,
                "duration_seconds": output_duration,
                "codec": ov.get("codec_name"),
                "pixel_format": ov.get("pix_fmt"),
                "chosen_crf": chosen_crf,
                "attempts": attempts,
            },
            "audio": {
                "present": bool(sa),
                "operation": "stream-copy" if sa else "none",
                "packet_payload_sha256": audio_hash,
                "packet_payload_identity": audio_identity,
                "codec": oa.get("codec_name") if oa else None,
                "sample_rate": int(oa["sample_rate"]) if oa else None,
                "channels": int(oa["channels"]) if oa else None,
            },
            "verification": {
                "size_within_budget": True,
                "frame_timeline_preserved": True,
                "full_video_decode": True,
                "full_audio_decode": bool(sa),
                "visual_review": "pending",
            },
        }
        tmp_report = Path(str(report_path) + ".tmp")
        tmp_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_report, report_path)
        print(json.dumps({"status": "ok", "output": str(output), "bytes": output.stat().st_size, "report": str(report_path)}))
        return 0
    except Exception:
        output.unlink(missing_ok=True)
        report_path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    sys.exit(main())
