#!/usr/bin/env python3
"""Single source of truth for YouTube Shorts title-safe geometry.

The lower 28% of the frame is always title-free. A 20% strip on the
right is also reserved for YouTube action buttons. FFmpeg expressions account
for drawtext's text dimensions and box border.
"""
from __future__ import annotations

import argparse
import json

BOTTOM_FREE = 0.28
RIGHT_FREE = 0.20
LEFT_MARGIN = 0.08
BOX_BORDER = 24



def ffmpeg_expressions(position: str = "lower_fifth", box_border: int = BOX_BORDER) -> dict[str, str | float | int]:
    if position not in {"lower_fifth", "middle"}:
        raise ValueError(f"unsupported YouTube-safe title position: {position}")

    # drawtext x/y address the text itself; boxborderw extends beyond it.
    x = (
        f"max(w*{LEFT_MARGIN:.2f}+{box_border}\\,"
        f"min((w-text_w)/2\\,w*{1-RIGHT_FREE:.2f}-text_w-{box_border}))"
    )
    # For the standard title, the bottom edge of the complete drawtext box is
    # pinned exactly to 72% of frame height, above the current Shorts metadata
    # and promotion controls. No additional visual centering.
    y = (f"h*{1-BOTTOM_FREE:.2f}-text_h-{box_border}" if position == "lower_fifth"
         else f"h*0.50-text_h/2")
    return {
        "x": x,
        "y": y,
        "bottom_free": BOTTOM_FREE,
        "right_free": RIGHT_FREE,
        "left_margin": LEFT_MARGIN,
        "box_border": box_border,
        "position": position,
    }


def safe_rect(width: int, height: int) -> dict[str, int]:
    """Pixel rectangle in which the complete title box must fit."""
    return {
        "x": round(width * LEFT_MARGIN),
        "y": 0,
        "width": round(width * (1 - RIGHT_FREE - LEFT_MARGIN)),
        "height": round(height * (1 - BOTTOM_FREE)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--position", choices=["lower_fifth", "middle"], default="lower_fifth")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--box-border", type=int, default=BOX_BORDER)
    args = parser.parse_args()
    result = ffmpeg_expressions(args.position, args.box_border)
    result["safe_rect"] = safe_rect(args.width, args.height)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
