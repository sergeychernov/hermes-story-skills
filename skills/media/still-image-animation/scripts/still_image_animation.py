#!/usr/bin/env python3
"""Pure helpers and FFmpeg rendering for one animated still scene."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
DEFAULT_FPS = 30
MOTIONS = {"none", "pan_left", "pan_right", "zoom_in", "zoom_out"}
FIT_MODES = {"crop", "contain"}
PAN_EASINGS = {"linear", "focus_dwell"}

# Explicit paths first (fast, deterministic), then shallow search under FONT_SEARCH_ROOTS.
FONT_CANDIDATES: tuple[Path, ...] = (
    # Linux — common distro layouts
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/liberation2/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSans-Bold.ttf"),
    # Homebrew — macOS (Apple Silicon / Intel) and Linuxbrew
    Path("/opt/homebrew/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/opt/homebrew/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/local/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/local/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    # macOS system and user fonts
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Verdana Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Tahoma Bold.ttf"),
    Path("/Library/Fonts/Arial Bold.ttf"),
    Path("/Library/Fonts/Arial.ttf"),
)
FONT_SEARCH_ROOTS: tuple[Path, ...] = (
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path("/opt/homebrew/share/fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"),
    Path.home() / "Library/Fonts",
)
FONT_RELATIVE_NAMES: tuple[str, ...] = (
    "DejaVuSans-Bold.ttf",
    "LiberationSans-Bold.ttf",
    "NotoSans-Bold.ttf",
    "Arial Bold.ttf",
    "Arial.ttf",
    "Verdana Bold.ttf",
    "Tahoma Bold.ttf",
    "truetype/dejavu/DejaVuSans-Bold.ttf",
    "truetype/liberation2/LiberationSans-Bold.ttf",
    "truetype/liberation/LiberationSans-Bold.ttf",
    "truetype/noto/NotoSans-Bold.ttf",
)
LOWER_FIFTH_Y = "min(h*0.80-text_h/2\\,h-text_h-360)"
# 0 = linear; 1 = full stop at focus. Keep below 1 so pan never freezes.
PAN_DWELL_STRENGTH = 0.55
ZOOM_AMOUNT = 0.130
ZOOM_OUT_START = 1.130
FADE_DURATION = 0.20


def resolve_font() -> Path | None:
    seen: set[Path] = set()
    for path in FONT_CANDIDATES:
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            return path
    for root in FONT_SEARCH_ROOTS:
        if not root.is_dir():
            continue
        for rel in FONT_RELATIVE_NAMES:
            path = root / rel
            if path in seen:
                continue
            seen.add(path)
            if path.is_file():
                return path
    return None


@lru_cache(maxsize=1)
def _ffmpeg_supports_drawtext() -> bool:
    try:
        completed = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            check=False,
            text=True,
            capture_output=True,
        )
    except OSError:
        return False
    return "drawtext" in completed.stdout


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
    pan_easing = str(raw.get("pan_easing", "focus_dwell"))
    if pan_easing not in PAN_EASINGS:
        raise ValueError(f"unsupported pan_easing: {pan_easing}")
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
        "fade_in": bool(raw.get("fade_in", True)),
        "fade_out": bool(raw.get("fade_out", True)),
        "pan_easing": pan_easing,
    }


def _resolve(root: Path, rel: str, *, require_file: bool) -> Path:
    root = root.resolve()
    path = (root / rel).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes root: {rel}")
    if require_file and not path.is_file():
        raise ValueError(f"missing input: {path}")
    return path


def _validate_motion_fit(motion: str, fit_mode: str) -> None:
    if motion not in MOTIONS:
        raise ValueError(f"unsupported motion: {motion}")
    if fit_mode not in FIT_MODES:
        raise ValueError(f"unsupported fit_mode: {fit_mode}")
    if fit_mode == "contain" and motion in {"pan_left", "pan_right"}:
        raise ValueError("contain fit_mode cannot pan while preserving the full image")


def _motion_canvas_size(width: int, height: int, motion: str) -> tuple[int, int]:
    if motion in {"zoom_in", "zoom_out"}:
        return width * 2, height * 2
    return width, height


def _pan_progress_expr(duration: float, pan_easing: str, focus_x: float) -> str:
    if pan_easing not in PAN_EASINGS:
        raise ValueError(f"unsupported pan_easing: {pan_easing}")
    u = f"t/{duration:.3f}"
    if pan_easing == "linear":
        return u
    # Slow near focus_x without stopping: p' = 1 - strength at the focus.
    # Fast toward the edges. Full [0,1] crop travel with clip for safety.
    d = PAN_DWELL_STRENGTH
    raw = f"({u}-{d:.3f}*sin(2*PI*({u}-{focus_x:.3f}))/(2*PI))"
    return f"clip({raw}\\,0\\,1)"


def _pan_progress_value(u: float, pan_easing: str, focus_x: float) -> float:
    if pan_easing == "linear":
        return u
    raw = u - PAN_DWELL_STRENGTH * math.sin(2 * math.pi * (u - focus_x)) / (2 * math.pi)
    return max(0.0, min(1.0, raw))


def _pan_crop_x_expr(
    motion: str,
    focus_x: float,
    duration: float,
    pan_easing: str = "focus_dwell",
) -> str:
    if pan_easing not in PAN_EASINGS:
        raise ValueError(f"unsupported pan_easing: {pan_easing}")
    progress = _pan_progress_expr(duration, pan_easing, focus_x)
    if motion == "pan_left":
        return f"'(iw-ow)*clip(1-({progress}),0,1)'"
    if motion == "pan_right":
        return f"'(iw-ow)*clip({progress},0,1)'"
    return f"(iw-ow)*{focus_x:.3f}"


def _crop_base_chain(
    input_index: int,
    canvas_w: int,
    canvas_h: int,
    x_expr: str,
    duration: float,
    fps: int,
) -> str:
    return (
        f"[{input_index}:v]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
        f"crop={canvas_w}:{canvas_h}:x={x_expr}:y=(ih-oh)/2,"
        f"setsar=1,fps={fps},trim=duration={duration:.3f},setpts=PTS-STARTPTS"
    )


def _contain_base_chain(
    input_index: int,
    width: int,
    height: int,
    canvas_w: int,
    canvas_h: int,
    duration: float,
    fps: int,
) -> str:
    return (
        f"[{input_index}:v]split=2[bg{input_index}src][fg{input_index}src];"
        f"[bg{input_index}src]scale={max(1, width // 2)}:{max(1, height // 2)}:force_original_aspect_ratio=increase,"
        f"crop={max(1, width // 2)}:{max(1, height // 2)},boxblur=24:12,"
        f"scale={canvas_w}:{canvas_h}[bg{input_index}];"
        f"[fg{input_index}src]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=decrease[fg{input_index}];"
        f"[bg{input_index}][fg{input_index}]overlay=(W-w)/2:(H-h)/2,setsar=1,fps={fps},"
        f"trim=duration={duration:.3f},setpts=PTS-STARTPTS"
    )


def _zoompan_filter(
    motion: str,
    focus_x: float,
    focus_y: float,
    duration: float,
    fps: int,
    width: int,
    height: int,
) -> str:
    if motion not in {"zoom_in", "zoom_out"}:
        return ""
    frames = max(1, round(duration * fps) - 1)
    ease = f"((1-cos(PI*min(on/{frames},1)))/2)"
    zoom = f"1+{ZOOM_AMOUNT:.3f}*{ease}" if motion == "zoom_in" else f"{ZOOM_OUT_START:.3f}-{ZOOM_AMOUNT:.3f}*{ease}"
    x = f"max(0,min(iw-iw/zoom,iw*{focus_x:.3f}-iw/(2*zoom)))"
    y = f"max(0,min(ih-ih/zoom,ih*{focus_y:.3f}-ih/(2*zoom)))"
    return f",zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={width}x{height}:fps={fps}"


def _drawtext_filter(
    text_file: Path,
    font: Path,
    fontsize: int,
    y: str,
    start: float | None = None,
    end: float | None = None,
) -> str:
    escaped = str(text_file).replace("'", "\\'").replace(":", "\\:")
    font_path = str(font).replace(":", "\\:")
    enable = "" if start is None or end is None else f":enable='between(t,{start:.3f},{end:.3f})'"
    return (
        f",drawtext=fontfile='{font_path}':textfile='{escaped}':fontcolor=white:"
        f"fontsize={fontsize}:line_spacing=10:x=max(70\\,min((w-text_w)/2\\,820-text_w)):"
        f"y={y}:box=1:boxcolor=black@0.58:boxborderw=24{enable}"
    )


def _text_overlay_filters(
    duration: float,
    title_file: Path | None,
    caption_overlays: list[tuple[Path, float, float]] | Path | None,
    title_y: str,
    caption_y: str,
) -> str:
    font = resolve_font()
    if not font or not _ffmpeg_supports_drawtext():
        return ""
    filters = ""
    if title_file:
        filters += _drawtext_filter(title_file, font, 58, title_y)
    if isinstance(caption_overlays, Path):
        caption_overlays = [(caption_overlays, 0.0, duration)]
    for caption_file, start, end in caption_overlays or []:
        filters += _drawtext_filter(caption_file, font, 48, caption_y, start, end)
    return filters


def _fade_filters(duration: float, fade_in: bool, fade_out: bool) -> str:
    filters = ""
    if fade_in:
        filters += f",fade=t=in:st=0:d={FADE_DURATION:.2f}"
    if fade_out:
        fade_out_start = max(0.0, duration - FADE_DURATION)
        filters += f",fade=t=out:st={fade_out_start:.3f}:d={FADE_DURATION:.2f}"
    return filters


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
    fade_in: bool = True,
    fade_out: bool = True,
    pan_easing: str = "focus_dwell",
) -> str:
    focus_x = max(0.0, min(1.0, focus_x))
    focus_y = max(0.0, min(1.0, focus_y))
    _validate_motion_fit(motion, fit_mode)
    canvas_w, canvas_h = _motion_canvas_size(width, height, motion)
    if fit_mode == "crop":
        base = _crop_base_chain(
            input_index,
            canvas_w,
            canvas_h,
            _pan_crop_x_expr(motion, focus_x, duration, pan_easing),
            duration,
            fps,
        )
    else:
        base = _contain_base_chain(input_index, width, height, canvas_w, canvas_h, duration, fps)
    base += _zoompan_filter(motion, focus_x, focus_y, duration, fps, width, height)
    base += _text_overlay_filters(duration, title_file, caption_overlays, title_y, caption_y)
    base += _fade_filters(duration, fade_in, fade_out)
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
            fade_in=spec["fade_in"],
            fade_out=spec["fade_out"],
            pan_easing=spec["pan_easing"],
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
