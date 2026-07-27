# Contract v1

## Input

`animate_still.py` reads one JSON object. Paths are relative to `--root`, making the root the explicit filesystem capability boundary.

Field names, enums, defaults, and cross-field rules are also defined in `templates/animation-spec.schema.json`. Example instance: `templates/animation-spec.json`.

Required fields:

- `schema_version`: integer `1`;
- `source`: existing image path relative to root;
- `output`: derived MP4 path relative to root.

Optional fields have stable defaults: 1080×1920, 30 fps, 3 seconds, `crop`, centered focus, `none`, no title, no overwrite, fade in and fade out enabled.
`fade_in` and `fade_out` control the 0.2 s black fades at scene start and end independently; both default to `true`.

Title rendering uses the first available system font from a cross-platform candidate list (DejaVu, Liberation, Noto, Arial, and similar paths on Linux and macOS). If no font is found, the scene still renders without text.

`fit_mode: contain` preserves the whole foreground over a blurred background. It supports static and zoom motion, but rejects left/right pan because panning would either be invisible or violate full-image preservation.

`pan_easing` applies to `pan_left` and `pan_right` only. Pan uses the full horizontal crop range (left edge to right edge). Default `focus_dwell` starts faster, slows near `focus_x` without stopping, then accelerates toward the far edge; use `linear` for constant speed.

## Output report

Successful stdout is JSON with:

- contract and status;
- relative output path;
- probed width, height, duration and codec;
- SHA-256 of the actual MP4;
- decode and sampled-motion checks.

Validation and filesystem errors return exit code `2` and a JSON error on stderr. FFmpeg failures retain a nonzero subprocess exit and are never represented as success.

## Integration

A caller must treat the report as evidence about the exact output hash, not as publication approval. `story` records the report against its scene; `social-publisher` consumes only a separately verified package after an explicit publication gate.
