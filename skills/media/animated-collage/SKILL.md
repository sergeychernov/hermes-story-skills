---
name: animated-collage
description: Use when rendering 2-6 photos as an animated collage.
version: 1.6.0
author: Sergey Chernov / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [collage, animation, ffmpeg, photos, vertical-video, qa]
    related_skills: [story, photo-story-archive, still-image-animation, collage-layout-design]
---

# Animated Collage

## Overview

Turn **2-6 archived photos** into one deterministic, independently playable animated collage. The skill derives the displayed portrait/landscape sequence, resolves it through an executable layout catalog, chooses an entrance preset from narrative emphasis, performs focal crops, renders a lower-fifth title only over a declared safe panel, and emits an MP4, report, representative frames, final frame, and contact sheet.

This is the reusable multi-image renderer missing between `story` and `still-image-animation`:

- `story` owns scene order, title choices, approval gates, and manifest state;
- `photo-story-archive` owns original preservation and provenance;
- `animated-collage` owns multi-panel geometry, motion, render, and QA;
- `still-image-animation` remains the renderer for a single photo;
- publication remains a separate explicit approval gate.

## When to use

Use when:

- 2-6 photos belong to one narrative beat and should appear in one vertical scene;
- the user asks for a collage, animated collage, montage card, or multi-photo Story;
- panel order, focal crops, faces, title zone, and entry motion must be reproducible.

Do not use for:

- one photo: use `still-image-animation`;
- more than six important photos: split at a semantic boundary into two scenes unless the user explicitly requests a very dense contact sheet;
- assembling a complete story, adding music, or publishing: return the verified scene to `story`.

## Workflow

### 1. Preserve and inspect inputs

Load `photo-story-archive`, copy originals without recompression, and verify hashes before rendering. Inspect every image and record:

- `focus_x`, `focus_y` in `[0,1]` around the visual anchor;
- `title_safe: true` only when the lower part can carry text without covering a face, food, signage, or key action;
- `hero: true` for at most one image whose appearance should be the payoff.

Completion criterion: every source exists under the chosen media root and every important face/object has a deliberate focal point.

### 2. Choose layout

Prefer `layout: auto`. The renderer probes displayed source dimensions in source order (`p` when width `<` height, `l` when width `>=` height) and calls [`scripts/layout_selector.py`](scripts/layout_selector.py):

```python
select_layout("ppl")  # -> "2+1"
```

The selector is the canonical executable contract; source count alone never chooses a layout. Its production catalog initially contains only renderable geometry:

| Orientation sequence | Canonical layout |
|---|---|
| `ll` | `stack` |
| `ppl` | `2+1` |
| `pppp` | `2x2` |
| `ppll` | `2+1+1` |
| `pplpp` | `2+1+2` |
| `ppppl` | `2+2+1` |
| `pppppp` | user choice: `portrait-pairs-descending`, `portrait-pairs-ascending`, `portrait-triples-descending`, or `portrait-triples-ascending` |
| `ppppll` | `2+2+1+1` |

Selection outcomes are explicit:

- one match: return its canonical layout ID;
- multiple matches: raise `AmbiguousLayoutSequenceError` with ordered candidate IDs; show those choices to the user and call `select_layout(sequence, requested=id)` after selection;
- no match: raise `UnsupportedLayoutSequenceError` with the unchanged sequence; only then load `collage-layout-design` for interactive design or an approved scene split;
- invalid symbols: reject the sequence before catalog lookup.

For example, `ppllppl` is a valid orientation string but currently has no catalog entry, so it produces `UnsupportedLayoutSequenceError` rather than a count-based fallback. The renderer's current 2–6 source limit is a separate concern handled by `collage-layout-design`; the selector itself does not reject a valid sequence merely because of its length.

When several layouts share a sequence—for example pair-grouped versus triple-grouped or ascending versus descending portrait cascades—the agent must present their labels and wait for a user choice. Never choose the first candidate silently. Preserve source order: the orientation sequence and the rendered panel order are the same. If a title is present, explain candidate viability before asking: pair-grouped portrait layouts require the existing final two sources to be `title_safe`; triple-grouped layouts require the existing final three. Do not move safe sources to manufacture compatibility.

Explicit presets also include `2+1+2` for a deliberately large middle landscape and `2+2+1` for a large final detail. Use `overlap_stack` for 3-6 photos when each image should stay large and cascade with intentional overlap while preserving mixed portrait/landscape base cells. Manual layout selection is editorial control, not a workaround for missing `title_safe` metadata.

#### `overlap_stack` (3-6 sources, explicit only)

| Field | Default | Range | Behavior |
|---|---:|---|---|
| `layout` | — | `overlap_stack` | expands heterogeneous cells from `base_layout` or explicit `base_cells`; later sources draw above earlier ones |
| `base_layout` | `auto` | tiled presets | source mosaic to preserve; for three cards auto uses `2+1` (two upper cards plus a full-width title-safe card), while 4–6 use heterogeneous tiled presets; `custom` when `base_cells` is set |
| `base_cells` | — | 3–6 rects | optional explicit anchors in source order: `[x,y,w,h]` normalized to canvas (`0`–`1`, width fractions for `x`/`w`, height fractions for `y`/`h`) or pixel coordinates when any value exceeds `1`; must tile the canvas exactly; cannot combine with explicit `base_layout` |
| `overlap_ratio` | `0.40` | `0.30`–`0.50` | overlap fraction between adjacent cards (z-order neighbors and cross-row stacks) where expanded rects intersect |
| `entry_seconds` | `4.0` when `duration` is `5.0` and source count ≥3 | — | ~1 s static hold after the last card lands; explicit `entry_seconds` always wins |
| `rotation_enabled` | `false` | — | optional entrance spin for each card: deterministic signed start angle eased to `0°` by that card's entrance end; only valid with `overlap_stack` |
| `rotation_min_deg` | `25` | `0`–`60` | minimum absolute start angle; requires `rotation_enabled` |
| `rotation_max_deg` | `45` | `0`–`60` | maximum absolute start angle; requires `rotation_min_deg <= rotation_max_deg`; requires `rotation_enabled` |
| `final_rotation_max_deg` | `0` | `0`–`10` | optional resting angle cap: each card eases from its start angle to a seeded signed angle in `[-final_rotation_max_deg, +final_rotation_max_deg]` by entrance end and holds it; `0` lands at exactly `0°`; requires `rotation_enabled` |
| `paper_edge` | `false` | boolean | when true, apply a deterministic subtly irregular outer paper contour to each card; requires `paper_edge_seed`; photo pixels are not noised |
| `paper_edge_seed` | — | integer | required when `paper_edge` is true; drives repeatable paper-edge contours |
| `paper_edge_variation_px` | `3` | `1`–`8` | maximum outer contour variation; must leave the requested inner white border intact |
| `paper_edge_inner_border_px` | `1` | `1`–`gutter` | guaranteed crisp continuous white line inside the organic outer edge |
| `paper_edge_inner_overlap_px` | `0` | `0`–`8` | optional softly varying white rim that overlaps 2–3 px onto the photo; use `3` for the approved paper-collage transition |
| `photo_corner_radius_px` | `0` | `0`–`8` | rounded radius of the photo’s own inner corners; the outer card remains organic rather than uniformly rounded |
| `seed` | — | integer | required when `rotation_enabled` is true; drives reproducible per-panel clockwise/counterclockwise choices and final resting angles |

Each source keeps its original `base_layout` or `base_cells` anchor. The card expands into free canvas opposite its entrance edge (row-left cells enter from the left and grow right, row-right cells enter from the right and grow left, full-width rows enter from below and grow up). Expansion is bounded by the canvas and limited to roughly `overlap_ratio` of the nearest adjacent base cell/row — never blindly to the canvas edge — so a late z-order card cannot cover the entire frame unless its base cell already does. Paired row neighbors overlap by `overlap_ratio` where possible. Every row after the first also grows upward to overlap the nearest preceding row by `overlap_ratio` where canvas space allows, regardless of left/right entrance — so middle-row cards stack over the hero above, not only over same-row partners. Cards are not re-tiled into equal horizontal strips.

Use `base_cells` when the tiled presets do not match the source orientations or editorial hierarchy. The explicit cells must tile the canvas exactly. When `base_cells` is omitted, `base_layout` presets supply the anchors.

Preserve source order. For a titled overlap stack, the existing final/topmost source must already be `title_safe`; the renderer never moves it. Focal crops use `force_original_aspect_ratio=increase` with no stretch. When `rotation_enabled` is true, each card starts at a seeded signed angle between `rotation_min_deg` and `rotation_max_deg`, rotates smoothly to its assigned final angle by its entrance end, and holds that angle for the rest of the scene. With the default `final_rotation_max_deg` of `0`, the final angle is exactly `0°`. When `final_rotation_max_deg` is greater than zero, each panel keeps its own seeded random resting-angle magnitude, while adjacent panels alternate final signs so they cannot accidentally look parallel. FFmpeg uses a transparent alpha canvas sized to `max(|start|, |final|)`. Before rendering, `rotation_safe_cells` shifts resting card centers by the final rotated-bbox inset (plus paper-edge padding), keeping all visible corners and ragged borders inside the canvas. If a full-width/full-height card physically cannot fit at any non-zero resting angle, only that card is explicitly reported as `zeroed-to-fit-canvas`; its entrance rotation remains intact. Overlay coordinates center the enlarged alpha canvas on the safe target rect. Because the rotated canvas is larger than the card, panels with `entrance.start > 0` are gated with `overlay enable='gte(t,start)'` so no pixels leak into the frame before their scheduled entrance (the first card with `start=0` is visible immediately). The renderer reports per-panel `rotation` metadata (`seed`, `start_angle_deg`, `rotation_direction`, `final_angle_deg`, `canvas`) plus aggregate `overlap.rotation` (including `final_rotation_max_deg`) in the JSON report. Validation fails when any later row has zero overlap with its preceding row.

Completion criterion: a non-empty title has enough `title_safe` sources for every panel it overlaps. The renderer uses the shared YouTube-safe policy: the bottom edge of the complete title box is pinned exactly to 72% of frame height, leaving the lower 28% clear of titles for current Shorts metadata and promotion controls, with a reserved right-side controls area; it fails rather than silently drawing over a face.

### 3. Choose animation

Use `animation: auto` unless the beat requires a specific rhythm:

| Preset | Use when | Behavior |
|---|---|---|
| `row_reveal` | balanced place/people montage | rows enter in sequence; paired cards arrive from opposite sides |
| `row_reveal_ascending` | bottom-up portrait grouping | lower groups enter first, then reveal upward |
| `hero_last` | reveal, payoff, before/after, setup/result | supporting cards arrive first; final full-width/hero panel arrives last from below |
| `fly_in` | energetic chronological set | every panel has its own staggered entrance |
| `none` | deliberate static card | no panel movement; still gets technical QA |

`auto` chooses `hero_last` for two/three images or when any source is marked `hero`; descending grid-like layouts choose `row_reveal`; ascending portrait layouts choose `row_reveal_ascending`; other layouts choose `fly_in`.

Motion must match visible direction when direction itself matters. A duck, vehicle, gaze, or walking subject should enter head-first. The generic presets handle panels, not semantic object tracking; use an explicit effect when a single moving card needs a custom direction.

Completion criterion: the selected preset is recorded in the JSON report and all entrances finish within `entry_seconds`.

### 4. Write a versioned spec

Start from `templates/collage-spec.json`. Every path is relative to `--root`; absolute paths and `..` are rejected.

Required fields:

```json
{
  "schema_version": 1,
  "sources": [
    {"path": "photos/a.jpg", "focus_x": 0.5, "focus_y": 0.45, "title_safe": false},
    {"path": "photos/b.jpg", "focus_x": 0.5, "focus_y": 0.55, "title_safe": true, "hero": true}
  ],
  "output": "exports/scene-collage.mp4",
  "layout": "auto",
  "animation": "auto",
  "title": {"text": "Титр", "max_chars": 25, "font_size": 54, "align": "center"}
}
```

Defaults: 1080x1920, 30 fps, five seconds, two-second entrance window (four seconds for explicit `overlap_stack` with three or more sources at five-second duration), six-pixel white seams, no audio, no overwrite.

### 5. Render

```bash
python3 <skill-dir>/scripts/render_collage.py \
  --root <media-root> \
  --spec <media-root>/scene-collage-spec.json
```

The renderer never modifies inputs. Existing output is rejected unless `overwrite: true` is explicit.

Completion criterion: stdout report has `status: ok`, `decodable: true`, correct dimensions, codec/pixel format/frame count, `audio: false`, source hashes, normalized spec, per-panel geometry/entrance metadata, overlap/timing fields when applicable, a non-empty output SHA-256, and the selected layout/animation. Output and report are written atomically; `visual_review` remains `pending` until representative frames are actually inspected.

### 6. Perform visual QA

Inspect all generated frames, not just the report:

1. `*-mid_entry.jpg`: motion is visible; no black/empty cell, wrong rotation, fly-in gap, or stretched panel.
2. `*-arrived.jpg`: every source reads correctly; faces and key objects survive the crop.
3. `*-last.jpg`: stable hold; title fully inside safe zone; no late movement or edge artifact.
4. `*-contact.jpg`: entrances complete by the configured window and the rest is a stable hold.

If any crop is wrong, change the source's focal coordinates and rerender from the same spec. If the title covers a person, fix `title_safe` assignment/layout; do not merely reduce opacity.

Completion criterion: technical report and all representative frames pass. Return the MP4 plus last frame to the user.

### 7. Hand back to `story`

Record output path, hash, source order, selected layout and animation, QA frame paths, title, and scene status in the story manifest. A rendered scene is not publication approval.

## Selection rules

- **Narrative order is input order.** Arrange sources deliberately before rendering. The renderer preserves that order exactly; its `source_order` report is verification, not evidence of an automatic reorder.
- **Faces above the lower fifth.** For five images, prefer `2+2+1` over `2+1+2` when people dominate the set.
- **Landscapes can carry text.** Water, reflections, foliage, pavement, and wide architecture are usually safer than portraits.
- **Crop deliberately.** `focus_x/y=0.5` is not a universal default; place focus between the eyes for one face and at the pair midpoint for two people. Preserve rotation metadata. Prefer wide cells for landscape sources and tall cells for portrait sources; never stretch or use `contain` merely to avoid choosing a crop.
- **Long titles need reading time.** The default two-second entrance plus three-second hold fits a short two-line title. Add about one second when the selected title wraps to three or more lines.
- **No filler.** A darkened source crop may sit behind panels during entrance, but no blurred background or empty cell remains in the completed composition.
- **Paper-collage finish.** When an overlap stack needs a physical-card feel, use `gutter: 7`, `paper_edge: true`, fixed `paper_edge_seed`, `paper_edge_variation_px: 4`, `paper_edge_inner_border_px: 1`, `paper_edge_inner_overlap_px: 3`, and `photo_corner_radius_px: 2`. This keeps a crisp one-pixel white inner line while the white edge softly overlaps 2–3 px onto the photo; the outer contour remains irregular. Verify a zoomed final frame: no photo noise, holes, or black seams.
- **Hold matters.** Tiled layouts default to two seconds of assembly plus three seconds of stable reading time. An `overlap_stack` with three or more sources defaults to four seconds of entrances and one second of stable hold in a five-second scene.
- **Audio stays separate.** The scene is silent unless a later story/music workflow explicitly mixes approved audio.

## Common pitfalls

1. **Equal grid first, subjects second.** This produces clipped faces and unreadable details. Inspect anchors before choosing cells.
2. **Title over unsafe title-zone cells.** `title_safe` is validation metadata, not a layout-switch or reorder instruction. Preserve source order and choose another existing compatible layout, change the title treatment, or revise the source set. A title-safety validation error is not `UnsupportedLayoutSequenceError`, so it does not by itself load `collage-layout-design`.
3. **Center crop everywhere.** Supply focal coordinates for every non-central subject.
4. **Panels still moving at the end.** Keep `entry_seconds <= duration - 1`; Sergey's Story default is `2 + 3` seconds.
5. **Decorative blurred background.** It hides weak geometry. Use a darkened source crop only behind moving panels; completed panels must cover the canvas.
6. **Treating automatic selection as visual QA.** Auto layout is deterministic, not clairvoyant. Inspect the three QA frames.
7. **Using a collage for a directional object gag.** When object direction is the punchline, use a custom base-photo/card effect and verify the object enters head-first.
8. **Publishing after rendering.** Return to `story`; explicit publication approval remains mandatory.

## Verification checklist

- [ ] 2-6 archived originals, unchanged and checksummed
- [ ] focal point recorded for every source
- [ ] all title-zone panels explicitly `title_safe`
- [ ] layout and animation selected and reported
- [ ] 1080x1920, 30 fps, H.264/yuv420p unless spec deliberately overrides
- [ ] tiled entrances complete within two seconds by default
- [ ] overlap stacks with more than three sources use four seconds of entrances and one second of hold by default
- [ ] optional overlap_stack rotation uses seeded start angles in range and finishes at assigned final angles (`0°` when `final_rotation_max_deg` is omitted) with no clipped corners
- [ ] rotated overlap_stack panels stay fully hidden until `entrance.start` (no rotated-canvas bleed before schedule)
- [ ] no audio, blurred filler, empty cells, or distorted panels
- [ ] faces, food, architecture, and key action survive crops
- [ ] title uses the canonical style and safe geometry reported by the shared title helpers
- [ ] mid-entry, arrived, final, and contact frames inspected
- [ ] MP4 and last frame delivered; story manifest updated separately
