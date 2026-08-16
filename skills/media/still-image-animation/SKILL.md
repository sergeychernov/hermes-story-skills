---
name: still-image-animation
description: Render one photo or designed still into a verified animated MP4 scene with controlled pan, zoom, crop, focus, safe typography, and a versioned JSON contract. Use for independent per-image animation and QA; not for story order or publication.
version: 1.0.5
author: Sergey Chernov / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [image, animation, ffmpeg, pan, zoom, vertical-video, rendering, qa]
---

# Still Image Animation

## Boundary

Turn **one still image plus one explicit motion specification** into one verified video scene. This skill owns pan/zoom geometry, crop/contain behavior, optional title rendering, FFmpeg execution, and machine-readable verification.

It must not infer narrative order, travel context, audience, social platform, or publication approval. The domain-neutral `story` skill owns editorial coordination.

## Workflow

1. Inspect the source image and identify its visual anchor.
2. Choose `crop` for ordinary full-frame motion. For a landscape source targeting 9:16, default to `crop` plus `pan_left` or `pan_right` so the source itself fills the canvas and the scene reveals the wide composition over time. Do not use blurred, duplicated, mirrored, or otherwise synthesized background fill unless the user explicitly requests it. Use `contain` only when preserving the entire image in every frame is essential and visible letterboxing has been explicitly accepted.
3. Choose one motion: `pan_left`, `pan_right`, `zoom_in`, `zoom_out`, or an explicitly requested `none`.
4. Set normalized `focus_x` and `focus_y` in `[0,1]`. For faces, focus between the eyes; for a pair, use the midpoint. Pan crosses the full horizontal crop range; default `pan_easing: focus_dwell` is faster at the edges and slower near `focus_x` without stopping; use `linear` for constant speed.
5. Keep `title_position: lower_fifth` by default. Use `title_position: middle` over visually unimportant background when the lower-fifth box would cover faces or primary action. `bottom` is available for non-YouTube canvases but is outside the reliable YouTube Shorts safe area; never use it for a YouTube deliverable.
6. Create a JSON spec from `templates/animation-spec.json` using paths relative to a dedicated root. See `templates/animation-spec.schema.json` for allowed values and defaults.
7. Render:

```bash
python3 <skill-dir>/scripts/animate_still.py \
  --root <media-root> \
  --spec <animation-spec.json>
```

8. Require a JSON report with `status: ok`, matching dimensions and hash, `decodable: true`, and `motion_detected: true` for moving scenes.
9. Inspect representative start/middle/end frames before presenting the scene. Technical verification does not replace visual QA.

## Contract and safety

- `schema_version` must be `1`.
- `source` and `output` must be relative to `--root`; absolute paths and `..` are rejected.
- Existing outputs are rejected unless the spec explicitly sets `overwrite: true`.
- Supported motion: `none`, `pan_left`, `pan_right`, `zoom_in`, `zoom_out`.
- Supported fit: `crop`, `contain`.
- Default output is 1080×1920, 30 fps, H.264/yuv420p.
- Fade in/out (0.2 s each) are on by default; disable independently with `fade_in: false` or `fade_out: false`.
- Pan easing: `focus_dwell` (default) or `linear`.
- Title position: `lower_fifth` (default shared YouTube-safe band: the bottom edge of the complete title box is pinned exactly to 72% of frame height, leaving the lower 28% clear for current Shorts metadata and promotion controls, plus a reserved right-side controls zone), `middle` for avoiding faces/actions while staying YouTube-safe, or `bottom` only for platforms without bottom delivery controls. The geometry comes from `shorts-assembly/scripts/youtube_safe_title.py`; do not duplicate constants locally.
- Preserve original files; write only the declared derived output and transient title sidecar.

Read `references/contract.md` before integrating another renderer or orchestrator.

## Testing

Run both pure and real-render tests:

```bash
python3 -m unittest discover \
  -s <skill-dir>/scripts/tests \
  -p 'test_*.py' -v
```

The integration test creates synthetic non-private media, runs actual FFmpeg/ffprobe, checks dimensions and checksum, and confirms sampled frames differ for a pan.

## Pitfalls

- Do not use exact MP4 bytes as a visual regression oracle across FFmpeg versions.
- Do not call a nonzero sampled-frame difference sufficient visual QA; fades and overlays can also change pixels.
- Do not hide weak geometry behind `motion: none`.
- Do not let this skill accumulate story assembly or publishing logic.
