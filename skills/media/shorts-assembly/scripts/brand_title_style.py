#!/usr/bin/env python3
"""Canonical reproducible title style for Sergey's vertical stories."""
from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from youtube_safe_title import ffmpeg_expressions

STYLE_VERSION = "sergey-vertical-title-v2"
FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
)
FONT_SIZE_AT_1080 = 54
LINE_SPACING_AT_1080 = 12
BOX_BORDER_AT_1080 = 24
BOX_COLOR = "black@0.406"
FONT_COLOR = "white"
POSITION = "lower_fifth"


def resolve_font() -> Path:
    for path in FONT_CANDIDATES:
        if path.is_file():
            return path
    raise FileNotFoundError("no canonical bold sans-serif font found")


def scaled(value: int, width: int) -> int:
    return max(1, round(value * width / 1080))


def style_manifest(width: int = 1080) -> dict[str, object]:
    border = scaled(BOX_BORDER_AT_1080, width)
    safe = ffmpeg_expressions(POSITION, border)
    font = resolve_font()
    return {
        "style_version": STYLE_VERSION,
        "font_file": str(font),
        "font_sha256_required": True,
        "font_family": "DejaVu Sans",
        "font_weight": "Bold",
        "font_size": scaled(FONT_SIZE_AT_1080, width),
        "line_spacing": scaled(LINE_SPACING_AT_1080, width),
        "font_color": FONT_COLOR,
        "box": True,
        "box_color": BOX_COLOR,
        "box_border": border,
        "position": POSITION,
        "x": safe["x"],
        "y": safe["y"],
        "safe_box_bottom_ratio": 0.72,
        "right_controls_free_ratio": 0.20,
    }


def drawtext_filter(text_file: Path, width: int = 1080) -> tuple[str, dict[str, object]]:
    style = style_manifest(width)
    font = str(style["font_file"]).replace(":", "\\:")
    text = str(text_file).replace("'", "'\\''").replace(":", "\\:")
    chain = (
        f"drawtext=fontfile='{font}':textfile='{text}':"
        f"fontcolor={style['font_color']}:fontsize={style['font_size']}:"
        f"line_spacing={style['line_spacing']}:"
        f"box=1:boxcolor={style['box_color']}:boxborderw={style['box_border']}:"
        f"x='{style['x']}':y='{style['y']}'"
    )
    return chain, style
