---
name: still-image-animation
description: Render one photo or designed still into a verified animated MP4 scene with controlled pan, zoom, crop, focus, safe typography, and a versioned JSON contract. Use for independent per-image animation and QA; not for story order or publication.
version: 1.0.0
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
2. Choose `crop` for ordinary full-frame motion; use `contain` only when preserving the entire image is essential.
3. Choose one motion: `pan_left`, `pan_right`, `zoom_in`, `zoom_out`, or an explicitly requested `none`.
4. Set normalized `focus_x` and `focus_y` in `[0,1]`. For faces, focus between the eyes; for a pair, use the midpoint.
5. Create a JSON spec from `templates/animation-spec.json` using paths relative to a dedicated root.
6. Render:

```bash
python3 <skill-dir>/scripts/animate_still.py \
  --root <media-root> \
  --spec <animation-spec.json>
```

7. Require a JSON report with `status: ok`, matching dimensions and hash, `decodable: true`, and `motion_detected: true` for moving scenes.
8. Inspect representative start/middle/end frames before presenting the scene. Technical verification does not replace visual QA.

## Contract and safety

- `schema_version` must be `1`.
- `source` and `output` must be relative to `--root`; absolute paths and `..` are rejected.
- Existing outputs are rejected unless the spec explicitly sets `overwrite: true`.
- Supported motion: `none`, `pan_left`, `pan_right`, `zoom_in`, `zoom_out`.
- Supported fit: `crop`, `contain`.
- Default output is 1080×1920, 30 fps, H.264/yuv420p.
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
