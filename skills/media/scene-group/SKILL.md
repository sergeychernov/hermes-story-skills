---
name: scene-group
description: Use when grouping scenes into one reusable scene-like unit.
version: 1.0.0
author: Sergey Chernov / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [video, scenes, group, ffmpeg, concat, qa]
    related_skills: [story, shorts-assembly]
---

# Scene Group

## Overview

Create a **logical group of two or more explicit scenes** and optionally render it as one scene-like MP4. A group owns identity, member order, boundaries, and its reusable artifact. It does not own narration or audio policy.

- `story` owns editorial order and approvals.
- `scene-group` owns group composition and scene-like rendering.
- `media-voiceover` may later process either one scene or one rendered group.
- `shorts-assembly` may consume the group exactly as it consumes a scene.

## When to use

Use when multiple finished scenes must become one reusable unit for downstream skills. Do not use for narration, source-audio preserve/remove/lower decisions, implicit member selection, or modification of originals.

## Contract

Set a stable `id`, optional `title`, and ordered `members`. Each member has:

- `ref`: stable source scene/group identifier;
- `type`: `scene` or `group`;
- `path`: explicit rendered MP4 relative to `--root`.

Nested `group` members are valid only when an explicit rendered MP4 path is available. Minimum two members.

The group contract deliberately rejects `voiceover`, `source_audio`, `audio_mode`, `audio_default`, `gain_db`, `ducking`, and `audio_policy` fields.

## Workflow

### 1. Define and validate

Start from `templates/group.json`:

```bash
python3 <skill-dir>/scripts/validate_scene_group.py \
  --root <media-root> --spec <media-root>/group.json
```

Completion: exact member order is explicit, paths stay inside root, member files exist, and no audio-policy field is present.

### 2. Render the scene-like artifact

```bash
python3 <skill-dir>/scripts/render_scene_group.py \
  --root <media-root> --spec <media-root>/group.json
```

The renderer:

- normalizes all members in one filter graph to target dimensions and CFR;
- preserves each existing source audio stream semantically;
- adds exact-length silence only when a member lacks audio, solely for concat compatibility;
- encodes H.264 `yuv420p` plus AAC 48 kHz stereo;
- derives boundaries from decoded video frames;
- verifies source immutability and full output decoding;
- atomically writes output and report.

Completion: report has `status: ok`, `artifact.kind: group`, exact members and boundaries, source/output hashes, and `full_decode_verification.ok: true`.

### 3. Register as one reusable scene-like unit

Record group `id`, title, members, output path/hash, boundaries, duration, streams, and report path in the story manifest. Downstream skills target this artifact by `kind: group` without reconstructing its members.

## Common pitfalls

1. **Audio policy in the group.** A group only composes members; use `media-voiceover` for narration and source-audio routing.
2. **Implicit ordering.** Never infer members from folder order or filenames.
3. **Unresolved nested group.** A nested group needs its rendered MP4 path.
4. **Member fades create black seams.** Before rendering a hard-cut group, inspect each member's first and last decoded frames. Disable per-scene fade-in/fade-out at internal boundaries unless a fade is explicitly part of the editorial transition. A technically valid concat with black boundary frames fails visual QA and must be rebuilt.
5. **Overwrite without permission.** Existing output requires `overwrite: true`.

## Verification checklist

- [ ] 2+ explicit members in exact order
- [ ] stable group identity and member references
- [ ] no voiceover or source-audio policy fields
- [ ] H.264 `yuv420p`, AAC 48 kHz stereo, target CFR
- [ ] exact decoded-frame boundaries recorded
- [ ] full decode passed
- [ ] originals unchanged and checksummed
- [ ] group registered as a scene-like artifact
