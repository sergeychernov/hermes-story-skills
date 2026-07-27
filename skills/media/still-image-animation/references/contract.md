# Contract v1

## Input

`animate_still.py` reads one JSON object. Paths are relative to `--root`, making the root the explicit filesystem capability boundary.

Required fields:

- `schema_version`: integer `1`;
- `source`: existing image path relative to root;
- `output`: derived MP4 path relative to root.

Optional fields have stable defaults: 1080×1920, 30 fps, 3 seconds, `crop`, centered focus, `none`, no title, no overwrite.

`fit_mode: contain` preserves the whole foreground over a blurred background. It supports static and zoom motion, but rejects left/right pan because panning would either be invisible or violate full-image preservation.

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
