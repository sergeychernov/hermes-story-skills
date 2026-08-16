---
name: static-cover-collage
description: Use for natural or collage platform-specific covers.
version: 1.3.3
author: Sergey Chernov / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [cover, collage, thumbnail, representative-frames, pillow, qa]
    related_skills: [story, shorts-assembly, animated-collage, photo-story-archive]
---

# Static Cover Collage

Production renderer for platform-specific static covers. Prefer a seamless, natural editorial composite assembled from representative source photos; use hard rectangular photo cells only as a deterministic fallback or when the user explicitly requests a card/collage aesthetic.

## Visual modes

### `natural_composite` — recommended default

Use when image generation/editing is available and the user permits an AI-assisted editorial composite.

1. Select 2–6 representative source photos with a clear hero and supporting subjects.
2. Call the configured image-generation/editing tool with the sources as references. Generate a **text-free**, seamless editorial background at the target platform aspect ratio: coherent light, depth, perspective and color; no grids, frames, panels, badges, watermarks, logos or invented text.
3. Preserve real people and story-critical objects. Do not invent extra people or events. Treat the generated image as an AI-assisted composite, not documentary evidence.
4. Visually reject identity drift, changed clothing, malformed anatomy, duplicate subjects, altered landmark identity, or loss of story-critical objects. For children, identity/anatomy review is mandatory; if fidelity is doubtful, use the deterministic fallback rather than presenting an altered likeness.
5. Save the accepted generated background as a versioned derivative and record its source-reference hashes plus generation provenance. Originals remain immutable.
6. Render exact Russian text with `scripts/render_cover_collage.py` using a spec with `"mode": "natural_composite"`, `background`, `platform_preset`, exact platform dimensions, focus coordinates and `provenance.ai_assisted: true`. The renderer adds a soft scrim without card borders, verifies text bounding boxes against the platform safe rectangle, and writes `visual_review: pending` plus `identity_review: pending`.
7. Pass both visual and identity review before user delivery. Approval remains per platform artifact.

Use `references/natural-composite-prompt.md` as the generation brief and `templates/natural-cover-spec.json` as the deterministic overlay spec.

### Card collage — fallback

Use the `layout.preset`/`sources` spec only when generation/editing is unavailable, identity preservation fails, or the user explicitly wants a card/grid collage. Never silently fall back to cards after a natural composite was requested; state why.

## Quick start

```bash
python scripts/render_cover_collage.py --root /path/to/project --spec cover-spec.json
```

Requires Pillow. All source and output paths remain under `--root`.

Before rendering, verify the exact interpreter can import Pillow:

```bash
python3 -c 'import PIL'
```

If system Python lacks Pillow or is PEP 668 managed, do not modify it globally. Create an isolated project venv and run the renderer with that interpreter:

```bash
uv venv .venv-cover
uv pip install --python .venv-cover/bin/python Pillow
.venv-cover/bin/python scripts/render_cover_collage.py --root /path/to/project --spec cover-spec.json
```

A successful JPEG/report render remains valid even if a later optional shell inspection utility such as `file` is unavailable; verify dimensions/format from the renderer report and Pillow decode instead.

## Representative frame selection

Select 2–6 sources that tell a coherent visual story:

1. Use narrative diversity: establishing place, people/action, and a characteristic detail.
2. Prefer readable faces, landmarks, food, or action; set `focus_x` / `focus_y` on the anchor.
3. Prefer clean source images or extracted video frames without burned-in titles and watermarks.
4. For video, extract a sharp representative frame at a meaningful moment rather than an arbitrary interval.
5. Do not use a uniform contact sheet as the final design; establish hierarchy.

## Default layouts

Use a platform preset whenever the destination is known:

- `youtube_api_thumbnail`: exact **3840×2160 (16:9)** wide thumbnail uploaded through YouTube Data API `thumbnails.set`; this is the default YouTube publishing cover and must be composed natively in landscape.
- `youtube_shorts_cover`: optional **2160×3840 (9:16)** portrait artifact only for an owner-facing Shorts/mobile cover surface when that distinct surface is explicitly requested; never pass it to `thumbnails.set`.
- `instagram_reels_cover`: exact 420×654 Reel cover with conservative central crop-safe rectangle;
- `telegram_story_cover`: 1080×1920 first-frame cover with conservative Telegram UI-safe rectangle.

Generic presets are available only for non-platform drafts:

- `vertical_crop_safe_center`: hero in the upper 38%, central text panel from 38–62%, and two supporting cells below.
- `vertical_story_asymmetric`: hero 52%, support 22%, bottom text panel 26%.

Images use aspect-preserving cover crops and fill every image cell edge-to-edge. No stretching, blurred filler, or blank regions.

Typography follows the current cover contract:

- accent headline: yellow with black stroke;
- primary title: white with black stroke;
- keyword line: smaller white type;
- DejaVu Sans Bold discovered from installed fonts.

## Spec

Copy `templates/cover-spec.json`. Schema is `templates/cover-spec.schema.json`. Core fields:

- `schema_version: 1`;
- relative `output` path;
- `width`, `height`;
- `layout.preset` or explicit normalized `layout.cells`;
- 2–6 `sources` with `path`, `focus_x`, `focus_y`, `role`;
- `text.accent_headline`, `text.primary`, `text.keywords`;
- optional colors;
- explicit `overwrite`.

Absolute paths and `..` traversal are rejected.

## Required platform cover package

Do not create one universal image and do not confuse encodings with platform formats. For every requested publishing target, create exactly one versioned cover artifact using its platform preset:

1. `youtube_api_thumbnail` — **3840×2160 (16:9)**. This is YouTube's current recommended standard thumbnail and the only cover artifact passed to Data API `thumbnails.set`. Compose it natively in landscape; never upload a portrait canvas and accept padding, blurred side fields or an automatic 16:9 fit as the finished design. Official source: <https://support.google.com/youtube/answer/72431?hl=en>.
2. `instagram_reels_cover` — **420×654 (1:1.55)**. Meta's current recommended Reel cover-photo size; Meta says it cannot currently be edited after upload. Official source: <https://www.facebook.com/help/instagram/1038071743007909>.
3. `telegram_story_cover` — **1080×1920 (9:16)** delivery default. Telegram's Story API accepts vertical `media` and has no separate cover/thumbnail argument, so this artifact is the exact first frame of the Story media. Dimensions are a production default, not an official exact-size requirement. Official API source: <https://core.telegram.org/method/stories.sendStory>.

`youtube_shorts_cover` at 2160×3840 is an optional, separate portrait surface for an owner-facing Shorts/mobile selector. Generate it only when explicitly requested and never route it to `thumbnails.set`.

Only generate presets for platforms requested by the publishing plan. A YouTube standard-video thumbnail is a different target and must not be generated for a Shorts-only story unless explicitly requested.

### Safe zones and provenance

The renderer records `platform_contract`, `text_safe_rect_pixels`, actual `text_bounding_boxes`, dimension provenance and safe-zone provenance. Rendering fails if text leaves the selected safe rectangle.

- YouTube API thumbnail: use a conservative inner 5% margin on every side. YouTube's cited page specifies 16:9 and 3840×2160 but does not publish numeric text-safe margins.
- Optional YouTube portrait Shorts cover: keep every critical text bounding box inside the central rectangle `x=8%..80%, y=29%..71%`. At 2160×3840 this is approximately `x=173..1728, y=1114..2727`; at a 1080×1920 first-frame derivative it is approximately `x=86..864, y=557..1363`. This retains the right-side Shorts controls strip and keeps text inside a conservative central crop for Telegram link previews when YouTube exposes the 9:16 Shorts `og:image`. This is a locally calibrated policy based on observed YouTube/Telegram behavior, not an official numeric Telegram or YouTube specification. Generate the title inside this rectangle rather than merely checking it after render; any text outside it fails the cover.
- Instagram Reels cover: text stays within `x=5%..95%, y=18%..82%`, a conservative crop policy. Meta's cited page specifies size but no numeric safe margins.
- Telegram Story first frame: text stays within `x=5%..95%, y=12%..80%`, a conservative UI policy to avoid common client chrome; recheck against a real target-client preview when UI changes.

Never describe local safe-zone percentages as official platform specifications. Platform dimensions and UI-safe geometry have separate provenance. Each platform artifact needs its own versioned spec, report, visual QA and approval. One platform's approval does not approve another platform artifact.

## Output

The initial renderer atomically writes:

1. canonical JPEG cover for visual review;
2. `{output}.report.json` with source hashes, normalized spec, pixel geometry, crop geometry, selected font, output hash/dimensions/format, and `visual_review: pending`.

After explicit visual approval, deliver a versioned multi-format package derived from the exact approved pixels:

1. canonical JPEG;
2. PNG pixel-preserving derivative;
3. lossless WebP derivative;
4. a manifest binding every derivative SHA-256, dimensions and format to the approved JPEG hash.

Decode every derivative and verify exact dimensions. PNG and lossless WebP must decode to the same RGB pixels as the approved JPEG. Do not overwrite an earlier revision.

`static-cover-collage` ownership ends at the approved hash-bound static artifact and its verified derivatives. `shorts-assembly` owns the target-specific cover-frame count, static-image-to-frame rendering, insertion and upload-candidate timeline verification. Load `still-image-animation` only when the user explicitly requests an animated cover as a separately reviewed derivative; it is not a prerequisite for a static first-frame or intro cover. Image approval alone does not update the story manifest or authorize video modification.

## Technical QA

- [ ] schema/version and role mapping valid
- [ ] 2–6 existing sources under root
- [ ] source aspect ratios preserved by cover crop
- [ ] exact output dimensions and JPEG decode
- [ ] report SHA-256 matches output
- [ ] no partial temp files
- [ ] tests pass

## Visual QA

- [ ] hero establishes the subject
- [ ] supporting cells add distinct context
- [ ] faces/landmarks/details survive crops
- [ ] no stretch, letterbox, blur, or empty cell
- [ ] text hierarchy is legible at phone size
- [ ] title fits without clipping
- [ ] composition reads as an editorial cover, not a grid dump
- [ ] update visual review only after inspecting actual output

## Tests

```bash
python -m unittest discover -s scripts/tests -p 'test_*.py' -v
```
