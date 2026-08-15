#!/usr/bin/env python3
"""Render a deterministic animated multi-photo collage from a JSON contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

SHORTS_SCRIPTS = Path(__file__).resolve().parents[2] / "shorts-assembly" / "scripts"
for _module_file in ("youtube_safe_title.py", "brand_title_style.py"):
    if not (SHORTS_SCRIPTS / _module_file).is_file():
        raise ImportError(f"missing sibling module: {SHORTS_SCRIPTS / _module_file}")
if str(SHORTS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SHORTS_SCRIPTS))
import youtube_safe_title as _youtube_safe_title
import brand_title_style as _brand_title_style
for _module, _module_file in (
    (_youtube_safe_title, "youtube_safe_title.py"),
    (_brand_title_style, "brand_title_style.py"),
):
    if Path(_module.__file__).resolve() != (SHORTS_SCRIPTS / _module_file).resolve():
        raise ImportError(f"sibling module mismatch: {_module_file}")
ffmpeg_expressions = _youtube_safe_title.ffmpeg_expressions
style_manifest = _brand_title_style.style_manifest

from typing import Any

FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSans-Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]
LAYOUTS = {
    "auto",
    "stack",
    "2+1",
    "2x2",
    "2+1+1",
    "2+1+2",
    "2+2+1",
    "2x3",
    "2+2+1+1",
    "overlap_stack",
}
BASE_LAYOUTS = LAYOUTS - {"auto", "overlap_stack"}
ANIMATIONS = {"auto", "fly_in", "row_reveal", "hero_last", "none"}
OVERLAP_RATIO_MIN = 0.30
OVERLAP_RATIO_MAX = 0.50
OVERLAP_RATIO_DEFAULT = 0.40
ROTATION_MIN_DEG_DEFAULT = 25.0
ROTATION_MAX_DEG_DEFAULT = 45.0
ROTATION_ABSOLUTE_MAX_DEG = 60.0
FINAL_ROTATION_MAX_DEG_DEFAULT = 0.0
FINAL_ROTATION_MAX_DEG_LIMIT = 10.0
RENDERER_VERSION = "1.5.0"


def run(cmd: list[str], *, capture: bool = False) -> str:
    if capture:
        return subprocess.check_output(cmd, text=True)
    subprocess.run(cmd, check=True)
    return ""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_paper_edge_mask(
    path: Path, width: int, height: int, seed: int, variation_px: int, inner_border_px: int = 1
) -> None:
    """Write a deterministic PGM matte with a torn outer contour and intact inner rim.

    The irregularity is confined to the outer card contour. An opaque one-pixel
    (or larger) inner rim is preserved so the photo always has a crisp continuous
    white line inside the organic paper edge.
    """
    if inner_border_px < 1:
        raise ValueError("inner_border_px must be at least 1")
    rng = random.Random(seed)
    step = max(5, variation_px * 3)
    top = [rng.randint(0, variation_px) for _ in range((width + step - 1) // step + 1)]
    bottom = [rng.randint(0, variation_px) for _ in range((width + step - 1) // step + 1)]
    left = [rng.randint(0, variation_px) for _ in range((height + step - 1) // step + 1)]
    right = [rng.randint(0, variation_px) for _ in range((height + step - 1) // step + 1)]

    def edge(values: list[int], pos: int) -> int:
        index = min(len(values) - 2, pos // step)
        frac = (pos % step) / step
        return round(values[index] * (1.0 - frac) + values[index + 1] * frac)

    with path.open("wb") as out:
        out.write(f"P5\n{width} {height}\n255\n".encode("ascii"))
        for y in range(height):
            ly = edge(left, y)
            ry = edge(right, y)
            row = bytearray(width)
            for x in range(width):
                tx = edge(top, x)
                bx = edge(bottom, x)
                if x >= ly and x < width - ry and y >= tx and y < height - bx:
                    row[x] = 255
            out.write(row)


def write_inner_paper_rim_mask(
    path: Path, width: int, height: int, gutter: int, seed: int, overlap_px: int
) -> None:
    """White alpha rim that softly varies 2–3px over the photo's inner edge."""
    rng = random.Random(seed)
    step = max(5, overlap_px * 3)
    top = [rng.randint(max(1, overlap_px - 1), overlap_px) for _ in range((width + step - 1) // step + 1)]
    bottom = [rng.randint(max(1, overlap_px - 1), overlap_px) for _ in range((width + step - 1) // step + 1)]
    left = [rng.randint(max(1, overlap_px - 1), overlap_px) for _ in range((height + step - 1) // step + 1)]
    right = [rng.randint(max(1, overlap_px - 1), overlap_px) for _ in range((height + step - 1) // step + 1)]

    def edge(values: list[int], pos: int) -> int:
        index = min(len(values) - 2, pos // step)
        frac = (pos % step) / step
        return round(values[index] * (1.0 - frac) + values[index + 1] * frac)

    with path.open("wb") as out:
        out.write(f"P5\n{width} {height}\n255\n".encode("ascii"))
        for y in range(height):
            ly, ry = edge(left, y), edge(right, y)
            row = bytearray(width)
            for x in range(width):
                tx, bx = edge(top, x), edge(bottom, x)
                # The white rim includes the gutter and gently overhangs the photo.
                inside_photo = gutter <= x < width - gutter and gutter <= y < height - gutter
                in_top = inside_photo and y < gutter + tx
                in_bottom = inside_photo and y >= height - gutter - bx
                in_left = inside_photo and x < gutter + ly
                in_right = inside_photo and x >= width - gutter - ry
                if in_top or in_bottom or in_left or in_right:
                    row[x] = 255
            out.write(row)


def rounded_photo_corner_boxes(width: int, height: int, gutter: int, radius: int) -> list[tuple[int, int, int, int]]:
    """One-pixel white cover boxes that round the inner photo corners, not the card."""
    if radius < 1:
        return []
    inner_w, inner_h = width - 2 * gutter, height - 2 * gutter
    boxes: list[tuple[int, int, int, int]] = []
    for dx in range(radius):
        for dy in range(radius):
            if math.hypot(radius - dx - 0.5, radius - dy - 0.5) > radius:
                for x, y in (
                    (gutter + dx, gutter + dy),
                    (gutter + inner_w - 1 - dx, gutter + dy),
                    (gutter + dx, gutter + inner_h - 1 - dy),
                    (gutter + inner_w - 1 - dx, gutter + inner_h - 1 - dy),
                ):
                    boxes.append((x, y, 1, 1))
    return boxes


def safe_path(root: Path, rel: str, *, must_exist: bool = False) -> Path:
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError("path must be a non-empty string")
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes root: {rel}") from exc
    if must_exist and not path.is_file():
        raise ValueError(f"missing source: {rel}")
    return path


def wrap_title(text: str, max_chars: int) -> str:
    words = text.split()
    if not words:
        return ""
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "\n".join(lines)


def _rows_for_layout(name: str, width: int, height: int) -> list[list[tuple[int, int, int, int]]]:
    half = width // 2
    other = width - half
    if name == "stack":
        h1 = height // 2
        return [[(0, 0, width, h1)], [(0, h1, width, height - h1)]]
    if name == "2+1":
        h1 = height // 2
        return [[(0, 0, half, h1), (half, 0, other, h1)], [(0, h1, width, height - h1)]]
    if name == "2x2":
        h1 = height // 2
        return [[(0, 0, half, h1), (half, 0, other, h1)], [(0, h1, half, height - h1), (half, h1, other, height - h1)]]
    if name == "2+1+1":
        h1 = height // 3
        h2 = height // 3
        return [[(0, 0, half, h1), (half, 0, other, h1)], [(0, h1, width, h2)], [(0, h1 + h2, width, height - h1 - h2)]]
    if name == "2+1+2":
        h1 = round(height * 650 / 1920)
        h2 = round(height * 500 / 1920)
        h3 = height - h1 - h2
        return [[(0, 0, half, h1), (half, 0, other, h1)], [(0, h1, width, h2)], [(0, h1 + h2, half, h3), (half, h1 + h2, other, h3)]]
    if name == "2+2+1":
        h1 = round(height * 620 / 1920)
        h2 = round(height * 660 / 1920)
        h3 = height - h1 - h2
        return [[(0, 0, half, h1), (half, 0, other, h1)], [(0, h1, half, h2), (half, h1, other, h2)], [(0, h1 + h2, width, h3)]]
    if name == "2x3":
        y1 = height // 3
        y2 = 2 * height // 3
        return [[(0, 0, half, y1), (half, 0, other, y1)], [(0, y1, half, y2 - y1), (half, y1, other, y2 - y1)], [(0, y2, half, height - y2), (half, y2, other, height - y2)]]
    if name == "2+2+1+1":
        ys = [round(i * height / 4) for i in range(5)]
        return [[(0, ys[0], half, ys[1] - ys[0]), (half, ys[0], other, ys[1] - ys[0])], [(0, ys[1], half, ys[2] - ys[1]), (half, ys[1], other, ys[2] - ys[1])], [(0, ys[2], width, ys[3] - ys[2])], [(0, ys[3], width, ys[4] - ys[3])]]
    raise ValueError(f"unsupported layout: {name}")


def validate_layout_geometry(cells: list[tuple[int, int, int, int]], width: int, height: int) -> None:
    """Require complete, non-overlapping final canvas coverage."""
    total = 0
    for index, (x, y, w, h) in enumerate(cells):
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width or y + h > height:
            raise ValueError(f"panel {index} is outside canvas: {(x, y, w, h)}")
        total += w * h
    for i, (ax, ay, aw, ah) in enumerate(cells):
        for j, (bx, by, bw, bh) in enumerate(cells[i + 1 :], i + 1):
            if max(ax, bx) < min(ax + aw, bx + bw) and max(ay, by) < min(ay + ah, by + bh):
                raise ValueError(f"panels {i} and {j} overlap")
    if total != width * height:
        raise ValueError(f"layout does not cover canvas exactly: {total} != {width * height}")


def default_base_layout(count: int, sources: list[dict[str, Any]], title: str) -> str:
    """Pick a heterogeneous legacy tiled layout for overlap_stack."""
    if count == 3:
        return "2+1"
    if count == 4:
        return "2+1+1"
    if count == 5:
        return "2+2+1"
    if count == 6:
        return "2+2+1+1"
    raise ValueError("overlap_stack supports 3-6 sources")


def _pair_extend(base_span: int, overlap_ratio: float) -> int:
    """Extra span for paired left/right neighbors; overlap width is 2*extend over one cell."""
    return max(1, int(round(overlap_ratio * base_span / (2.0 - overlap_ratio))))


def _unilateral_extend(neighbor_span: int, overlap_ratio: float) -> int:
    """Extra span for one-sided expansion so intersection / neighbor area ~= overlap_ratio."""
    return max(1, int(round(overlap_ratio * neighbor_span)))


def _horizontal_overlap_width(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
) -> int:
    ax, _, aw, _ = a
    bx, _, bw, _ = b
    return max(0, min(ax + aw, bx + bw) - max(ax, bx))


def _rows_from_base_cells(cells: list[tuple[int, int, int, int]]) -> list[list[tuple[int, int, int, int]]]:
    """Group flattened base cells into rows sorted top-to-bottom, left-to-right."""
    by_row: dict[int, list[tuple[int, int, int, int]]] = {}
    for cell in cells:
        by_row.setdefault(cell[1], []).append(cell)
    return [sorted(by_row[y], key=lambda c: c[0]) for y in sorted(by_row)]


def _best_above_neighbor(
    base: tuple[int, int, int, int],
    above_row: list[tuple[int, int, int, int]],
) -> tuple[int, int, int, int] | None:
    best: tuple[int, int, int, int] | None = None
    best_overlap = 0
    for cell in above_row:
        overlap = _horizontal_overlap_width(base, cell)
        if overlap > best_overlap:
            best_overlap = overlap
            best = cell
    return best


def _cell_row_neighbors(
    base_rows: list[list[tuple[int, int, int, int]]],
) -> list[tuple[int | None, int | None]]:
    """For each flattened cell index, return (left_neighbor_idx, right_neighbor_idx)."""
    neighbors: list[tuple[int | None, int | None]] = []
    index = 0
    for row in base_rows:
        for pos, _ in enumerate(row):
            left = index - 1 if pos > 0 else None
            right = index + 1 if pos < len(row) - 1 else None
            neighbors.append((left, right))
            index += 1
    return neighbors


def _expand_upward(
    rect: tuple[int, int, int, int],
    above_neighbor: tuple[int, int, int, int],
    overlap_ratio: float,
) -> tuple[int, int, int, int]:
    """Grow rect upward to overlap the row above by overlap_ratio where canvas allows."""
    rx, ry, rw, rh = rect
    if ry <= 0:
        return rect
    _, _, _, above_h = above_neighbor
    extend = _unilateral_extend(above_h, overlap_ratio)
    extend = min(extend, ry)
    return (rx, ry - extend, rw, rh + extend)


def expand_overlap_cell(
    base: tuple[int, int, int, int],
    direction: str,
    width: int,
    height: int,
    overlap_ratio: float,
    *,
    left_neighbor: tuple[int, int, int, int] | None = None,
    left_direction: str | None = None,
    right_neighbor: tuple[int, int, int, int] | None = None,
    right_direction: str | None = None,
    above_neighbor: tuple[int, int, int, int] | None = None,
) -> tuple[int, int, int, int]:
    """Expand one base cell opposite its entrance edge, anchoring the original edge."""
    bx, by, bw, bh = base
    if direction == "left":
        if right_direction == "right" and right_neighbor is not None:
            extend = _pair_extend(bw, overlap_ratio)
            rect = (bx, by, bw + extend, bh)
        else:
            extend = _unilateral_extend(bw, overlap_ratio)
            extend = min(extend, max(0, width - bx - bw))
            rect = (bx, by, bw + extend, bh)
    elif direction == "right":
        if left_direction == "left" and left_neighbor is not None:
            extend = _pair_extend(bw, overlap_ratio)
            new_w = bw + extend
            rect = (bx + bw - new_w, by, new_w, bh)
        else:
            extend = _unilateral_extend(bw, overlap_ratio)
            extend = min(extend, bx)
            rect = (bx - extend, by, bw + extend, bh)
    elif direction == "bottom":
        rect = base
    else:
        raise ValueError(f"unsupported overlap entrance edge: {direction}")
    if above_neighbor is not None:
        rect = _expand_upward(rect, above_neighbor, overlap_ratio)
    return rect


def overlap_stack_cells(
    base_cells: list[tuple[int, int, int, int]],
    base_rows: list[list[tuple[int, int, int, int]]],
    directions: list[str],
    width: int,
    height: int,
    overlap_ratio: float,
) -> list[tuple[int, int, int, int]]:
    """Expand heterogeneous base cells into overlapping cards; later indices draw above earlier ones."""
    if len(base_cells) != len(directions):
        raise ValueError("base cells and entrance directions must match")
    neighbors = _cell_row_neighbors(base_rows)
    row_lookup: list[int] = []
    for row_index, row in enumerate(base_rows):
        row_lookup.extend([row_index] * len(row))
    expanded: list[tuple[int, int, int, int]] = []
    for i, (base, direction) in enumerate(zip(base_cells, directions)):
        left_idx, right_idx = neighbors[i]
        row_index = row_lookup[i]
        above_neighbor = None
        if row_index > 0:
            above_neighbor = _best_above_neighbor(base, base_rows[row_index - 1])
        expanded.append(
            expand_overlap_cell(
                base,
                direction,
                width,
                height,
                overlap_ratio,
                left_neighbor=base_cells[left_idx] if left_idx is not None else None,
                left_direction=directions[left_idx] if left_idx is not None else None,
                right_neighbor=base_cells[right_idx] if right_idx is not None else None,
                right_direction=directions[right_idx] if right_idx is not None else None,
                above_neighbor=above_neighbor,
            )
        )
    return expanded


def _rect_contains(outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]) -> bool:
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    return ox <= ix and oy <= iy and ox + ow >= ix + iw and oy + oh >= iy + ih


def _rect_intersection(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0 = max(ax, bx)
    y0 = max(ay, by)
    x1 = min(ax + aw, bx + bw)
    y1 = min(ay + ah, by + bh)
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1 - x0, y1 - y0)


def _overlap_fraction(over: tuple[int, int, int, int], under: tuple[int, int, int, int]) -> float:
    inter = _rect_intersection(over, under)
    if inter is None:
        return 0.0
    _, _, iw, ih = inter
    _, _, uw, uh = under
    return (iw * ih) / max(1, uw * uh)


def _normalize_rect_entry(entry: Any) -> list[float]:
    if isinstance(entry, dict):
        return [float(entry["x"]), float(entry["y"]), float(entry["w"]), float(entry["h"])]
    if isinstance(entry, (list, tuple)) and len(entry) == 4:
        return [float(v) for v in entry]
    raise ValueError("base_cells entries must be [x,y,w,h] arrays or {x,y,w,h} objects")


def parse_base_cells(
    raw_cells: list[Any],
    width: int,
    height: int,
) -> list[tuple[int, int, int, int]]:
    """Parse normalized [0,1] or pixel [x,y,w,h] rects; require exact canvas coverage."""
    parsed = [_normalize_rect_entry(entry) for entry in raw_cells]
    if not parsed:
        raise ValueError("base_cells must not be empty")
    normalized = all(0.0 <= value <= 1.0 for rect in parsed for value in rect)
    if normalized:
        cells = [
            (
                int(round(rect[0] * width)),
                int(round(rect[1] * height)),
                int(round(rect[2] * width)),
                int(round(rect[3] * height)),
            )
            for rect in parsed
        ]
    else:
        cells = [
            (int(round(rect[0])), int(round(rect[1])), int(round(rect[2])), int(round(rect[3])))
            for rect in parsed
        ]
    validate_layout_geometry(cells, width, height)
    return cells


def serialize_base_cells(cells: list[tuple[int, int, int, int]], width: int, height: int) -> list[list[float]]:
    return [[x / width, y / height, w / width, h / height] for x, y, w, h in cells]


def _orientation_signature(cells: list[tuple[int, int, int, int]]) -> set[str]:
    sig: set[str] = set()
    for _, _, w, h in cells:
        ratio = w / max(1, h)
        if ratio >= 1.15:
            sig.add("landscape")
        elif ratio <= 0.87:
            sig.add("portrait")
        else:
            sig.add("square")
    return sig


def _cross_row_overlap_ratios(
    expanded: list[tuple[int, int, int, int]],
    base_rows: list[list[tuple[int, int, int, int]]],
) -> list[float]:
    """For each card below the first row, return best overlap fraction vs any card in the preceding row."""
    ratios: list[float] = []
    flat_index = 0
    for row_index, row in enumerate(base_rows):
        if row_index == 0:
            flat_index += len(row)
            continue
        prev_start = flat_index - len(base_rows[row_index - 1])
        prev_end = flat_index
        for _ in row:
            best = 0.0
            for prev_idx in range(prev_start, prev_end):
                ratio = _overlap_fraction(expanded[flat_index], expanded[prev_idx])
                best = max(best, ratio)
            ratios.append(best)
            flat_index += 1
    return ratios


def validate_overlap_stack_geometry(
    expanded: list[tuple[int, int, int, int]],
    base_cells: list[tuple[int, int, int, int]],
    width: int,
    height: int,
    overlap_ratio: float,
    *,
    base_rows: list[list[tuple[int, int, int, int]]] | None = None,
) -> dict[str, Any]:
    """Ensure overlap-stack cards fit the canvas, contain their base cells, and overlap as configured."""
    if len(expanded) < 2:
        raise ValueError("overlap_stack needs at least two cards")
    if len(expanded) != len(base_cells):
        raise ValueError("expanded and base cells must match")
    if base_rows is None:
        base_rows = _rows_from_base_cells(base_cells)
    canvas = (0, 0, width, height)
    canvas_area = width * height
    for index, (cell, base) in enumerate(zip(expanded, base_cells)):
        if not _rect_contains(cell, base):
            raise ValueError(f"overlap card {index} does not contain its base cell")
        x, y, w, h = cell
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width or y + h > height:
            raise ValueError(f"overlap card {index} is outside canvas: {(x, y, w, h)}")
        if base != canvas and cell == canvas:
            raise ValueError(f"overlap card {index} expanded to full canvas")
        if base[2] * base[3] < canvas_area and w * h >= canvas_area:
            raise ValueError(f"overlap card {index} covers the entire canvas without a full-size base cell")
    widths = {w for _, _, w, _ in expanded}
    heights = {h for _, _, _, h in expanded}
    if len(widths) == 1 and len(heights) == 1:
        raise ValueError("overlap_stack must preserve heterogeneous cell sizes, not uniform strips")
    if len(_orientation_signature(base_cells)) < 2:
        raise ValueError("overlap_stack base layout must include mixed orientations")
    overlaps: list[float] = []
    for i in range(len(expanded) - 1):
        ratio = _overlap_fraction(expanded[i + 1], expanded[i])
        if ratio > 0:
            overlaps.append(ratio)
    tolerance = 0.12
    measured = [v for v in overlaps if OVERLAP_RATIO_MIN - tolerance <= v <= OVERLAP_RATIO_MAX + tolerance]
    if overlaps and not measured:
        raise ValueError("no adjacent overlap-stack cards overlap within the configured ratio")
    cross_row = _cross_row_overlap_ratios(expanded, base_rows)
    if cross_row:
        offset = len(base_rows[0])
        for local_index, ratio in enumerate(cross_row):
            if ratio <= 0.0:
                raise ValueError(
                    f"overlap_stack card {offset + local_index} has zero cross-row overlap with preceding row"
                )
        cross_measured = [
            v for v in cross_row if OVERLAP_RATIO_MIN - tolerance <= v <= OVERLAP_RATIO_MAX + tolerance
        ]
        if not cross_measured:
            raise ValueError("no cross-row overlap-stack cards overlap within the configured ratio")
    return {
        "overlap_ratio": overlap_ratio,
        "base_cell_count": len(base_cells),
        "orientation_signature": sorted(_orientation_signature(base_cells)),
        "unique_widths": sorted(widths),
        "unique_heights": sorted(heights),
        "per_card_overlap_ratio": [round(v, 4) for v in overlaps],
        "overlap_pairs": len(overlaps),
        "cross_row_overlap_ratio": [round(v, 4) for v in cross_row],
    }


def choose_layout(count: int, sources: list[dict[str, Any]], title: str, requested: str) -> tuple[str, list[int]]:
    if not 2 <= count <= 6:
        raise ValueError("animated-collage supports 2-6 sources; split larger sets into two scenes")
    safe = [i for i, src in enumerate(sources) if bool(src.get("title_safe"))]
    if requested == "overlap_stack":
        if not 3 <= count <= 6:
            raise ValueError("overlap_stack supports 3-6 sources")
        name = "overlap_stack"
    elif requested != "auto":
        name = requested
    elif count == 2:
        name = "stack"
    elif count == 3:
        name = "2+1"
    elif count == 4:
        name = "2x2" if (not title or len(safe) >= 2) else "2+1+1"
    elif count == 5:
        name = "2+2+1"
    else:
        name = "2x3" if (not title or len(safe) >= 2) else "2+2+1+1"
    if name == "overlap_stack":
        expected = count
    else:
        expected = sum(len(row) for row in _rows_for_layout(name, 1080, 1920))
    if expected != count:
        raise ValueError(f"layout {name} expects {expected} sources, got {count}")
    order = list(range(count))
    if title:
        if not safe:
            raise ValueError("title requires at least one source with title_safe=true")
        if name == "overlap_stack":
            order = [i for i in order if i not in safe] + safe
        else:
            last_cells = len(_rows_for_layout(name, 1080, 1920)[-1])
            need = last_cells
            if len(safe) < need:
                raise ValueError(f"layout {name} needs {need} title_safe source(s) in its bottom row; got {len(safe)}")
            bottom = safe[-need:]
            order = [i for i in order if i not in bottom] + bottom
    return name, order


def choose_animation(requested: str, layout: str, sources: list[dict[str, Any]]) -> str:
    if requested != "auto":
        return requested
    if any(bool(s.get("hero")) for s in sources) or layout in {"stack", "2+1"}:
        return "hero_last"
    if layout in {"2x2", "2x3", "2+2+1", "2+2+1+1"}:
        return "row_reveal"
    if layout == "overlap_stack":
        return "fly_in"
    return "fly_in"


def overlap_entrance_directions(base_rows: list[list[tuple[int, int, int, int]]]) -> list[str]:
    """Assign entrance edges from base-row geometry so paired cells expand toward each other."""
    directions: list[str] = []
    for row in base_rows:
        if len(row) == 1:
            directions.append("bottom")
            continue
        for col in range(len(row)):
            directions.append("left" if col % 2 == 0 else "right")
    return directions


def _ease_expr(t: str) -> str:
    return f"(1-pow(1-({t}),3))"


def entry_schedule(rows: list[list[tuple[int, int, int, int]]], animation: str, entry_seconds: float) -> list[tuple[float, float, str]]:
    cells = [cell for row in rows for cell in row]
    n = len(cells)
    travel = min(0.70, max(0.35, entry_seconds * 0.38))
    schedule: list[tuple[float, float, str]] = []
    if animation == "none":
        return [(0.0, 0.0, "none") for _ in cells]
    if animation == "row_reveal":
        row_count = len(rows)
        for row_index, row in enumerate(rows):
            start = 0.0 if row_count == 1 else row_index * max(0.0, entry_seconds - travel) / (row_count - 1)
            for col, _ in enumerate(row):
                direction = "bottom" if len(row) == 1 else ("left" if col % 2 == 0 else "right")
                schedule.append((start, min(entry_seconds, start + travel), direction))
        return schedule
    if animation == "hero_last":
        for i, cell in enumerate(cells):
            if i == n - 1:
                start = max(0.0, entry_seconds - travel)
                direction = "bottom"
            else:
                span = max(0.0, entry_seconds * 0.55 - travel)
                start = 0.0 if n <= 2 else i * span / max(1, n - 2)
                direction = "left" if i % 2 == 0 else "right"
            schedule.append((start, min(entry_seconds, start + travel), direction))
        return schedule
    # fly_in
    for i, cell in enumerate(cells):
        start = 0.0 if n == 1 else i * max(0.0, entry_seconds - travel) / (n - 1)
        direction = "bottom" if cell[2] == max(c[2] for c in cells) and i == n - 1 else ("left" if i % 2 == 0 else "right")
        schedule.append((start, min(entry_seconds, start + travel), direction))
    return schedule


def rotation_canvas_size(width: int, height: int, angle_deg: float) -> tuple[int, int]:
    """Bounding box for a width x height card rotated by angle_deg (absolute value)."""
    rad = math.radians(abs(angle_deg))
    cos_a = abs(math.cos(rad))
    sin_a = abs(math.sin(rad))
    ow = int(math.ceil(width * cos_a + height * sin_a))
    oh = int(math.ceil(width * sin_a + height * cos_a))
    return max(ow, width), max(oh, height)


def rotation_safe_cells(
    cells: list[tuple[int, int, int, int]],
    panel_rotations: list[dict[str, Any]],
    canvas_width: int,
    canvas_height: int,
    *,
    padding_px: int = 2,
) -> list[tuple[int, int, int, int]]:
    """Shift resting card centers so final rotated pixels stay inside canvas."""
    if len(cells) != len(panel_rotations):
        raise ValueError("rotation safe-cell count mismatch")
    safe: list[tuple[int, int, int, int]] = []
    for index, ((x, y, w, h), rotation) in enumerate(zip(cells, panel_rotations), 1):
        final_angle = abs(float(rotation.get("final_angle_deg", 0.0)))
        bbox_w, bbox_h = rotation_canvas_size(w, h, final_angle)
        active_padding = padding_px if final_angle > 1e-9 else 0
        inset_x = math.ceil((bbox_w - w) / 2) + active_padding
        inset_y = math.ceil((bbox_h - h) / 2) + active_padding
        min_x, max_x = inset_x, canvas_width - w - inset_x
        min_y, max_y = inset_y, canvas_height - h - inset_y
        if min_x > max_x or min_y > max_y:
            rotation["requested_final_angle_deg"] = rotation.get("final_angle_deg", 0.0)
            rotation["final_angle_deg"] = 0.0
            rotation["final_sign_policy"] = "zeroed-to-fit-canvas"
            inset_x = inset_y = 0
            min_x, max_x = 0, canvas_width - w
            min_y, max_y = 0, canvas_height - h
            if min_x > max_x or min_y > max_y:
                raise ValueError(f"panel {index} cannot fit inside canvas even without rotation")
        safe.append((min(max(x, min_x), max_x), min(max(y, min_y), max_y), w, h))
    return safe


def _sample_final_signed_angle(rng: random.Random, max_deg: float) -> float:
    """Uniform signed angle in [-max_deg, max_deg]; retry once away from near-zero when practical."""
    angle = rng.uniform(-max_deg, max_deg)
    if max_deg > 0.0 and abs(angle) < 0.05:
        angle = rng.uniform(-max_deg, max_deg)
        if abs(angle) < 0.05 and max_deg >= 0.05:
            sign = -1.0 if angle < 0 else 1.0
            angle = sign * rng.uniform(0.05, max_deg)
    return angle


def assign_panel_rotations(
    count: int,
    seed: int,
    min_deg: float,
    max_deg: float,
    final_rotation_max_deg: float = FINAL_ROTATION_MAX_DEG_DEFAULT,
) -> list[dict[str, Any]]:
    """Deterministically assign signed start and final angles per panel from one RNG stream."""
    rng = random.Random(seed)
    panels: list[dict[str, Any]] = []
    first_final_sign: float | None = None
    for index in range(count):
        magnitude = rng.uniform(min_deg, max_deg)
        clockwise = rng.random() < 0.5
        signed = -magnitude if clockwise else magnitude
        direction = "clockwise" if clockwise else "counterclockwise"
        final_angle = 0.0
        if final_rotation_max_deg > 0.0:
            sampled_final = _sample_final_signed_angle(rng, final_rotation_max_deg)
            if first_final_sign is None:
                first_final_sign = -1.0 if sampled_final < 0 else 1.0
            final_sign = first_final_sign if index % 2 == 0 else -first_final_sign
            final_angle = final_sign * abs(sampled_final)
        panels.append(
            {
                "seed": seed,
                "start_angle_deg": round(signed, 4),
                "rotation_direction": direction,
                "final_angle_deg": round(final_angle, 4),
                "final_sign_policy": "alternating-per-collage" if final_rotation_max_deg > 0.0 else "zero",
            }
        )
    return panels


def rotation_angle_expr(
    start_angle_deg: float,
    final_angle_deg: float,
    timing: tuple[float, float, str],
) -> str:
    """FFmpeg radians expression: eased from start_angle at entrance begin to final_angle by entrance end."""
    start, end, direction = timing
    if direction == "none" or end <= start:
        if abs(final_angle_deg) < 1e-9:
            return "0"
        return f"{final_angle_deg * math.pi / 180.0:.8f}"
    if abs(start_angle_deg - final_angle_deg) < 1e-9:
        if abs(start_angle_deg) < 1e-9:
            return "0"
        start_rad = start_angle_deg * math.pi / 180.0
        return f"{start_rad:.8f}"
    start_rad = start_angle_deg * math.pi / 180.0
    final_rad = final_angle_deg * math.pi / 180.0
    progress = f"(t-{start:.3f})/{end-start:.3f}"
    eased = _ease_expr(progress)
    return (
        f"if(lt(t,{start:.3f}),{start_rad:.8f},"
        f"if(lt(t,{end:.3f}),{start_rad:.8f}+({final_rad:.8f}-{start_rad:.8f})*({eased}),{final_rad:.8f}))"
    )


def overlay_enable_option(timing: tuple[float, float, str]) -> str:
    """FFmpeg overlay enable clause: keep panel fully hidden until entrance.start."""
    start, _, _ = timing
    if start <= 0.0:
        return ""
    return f":enable='gte(t,{start:.3f})'"


def build_panel_overlay_graph(
    cells: list[tuple[int, int, int, int]],
    schedule: list[tuple[float, float, str]],
    panel_rotations: list[dict[str, Any]] | None,
    width: int,
    height: int,
) -> tuple[list[str], str]:
    """Build rotate/overlay filter segments for all panels; returns (lines, final_label)."""
    graph: list[str] = []
    previous = "0:v"
    for i, (cell, timing) in enumerate(zip(cells, schedule), 1):
        xexpr, yexpr = motion_expr(cell, timing, width, height)
        out = f"o{i}"
        enable = overlay_enable_option(timing)
        _, _, card_w, card_h = cell
        rotation = panel_rotations[i - 1] if panel_rotations else None
        if rotation is not None:
            start_angle = float(rotation["start_angle_deg"])
            final_angle = float(rotation.get("final_angle_deg", 0.0))
            angle_expr = rotation_angle_expr(start_angle, final_angle, timing)
            rotated = f"r{i}"
            canvas_w, canvas_h = rotation_canvas_size(
                card_w, card_h, max(abs(start_angle), abs(final_angle))
            )
            graph.append(
                f"[{i}:v]format=rgba,rotate=a='{angle_expr}':ow={canvas_w}:oh={canvas_h}:"
                f"fillcolor=0x00000000[{rotated}]"
            )
            ox = f"({xexpr})+{card_w}/2-w/2"
            oy = f"({yexpr})+{card_h}/2-h/2"
            graph.append(f"[{previous}][{rotated}]overlay=x='{ox}':y='{oy}':eval=frame{enable}[{out}]")
        else:
            graph.append(f"[{previous}][{i}:v]overlay=x='{xexpr}':y='{yexpr}':eval=frame{enable}[{out}]")
        previous = out
    return graph, previous


def motion_expr(cell: tuple[int, int, int, int], timing: tuple[float, float, str], width: int, height: int) -> tuple[str, str]:
    x, y, w, h = cell
    start, end, direction = timing
    if direction == "none" or end <= start:
        return str(x), str(y)
    progress = f"(t-{start:.3f})/{end-start:.3f}"
    eased = _ease_expr(progress)
    if direction == "left":
        xexpr = f"if(lt(t,{start:.3f}),{-w},if(lt(t,{end:.3f}),{-w}+({x+w})*{eased},{x}))"
        return xexpr, str(y)
    if direction == "right":
        xexpr = f"if(lt(t,{start:.3f}),{width},if(lt(t,{end:.3f}),{width}-({width-x})*{eased},{x}))"
        return xexpr, str(y)
    yexpr = f"if(lt(t,{start:.3f}),{height},if(lt(t,{end:.3f}),{height}-({height-y})*{eased},{y}))"
    return str(x), yexpr


def _drawtext_coord(value: str) -> str:
    s = str(value).strip()
    if s.startswith("'") and s.endswith("'"):
        return s
    try:
        float(s)
        return s
    except ValueError:
        return f"'{s}'"


def _find_font() -> Path | None:
    return next((path for path in FONT_CANDIDATES if path.is_file()), None)


def default_entry_seconds(raw: dict[str, Any], source_count: int, duration: float) -> float:
    if "entry_seconds" in raw:
        return float(raw["entry_seconds"])
    layout = str(raw.get("layout", "auto"))
    if layout == "overlap_stack" and source_count >= 3 and duration == 5.0:
        return 4.0
    return 2.0


def validate_spec(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    result = dict(raw)
    sources = result.get("sources")
    if not isinstance(sources, list) or not all(isinstance(s, dict) for s in sources):
        raise ValueError("sources must be a list of objects")
    if not 2 <= len(sources) <= 6:
        raise ValueError("sources must contain 2-6 images")
    for i, src in enumerate(sources):
        if not isinstance(src.get("path"), str) or not src["path"].strip():
            raise ValueError(f"sources[{i}].path must be non-empty")
        for key in ("focus_x", "focus_y"):
            value = float(src.get(key, 0.5))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"sources[{i}].{key} must be in [0,1]")
            src[key] = value
    result["width"] = int(result.get("width", 1080))
    result["height"] = int(result.get("height", 1920))
    result["fps"] = int(result.get("fps", 30))
    result["duration"] = float(result.get("duration", 5.0))
    result["entry_seconds"] = default_entry_seconds(raw, len(sources), float(result["duration"]))
    result["gutter"] = int(result.get("gutter", 6))
    if result["width"] < 240 or result["height"] < 320 or result["fps"] < 1:
        raise ValueError("invalid output dimensions or fps")
    if not 0.0 <= result["entry_seconds"] < result["duration"]:
        raise ValueError("entry_seconds must be non-negative and less than duration")
    if result["duration"] - result["entry_seconds"] < 1.0:
        raise ValueError("completed collage must hold for at least 1 second")
    if not 0 <= result["gutter"] <= 24:
        raise ValueError("gutter must be in [0,24]")
    result["paper_edge"] = bool(raw.get("paper_edge", False))
    if result["paper_edge"]:
        if "paper_edge_seed" not in raw:
            raise ValueError("paper_edge_seed is required when paper_edge=true")
        result["paper_edge_seed"] = int(raw["paper_edge_seed"])
        result["paper_edge_variation_px"] = int(raw.get("paper_edge_variation_px", 3))
        result["paper_edge_inner_border_px"] = int(raw.get("paper_edge_inner_border_px", 1))
        result["paper_edge_inner_overlap_px"] = int(raw.get("paper_edge_inner_overlap_px", 0))
        if not 1 <= result["paper_edge_variation_px"] <= 8:
            raise ValueError("paper_edge_variation_px must be in [1,8]")
        if not 1 <= result["paper_edge_inner_border_px"] <= result["gutter"]:
            raise ValueError("paper_edge_inner_border_px must be in [1,gutter]")
        if not 0 <= result["paper_edge_inner_overlap_px"] <= 8:
            raise ValueError("paper_edge_inner_overlap_px must be in [0,8]")
        if result["paper_edge_variation_px"] > result["gutter"] - result["paper_edge_inner_border_px"]:
            raise ValueError("paper_edge_variation_px must leave the requested inner white border")
    elif any(key in raw for key in ("paper_edge_seed", "paper_edge_variation_px", "paper_edge_inner_border_px", "paper_edge_inner_overlap_px")):
        raise ValueError("paper_edge settings require paper_edge=true")
    result["photo_corner_radius_px"] = int(raw.get("photo_corner_radius_px", 0))
    if not 0 <= result["photo_corner_radius_px"] <= 8:
        raise ValueError("photo_corner_radius_px must be in [0,8]")
    if result["photo_corner_radius_px"] > result["gutter"]:
        raise ValueError("photo_corner_radius_px cannot exceed gutter")
    result["layout"] = str(result.get("layout", "auto"))
    result["animation"] = str(result.get("animation", "auto"))
    if result["layout"] not in LAYOUTS:
        raise ValueError(f"unsupported layout: {result['layout']}")
    if result["animation"] not in ANIMATIONS:
        raise ValueError(f"unsupported animation: {result['animation']}")
    if "overlap_ratio" in raw and result["layout"] != "overlap_stack":
        raise ValueError("overlap_ratio is only valid with layout overlap_stack")
    if "base_layout" in raw and result["layout"] != "overlap_stack":
        raise ValueError("base_layout is only valid with layout overlap_stack")
    if "base_cells" in raw and result["layout"] != "overlap_stack":
        raise ValueError("base_cells is only valid with layout overlap_stack")
    if result["layout"] == "overlap_stack":
        ratio = float(raw.get("overlap_ratio", OVERLAP_RATIO_DEFAULT))
        if not OVERLAP_RATIO_MIN <= ratio <= OVERLAP_RATIO_MAX:
            raise ValueError(f"overlap_ratio must be in [{OVERLAP_RATIO_MIN:.2f}, {OVERLAP_RATIO_MAX:.2f}]")
        result["overlap_ratio"] = ratio
        if "base_cells" in raw:
            if "base_layout" in raw and str(raw.get("base_layout", "auto")) != "auto":
                raise ValueError("base_cells cannot be combined with explicit base_layout")
            raw_cells = raw["base_cells"]
            if not isinstance(raw_cells, list) or not raw_cells:
                raise ValueError("base_cells must be a non-empty array")
            cells = parse_base_cells(raw_cells, result["width"], result["height"])
            if len(cells) != len(sources):
                raise ValueError(f"base_cells length {len(cells)} must match source count {len(sources)}")
            result["base_cells"] = serialize_base_cells(cells, result["width"], result["height"])
            result["base_layout"] = "custom"
        else:
            base_layout = str(raw.get("base_layout", "auto"))
            if base_layout == "auto":
                raw_title = result.get("title", "")
                title_text = raw_title.strip() if isinstance(raw_title, str) else str(raw_title.get("text", "")).strip() if isinstance(raw_title, dict) else ""
                base_layout = default_base_layout(len(sources), sources, title_text)
            if base_layout not in BASE_LAYOUTS:
                raise ValueError(f"unsupported base_layout: {base_layout}")
            expected = sum(len(row) for row in _rows_for_layout(base_layout, 1080, 1920))
            if expected != len(sources):
                raise ValueError(f"base_layout {base_layout} expects {expected} sources, got {len(sources)}")
            result["base_layout"] = base_layout
    rotation_fields = (
        "rotation_enabled",
        "rotation_min_deg",
        "rotation_max_deg",
        "final_rotation_max_deg",
        "seed",
    )
    if any(key in raw for key in rotation_fields) and result["layout"] != "overlap_stack":
        raise ValueError("rotation fields are only valid with layout overlap_stack")
    result["rotation_enabled"] = bool(raw.get("rotation_enabled", False))
    if result["rotation_enabled"]:
        if result["layout"] != "overlap_stack":
            raise ValueError("rotation_enabled requires layout overlap_stack")
        if "seed" not in raw:
            raise ValueError("seed is required when rotation_enabled is true")
        result["seed"] = int(raw["seed"])
        min_deg = float(raw.get("rotation_min_deg", ROTATION_MIN_DEG_DEFAULT))
        max_deg = float(raw.get("rotation_max_deg", ROTATION_MAX_DEG_DEFAULT))
        if not 0.0 <= min_deg <= max_deg <= ROTATION_ABSOLUTE_MAX_DEG:
            raise ValueError(
                f"rotation degrees must satisfy 0 <= rotation_min_deg <= rotation_max_deg <= {ROTATION_ABSOLUTE_MAX_DEG:.0f}"
            )
        result["rotation_min_deg"] = min_deg
        result["rotation_max_deg"] = max_deg
        final_max = float(raw.get("final_rotation_max_deg", FINAL_ROTATION_MAX_DEG_DEFAULT))
        if not 0.0 <= final_max <= FINAL_ROTATION_MAX_DEG_LIMIT:
            raise ValueError(
                f"final_rotation_max_deg must be in [0, {FINAL_ROTATION_MAX_DEG_LIMIT:.0f}]"
            )
        result["final_rotation_max_deg"] = final_max
    else:
        if "rotation_min_deg" in raw or "rotation_max_deg" in raw:
            raise ValueError("rotation_min_deg and rotation_max_deg require rotation_enabled=true")
        if "final_rotation_max_deg" in raw:
            raise ValueError("final_rotation_max_deg requires rotation_enabled=true")
        if "seed" in raw:
            raise ValueError("seed requires rotation_enabled=true")
    title = result.get("title", {})
    if isinstance(title, str):
        title = {"text": title}
    if not isinstance(title, dict):
        raise ValueError("title must be an object or string")
    title.setdefault("text", "")
    title.setdefault("max_chars", 25)
    canonical_title = style_manifest(result["width"])
    title.setdefault("font_size", int(canonical_title["font_size"]))
    title.setdefault("align", "center")
    if title["align"] not in {"left", "center", "right"}:
        raise ValueError("title.align must be left, center or right")
    result["title"] = title
    result["overwrite"] = bool(result.get("overwrite", False))
    return result


def render(root: Path, raw: dict[str, Any]) -> dict[str, Any]:
    root = root.resolve()
    spec = validate_spec(raw)
    output = safe_path(root, str(spec.get("output", "")))
    if output.exists() and not spec["overwrite"]:
        raise ValueError(f"output exists and overwrite=false: {output.relative_to(root)}")
    source_paths = [safe_path(root, src["path"], must_exist=True) for src in spec["sources"]]
    title_text = str(spec["title"].get("text", "")).strip()
    layout, order = choose_layout(len(source_paths), spec["sources"], title_text, spec["layout"])
    ordered_sources = [spec["sources"][i] for i in order]
    ordered_paths = [source_paths[i] for i in order]
    overlap_meta: dict[str, Any] | None = None
    base_cells: list[tuple[int, int, int, int]] | None = None
    panel_rotations: list[dict[str, Any]] | None = None
    render_cells: list[tuple[int, int, int, int]] | None = None
    if layout == "overlap_stack":
        overlap_ratio = float(spec["overlap_ratio"])
        if "base_cells" in spec:
            base_cells = parse_base_cells(spec["base_cells"], spec["width"], spec["height"])
            base_rows = _rows_from_base_cells(base_cells)
            base_layout_name = "custom"
        else:
            base_layout_name = str(spec["base_layout"])
            base_rows = _rows_for_layout(base_layout_name, spec["width"], spec["height"])
            base_cells = [cell for row in base_rows for cell in row]
        animation = choose_animation(spec["animation"], layout, ordered_sources)
        schedule = entry_schedule(base_rows, animation, spec["entry_seconds"])
        directions = overlap_entrance_directions(base_rows)
        schedule = [(start, end, directions[i]) for i, (start, end, _) in enumerate(schedule)]
        cells = overlap_stack_cells(
            base_cells, base_rows, directions, spec["width"], spec["height"], overlap_ratio
        )
        overlap_meta = validate_overlap_stack_geometry(
            cells, base_cells, spec["width"], spec["height"], overlap_ratio, base_rows=base_rows
        )
        overlap_meta["base_layout"] = base_layout_name
        if "base_cells" in spec:
            overlap_meta["base_cells"] = spec["base_cells"]
        if spec.get("rotation_enabled"):
            panel_rotations = assign_panel_rotations(
                len(cells),
                int(spec["seed"]),
                float(spec["rotation_min_deg"]),
                float(spec["rotation_max_deg"]),
                float(spec.get("final_rotation_max_deg", FINAL_ROTATION_MAX_DEG_DEFAULT)),
            )
            overlap_meta["rotation"] = {
                "enabled": True,
                "seed": int(spec["seed"]),
                "rotation_min_deg": float(spec["rotation_min_deg"]),
                "rotation_max_deg": float(spec["rotation_max_deg"]),
                "final_rotation_max_deg": float(spec.get("final_rotation_max_deg", FINAL_ROTATION_MAX_DEG_DEFAULT)),
                "panels": panel_rotations,
            }
            edge_padding = int(spec["paper_edge_variation_px"]) + 2 if spec["paper_edge"] else 2
            render_cells = rotation_safe_cells(
                cells, panel_rotations, spec["width"], spec["height"], padding_px=edge_padding
            )
            overlap_meta["rotation"]["render_cells"] = [list(cell) for cell in render_cells]
        rows = [cells]
    else:
        rows = _rows_for_layout(layout, spec["width"], spec["height"])
        cells = [cell for row in rows for cell in row]
        validate_layout_geometry(cells, spec["width"], spec["height"])
        animation = choose_animation(spec["animation"], layout, ordered_sources)
        schedule = entry_schedule(rows, animation, spec["entry_seconds"])

    if render_cells is None:
        render_cells = cells

    work = safe_path(root, str(spec.get("work_dir", f"derived/{output.stem}")))
    work.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    preview_dir = safe_path(root, str(spec.get("preview_dir", "previews")))
    preview_dir.mkdir(parents=True, exist_ok=True)

    # The background may only reveal content that has already entered. Using a later
    # title-safe source here leaks a future card before its scheduled entrance.
    bg_index = 0
    bg_src = ordered_sources[bg_index]
    bg = work / "background.jpg"
    bg_filter = (
        f"scale={spec['width']}:{spec['height']}:force_original_aspect_ratio=increase,"
        f"crop={spec['width']}:{spec['height']}:x=(iw-ow)*{bg_src.get('focus_x',0.5):.4f}:y=(ih-oh)*{bg_src.get('focus_y',0.5):.4f},"
        "eq=brightness=-0.40:saturation=0.72"
    )
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(ordered_paths[bg_index]), "-vf", bg_filter, "-frames:v", "1", "-update", "1", str(bg)])

    cards: list[Path] = []
    for i, (src, path, cell) in enumerate(zip(ordered_sources, ordered_paths, cells), 1):
        _, _, w, h = cell
        inner_w = w - 2 * spec["gutter"]
        inner_h = h - 2 * spec["gutter"]
        if inner_w < 32 or inner_h < 32:
            raise ValueError("gutter leaves no usable panel area")
        card = work / f"card-{i:02d}.png"
        crop = (
            f"scale={inner_w}:{inner_h}:force_original_aspect_ratio=increase,"
            f"crop={inner_w}:{inner_h}:x=(iw-ow)*{src.get('focus_x',0.5):.4f}:y=(ih-oh)*{src.get('focus_y',0.5):.4f},"
            "format=rgba"
        )
        if spec["gutter"]:
            # Keep paper construction in RGBA. Subsampled YUV padding allows
            # photo chroma to bleed into the nominal white gutter, appearing
            # as a dark seam between the inner and outer paper frame.
            crop += f",pad={w}:{h}:{spec['gutter']}:{spec['gutter']}:color=white"
        for cx, cy, cw, ch in rounded_photo_corner_boxes(
            w, h, spec["gutter"], spec["photo_corner_radius_px"]
        ):
            crop += f",drawbox=x={cx}:y={cy}:w={cw}:h={ch}:color=white:t=fill"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-vf", crop, "-frames:v", "1", "-update", "1", str(card)])
        if spec["paper_edge"] and spec["paper_edge_inner_overlap_px"]:
            rim_mask = work / f"card-{i:02d}-paper-inner-rim.pgm"
            write_inner_paper_rim_mask(
                rim_mask, w, h, spec["gutter"], int(spec["paper_edge_seed"]) + 10_000 + i - 1,
                int(spec["paper_edge_inner_overlap_px"]),
            )
            rim = work / f"card-{i:02d}-paper-inner-rim.png"
            run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color=white:s={w}x{h}",
                "-i", str(rim_mask), "-filter_complex", "[0:v]format=rgba[c];[1:v]format=gray[m];[c][m]alphamerge",
                "-frames:v", "1", "-update", "1", str(rim),
            ])
            rimmed = work / f"card-{i:02d}-paper-rimmed.png"
            run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(card), "-i", str(rim),
                "-filter_complex", "[0:v][1:v]overlay=format=auto", "-frames:v", "1", "-update", "1", str(rimmed),
            ])
            card = rimmed
        if spec["paper_edge"]:
            mask = work / f"card-{i:02d}-paper-edge.pgm"
            write_paper_edge_mask(
                mask, w, h, int(spec["paper_edge_seed"]) + i - 1, int(spec["paper_edge_variation_px"]),
                int(spec["paper_edge_inner_border_px"]),
            )
            paper_card = work / f"card-{i:02d}-paper.png"
            run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(card), "-i", str(mask),
                "-filter_complex", "[0:v]format=rgba[c];[1:v]format=gray[m];[c][m]alphamerge",
                "-frames:v", "1", "-update", "1", str(paper_card),
            ])
            card = paper_card
        cards.append(card)

    graph, previous = build_panel_overlay_graph(
        render_cells, schedule, panel_rotations, spec["width"], spec["height"]
    )
    font = _find_font()
    title_rendered = bool(title_text and font)
    if title_rendered:
        title_file = work / "title.txt"
        title_file.write_text(wrap_title(title_text, int(spec["title"]["max_chars"])), encoding="utf-8")
        align = spec["title"]["align"]
        canonical_title = style_manifest(spec["width"])
        box_border = int(canonical_title["box_border"])
        safe = ffmpeg_expressions("lower_fifth", box_border)
        xexpr = _drawtext_coord(safe["x"])
        yexpr = _drawtext_coord(safe["y"])
        line_spacing = int(canonical_title["line_spacing"])
        box_color = str(canonical_title["box_color"])
        graph.append(
            f"[{previous}]drawtext=fontfile='{font}':textfile='{title_file}':"
            f"fontcolor=white:fontsize={int(spec['title']['font_size'])}:line_spacing={line_spacing}:x={xexpr}:"
            f"y={yexpr}:"
            f"box=1:boxcolor={box_color}:boxborderw={box_border},setparams=range=limited,format=yuv420p[v]"
        )
    else:
        graph.append(f"[{previous}]setparams=range=limited,format=yuv420p[v]")

    temp_output = output.with_name(f".{output.stem}.{os.getpid()}.tmp{output.suffix}")
    temp_output.unlink(missing_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for path in [bg, *cards]:
        cmd += ["-loop", "1", "-framerate", str(spec["fps"]), "-t", str(spec["duration"]), "-i", str(path)]
    cmd += ["-filter_complex", ";".join(graph), "-map", "[v]", "-an", "-r", str(spec["fps"]), "-t", str(spec["duration"]), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temp_output)]
    try:
        run(cmd)
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(temp_output), "-f", "null", "-"])
        run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height", "-of", "json", str(temp_output)], capture=True)
        temp_output.replace(output)
    finally:
        temp_output.unlink(missing_ok=True)

    qa_times = {
        "mid_entry": max(0.05, spec["entry_seconds"] / 2),
        "arrived": min(spec["duration"] - 0.2, spec["entry_seconds"] + 0.1),
        "last": max(0.05, spec["duration"] - 0.2),
    }
    qa: dict[str, str] = {}
    hashes: list[str] = []
    for label, seconds in qa_times.items():
        target = preview_dir / f"{output.stem}-{label}.jpg"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{seconds:.3f}", "-i", str(output), "-frames:v", "1", "-update", "1", str(target)])
        qa[label] = str(target.relative_to(root))
        hashes.append(sha256(target))
    last_copy = output.with_name(f"{output.stem}-last.jpg")
    last_preview = root / qa["last"]
    last_copy.write_bytes(last_preview.read_bytes())
    contact = preview_dir / f"{output.stem}-contact.jpg"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(output), "-vf", f"fps=1,scale={max(120,spec['width']//4)}:-2,tile={max(2,math.ceil(spec['duration']))}x1", "-frames:v", "1", "-update", "1", str(contact)])

    probe = json.loads(run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,width,height,r_frame_rate,pix_fmt,nb_frames", "-of", "json", str(output)], capture=True))
    stream = probe["streams"][0]
    if (stream["width"], stream["height"]) != (spec["width"], spec["height"]):
        raise ValueError("encoded dimensions do not match spec")
    source_hashes = [sha256(path) for path in ordered_paths]
    panel_report = []
    for idx, (src, cell, layout_cell, timing, digest) in enumerate(zip(ordered_sources, render_cells, cells, schedule, source_hashes)):
        panel: dict[str, Any] = {
            "source": src["path"], "sha256": digest, "rect": list(cell),
            "focus_x": src.get("focus_x", 0.5), "focus_y": src.get("focus_y", 0.5),
            "title_safe": bool(src.get("title_safe")), "hero": bool(src.get("hero")),
            "entrance": {"start": timing[0], "end": timing[1], "edge": timing[2]},
        }
        if base_cells is not None:
            panel["base_rect"] = list(base_cells[idx])
        if cell != layout_cell:
            panel["layout_rect"] = list(layout_cell)
        if panel_rotations is not None:
            rot = panel_rotations[idx]
            panel["rotation"] = {
                "seed": rot["seed"],
                "start_angle_deg": rot["start_angle_deg"],
                "rotation_direction": rot["rotation_direction"],
                "final_angle_deg": rot["final_angle_deg"],
            }
            _, _, pw, ph = cell
            start_abs = abs(float(rot["start_angle_deg"]))
            final_abs = abs(float(rot["final_angle_deg"]))
            canvas_w, canvas_h = rotation_canvas_size(pw, ph, max(start_abs, final_abs))
            panel["rotation"]["canvas"] = [canvas_w, canvas_h]
        panel_report.append(panel)
    report = {
        "schema_version": 1,
        "renderer_version": RENDERER_VERSION,
        "status": "ok",
        "output": str(output.relative_to(root)),
        "sha256": sha256(output),
        "width": stream["width"],
        "height": stream["height"],
        "fps": stream["r_frame_rate"],
        "duration": float(probe["format"]["duration"]),
        "codec": stream["codec_name"],
        "pixel_format": stream.get("pix_fmt"),
        "frame_count": int(stream["nb_frames"]) if stream.get("nb_frames", "").isdigit() else None,
        "decodable": True,
        "audio": False,
        "layout_requested": spec["layout"],
        "layout_selected": layout,
        "base_layout": spec.get("base_layout"),
        "animation_requested": spec["animation"],
        "animation_selected": animation,
        "entry_seconds": spec["entry_seconds"],
        "hold_seconds": spec["duration"] - spec["entry_seconds"],
        "entry_seconds_defaulted": "entry_seconds" not in raw,
        "source_order": [src["path"] for src in ordered_sources],
        "source_hashes": source_hashes,
        "panels": panel_report,
        "normalized_spec": spec,
        "title": title_text,
        "title_rendered": title_rendered,
        "title_zone": "lower-fifth over bottom title-safe row" if title_text else None,
        "motion_detected": len(set(hashes)) > 1 if animation != "none" else True,
        "qa_frames": qa,
        "last_frame": str(last_copy.relative_to(root)),
        "contact_sheet": str(contact.relative_to(root)),
        "visual_review": "pending",
    }
    if overlap_meta is not None:
        report["overlap"] = overlap_meta
    report_path = output.with_name(f"{output.stem}-report.json")
    temp_report = report_path.with_name(f".{report_path.name}.{os.getpid()}.tmp")
    temp_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_report.replace(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    args = parser.parse_args()
    try:
        raw = json.loads(args.spec.read_text(encoding="utf-8"))
        report = render(args.root, raw)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"schema_version": 1, "status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
