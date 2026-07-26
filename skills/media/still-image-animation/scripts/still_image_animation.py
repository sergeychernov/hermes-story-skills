#!/usr/bin/env python3
"""Pure helpers and FFmpeg rendering for one animated still scene."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path

DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
DEFAULT_FPS = 30
MOTIONS = {"none", "pan_left", "pan_right", "zoom_in", "zoom_out"}
FIT_MODES = {"crop", "contain"}
FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
]
LOWER_FIFTH_Y = "min(h*0.80-text_h/2\\,h-text_h-360)"


def _relative_path(value: object, field: str) -> str:
    raw = str(value or "").strip()
    path = Path(raw)
    if not raw:
        raise ValueError(f"{field} is required")
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"path escapes root: {raw}")
    return raw


def normalize_spec(raw: dict) -> dict:
    if raw.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    motion = str(raw.get("motion", "none"))
    if motion not in MOTIONS:
        raise ValueError(f"unsupported motion: {motion}")
    fit_mode = str(raw.get("fit_mode", "crop"))
    if fit_mode not in FIT_MODES:
        raise ValueError(f"unsupported fit_mode: {fit_mode}")
    if fit_mode == "contain" and motion in {"pan_left", "pan_right"}:
        raise ValueError("contain fit_mode cannot pan while preserving the full image")
    width = int(raw.get("width", DEFAULT_WIDTH))
    height = int(raw.get("height", DEFAULT_HEIGHT))
    fps = int(raw.get("fps", DEFAULT_FPS))
    duration = float(raw.get("duration", 3.0))
    if width <= 0 or height <= 0 or fps <= 0 or duration <= 0:
        raise ValueError("width, height, fps, and duration must be positive")
    return {
        "schema_version": 1,
        "source": _relative_path(raw.get("source"), "source"),
        "output": _relative_path(raw.get("output"), "output"),
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
        "fit_mode": fit_mode,
        "motion": motion,
        "focus_x": max(0.0, min(1.0, float(raw.get("focus_x", 0.5)))),
        "focus_y": max(0.0, min(1.0, float(raw.get("focus_y", 0.5)))),
        "title": str(raw.get("title", "")).strip(),
        "overwrite": bool(raw.get("overwrite", False)),
    }


def _resolve(root: Path, rel: str, *, require_file: bool) -> Path:
    root = root.resolve()
    path = (root / rel).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes root: {rel}")
    if require_file and not path.is_file():
        raise ValueError(f"missing input: {path}")
    return path


def visual_filter(
    input_index: int,
    duration: float,
    title_file: Path | None = None,
    caption_overlays: list[tuple[Path, float, float]] | Path | None = None,
    *,
    fit_mode: str = "contain",
    focus_x: float = 0.5,
    focus_y: float = 0.5,
    motion: str = "none",
    title_y: str = LOWER_FIFTH_Y,
    caption_y: str = LOWER_FIFTH_Y,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    fps: int = DEFAULT_FPS,
    fade: bool = True,
) -> str:
    focus_x = max(0.0, min(1.0, focus_x))
    focus_y = max(0.0, min(1.0, focus_y))
    if motion not in MOTIONS:
        raise ValueError(f"unsupported motion: {motion}")
    if fit_mode not in FIT_MODES:
        raise ValueError(f"unsupported fit_mode: {fit_mode}")
    if fit_mode == "contain" and motion in {"pan_left", "pan_right"}:
        raise ValueError("contain fit_mode cannot pan while preserving the full image")
    zoom_motion = motion in {"zoom_in", "zoom_out"}
    canvas_w, canvas_h = (width * 2, height * 2) if zoom_motion else (width, height)
    if fit_mode == "crop":
        if motion == "pan_left":
            x_expr = f"'(iw-ow)*clip({min(1.0, focus_x + 0.18):.3f}-0.360*t/{duration:.3f},0,1)'"
        elif motion == "pan_right":
            x_expr = f"'(iw-ow)*clip({max(0.0, focus_x - 0.18):.3f}+0.360*t/{duration:.3f},0,1)'"
        else:
            x_expr = f"(iw-ow)*{focus_x:.3f}"
        base = (
            f"[{input_index}:v]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
            f"crop={canvas_w}:{canvas_h}:x={x_expr}:y=(ih-oh)/2,"
            f"setsar=1,fps={fps},trim=duration={duration:.3f},setpts=PTS-STARTPTS"
        )
    else:
        base = (
            f"[{input_index}:v]split=2[bg{input_index}src][fg{input_index}src];"
            f"[bg{input_index}src]scale={max(1, width // 2)}:{max(1, height // 2)}:force_original_aspect_ratio=increase,"
            f"crop={max(1, width // 2)}:{max(1, height // 2)},boxblur=24:12,"
            f"scale={canvas_w}:{canvas_h}[bg{input_index}];"
            f"[fg{input_index}src]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=decrease[fg{input_index}];"
            f"[bg{input_index}][fg{input_index}]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={fps},"
            f"trim=duration={duration:.3f},setpts=PTS-STARTPTS"
        )
    if zoom_motion:
        frames = max(1, round(duration * fps) - 1)
        ease = f"((1-cos(PI*min(on/{frames},1)))/2)"
        zoom = f"1+0.130*{ease}" if motion == "zoom_in" else f"1.130-0.130*{ease}"
        x = f"max(0,min(iw-iw/zoom,iw*{focus_x:.3f}-iw/(2*zoom)))"
        y = f"max(0,min(ih-ih/zoom,ih*{focus_y:.3f}-ih/(2*zoom)))"
        base += f",zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={width}x{height}:fps={fps}"

    font = next((path for path in FONT_CANDIDATES if path.exists()), None)

    def add_text(text_file: Path, fontsize: int, y: str, start: float | None = None, end: float | None = None) -> str:
        escaped = str(text_file).replace("'", "\\'").replace(":", "\\:")
        font_path = str(font).replace(":", "\\:")
        enable = "" if start is None or end is None else f":enable='between(t,{start:.3f},{end:.3f})'"
        return (
            f",drawtext=fontfile='{font_path}':textfile='{escaped}':fontcolor=white:"
            f"fontsize={fontsize}:line_spacing=10:x=max(70\\,min((w-text_w)/2\\,820-text_w)):"
            f"y={y}:box=1:boxcolor=black@0.58:boxborderw=24{enable}"
        )

    if font and title_file:
        base += add_text(title_file, 58, title_y)
    if isinstance(caption_overlays, Path):
        caption_overlays = [(caption_overlays, 0.0, duration)]
    if font:
        for caption_file, start, end in caption_overlays or []:
            base += add_text(caption_file, 48, caption_y, start, end)
    if fade:
        fade_out = max(0.0, duration - 0.20)
        base += f",fade=t=in:st=0:d=0.20,fade=t=out:st={fade_out:.3f}:d=0.20"
    return base + f",format=yuv420p[v{input_index}]"


def _probe(path: Path) -> dict:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


def _sampled_frame_difference(path: Path, fps: int, duration: float) -> float:
    frame_count = max(2, round(fps * duration))
    first, last = min(2, frame_count - 1), max(1, frame_count - 3)
    completed = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", str(path),
            "-vf", f"select='eq(n,{first})+eq(n,{last})',scale=1:1",
            "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ],
        check=True,
        capture_output=True,
    )
    data = completed.stdout
    if len(data) < 6:
        return 0.0
    a, b = data[:3], data[3:6]
    return round(math.sqrt(sum((int(x) - int(y)) ** 2 for x, y in zip(a, b))), 3)


def render(root: Path, raw_spec: dict) -> dict:
    spec = normalize_spec(raw_spec)
    root = root.resolve()
    source = _resolve(root, spec["source"], require_file=True)
    output = _resolve(root, spec["output"], require_file=False)
    if output.exists() and not spec["overwrite"]:
        raise ValueError(f"output exists (set overwrite=true): {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    title_file = None
    try:
        if spec["title"]:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=output.parent,
                prefix=f".{output.stem}.title.",
                suffix=".txt",
                delete=False,
            ) as handle:
                handle.write(spec["title"].rstrip() + "\n")
                title_file = Path(handle.name)
        vf = visual_filter(
            0,
            spec["duration"],
            title_file,
            [],
            fit_mode=spec["fit_mode"],
            focus_x=spec["focus_x"],
            focus_y=spec["focus_y"],
            motion=spec["motion"],
            width=spec["width"],
            height=spec["height"],
            fps=spec["fps"],
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-loop", "1", "-t", f"{spec['duration']:.3f}",
                "-i", str(source), "-filter_complex", vf, "-map", "[v0]", "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(spec["fps"]), "-movflags", "+faststart", str(output),
            ],
            check=True,
        )
        metadata = _probe(output)
        video = next(stream for stream in metadata["streams"] if stream.get("codec_type") == "video")
        difference = _sampled_frame_difference(output, spec["fps"], spec["duration"])
        return {
            "schema_version": 1,
            "status": "ok",
            "output": spec["output"],
            "width": int(video["width"]),
            "height": int(video["height"]),
            "fps": spec["fps"],
            "duration": float(metadata["format"]["duration"]),
            "codec": video["codec_name"],
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "verification": {
                "decodable": True,
                "sampled_frame_difference": difference,
                "motion_detected": spec["motion"] != "none" and difference > 1.0,
            },
        }
    finally:
        if title_file:
            title_file.unlink(missing_ok=True)
