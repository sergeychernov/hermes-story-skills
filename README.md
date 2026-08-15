# Story Skills

Composable Hermes skills for small media stories:

- `story` — domain-neutral editorial orchestration and approval gates;
- `photo-story-archive` — preserved source material and journal;
- `still-image-animation` — one still image to one verified motion scene;
- `animated-collage` — independently rendered multi-photo scenes;
- `scene-group` — reusable editorial beats built from approved scenes;
- `media-voiceover` — immutable source voiceover plus versioned derivatives;
- `static-cover-collage` — platform-specific natural and collage covers;
- `story-soundtrack` — frame-locked composition, source mix, approval and handoff;
- `shorts-assembly` — final visual assembly and exact approved-audio mux;
- `social-publisher` — gated external publication.

These packages are the media dependency graph delegated by `story`. They are
kept together so a checkout does not silently fall back to stale globally
installed skill copies.

By default, durable story archives live under the domain-neutral `~/stories/YYYY-MM-DD-topic/` root. Originals, previews, music, renders, and publishing packages stay together in the corresponding story directory; platform names describe exports, not storage roots.

## Shorts editing workflow

### Quick how-to: build one story

Use one story root and keep every spec, report, approval, and derived artifact under it:

```bash
export STORY="$HOME/stories/YYYY-MM-DD-topic"
mkdir -p "$STORY"/{originals,normalized,specs,scenes,covers,soundtrack,renders,reports}
```

Then follow this short path:

1. Copy uploads unchanged into `originals/`; create `story.json` with scene order and approval state.
2. Validate the manifest:

   ```bash
   .venv/bin/python skills/media/story/scripts/validate_story.py "$STORY/story.json"
   ```

3. Normalize each real video once. Approve a title, then render every scene through the matching recipe below.
4. Review each scene as an MP4. Correct and approve scenes before assembling the whole film.
5. Render and approve each requested platform cover separately.
6. Build the zero-origin, CFR visual timeline with exact scene/cover frame counts.
7. Render, mix, review, and approve soundtrack against that frozen timeline.
8. Mux the approved audio handoff without additional audio processing; fully verify the final master.
9. Create review-only transport copies if needed. Publish only after explicit package approval.

### Concrete recipes

All `--spec` paths are relative to `--root` unless a script's schema says otherwise. Start from the templates and contract in the named owner skill; use `--help` for the complete CLI.

| Need | Canonical owner | Concrete entrypoint |
|---|---|---|
| Validate story order/state | `story` | `python3 skills/media/story/scripts/validate_story.py "$STORY/story.json"` |
| Animate one narrative photo | `still-image-animation` | `python3 skills/media/still-image-animation/scripts/animate_still.py --root "$STORY" --spec specs/still.json` |
| Render a 2–6 photo collage scene | `animated-collage` | `python3 skills/media/animated-collage/scripts/render_collage.py --root "$STORY" --spec specs/collage.json` |
| Combine approved scenes into one editorial beat | `scene-group` | `python3 skills/media/scene-group/scripts/render_scene_group.py --root "$STORY" --spec specs/group.json` |
| Add or replace voiceover on a scene/group | `media-voiceover` | `python3 skills/media/media-voiceover/scripts/render_media_voiceover.py --root "$STORY" --spec specs/voiceover.json` |
| Render a platform-specific static cover | `static-cover-collage` | `python3 skills/media/static-cover-collage/scripts/render_cover_collage.py --root "$STORY" --spec specs/cover.json` |
| Insert an approved cover frame-exactly | `shorts-assembly` | Follow `skills/media/shorts-assembly/references/platform-cover-timeline-insertion.md` and `skills/media/shorts-assembly/references/frame-exact-cover-timeline.md` |
| Build an aspect-safe review timeline | `shorts-assembly` | Follow `skills/media/shorts-assembly/references/review-first-aspect-safe-assembly.md` and `skills/media/shorts-assembly/references/full-story-preview-assembly.md` |
| Render a soundtrack revision | `story-soundtrack` | `python3 skills/media/story-soundtrack/scripts/render_story_score.py --root "$STORY" --spec specs/soundtrack.json` |
| Mix source audio and score | `story-soundtrack` | `python3 skills/media/story-soundtrack/scripts/mix_story_audio.py --root "$STORY" --spec specs/soundtrack.json` |
| Approve the chosen soundtrack revision | `story-soundtrack` | `python3 skills/media/story-soundtrack/scripts/approve_story_soundtrack.py --root "$STORY" --spec specs/soundtrack.json --approval-note "<user approval>"` |
| Verify the locked soundtrack handoff | `story-soundtrack` | `python3 skills/media/story-soundtrack/scripts/verify_story_soundtrack.py --root "$STORY" --spec specs/soundtrack.json --require-approved-handoff` |
| Deliver a review-only Telegram copy | `shorts-assembly` | `python3 skills/media/shorts-assembly/scripts/deliver_telegram_review_video.py --input <master.mp4> --derivative-output <preview.mp4> --chat-id <id>` |
| Publish approved package | `social-publisher` | Use `publish_youtube.py`, `publish_instagram.py`, or `publish_telegram_story.py` only after their explicit approval gate |

Common variants are documented as focused recipes rather than copied into project scripts:

- title fitting and horizontal stills: `skills/media/shorts-assembly/references/title-preflight-and-horizontal-stills.md`;
- stop-frame photo cards: `skills/media/shorts-assembly/references/stop-frame-photo-cards.md`;
- animated inset cards: `skills/media/shorts-assembly/references/animated-inset-card-overlays.md`;
- local cover replacement with locked audio: `skills/media/shorts-assembly/references/cover-swap-with-locked-audio.md`;
- cover-inclusive timeline before scoring: `skills/media/shorts-assembly/references/cover-inclusive-timeline-and-score.md`;
- Telegram review delivery diagnostics: `skills/media/shorts-assembly/references/telegram-bot-review-delivery.md`;
- editorial reaction-tail trim: `skills/media/shorts-assembly/references/editorial-reaction-tail-trimming.md`.

### Why this order

The workflow is a dependency graph, not a set of interchangeable FFmpeg steps. Each stage consumes an approved, hash-bound handoff from the previous owner. This order keeps source media immutable, avoids repeated lossy processing, and prevents a late visual change from silently invalidating titles, music, or publication packages.

#### 1. Define the deliverable and editorial order

Decide whether the requested artifact is a platform-limited Short, a full story, or a review master. Create the `story` manifest with explicit scene order and approval state before rendering.

**Why first:** duration limits, cover treatment, scene selection, and publication targets change the frame contract. Starting from FFmpeg commands before those decisions are explicit creates disposable renders and ambiguous approvals.

#### 2. Preserve every source and create canonical video derivatives

Store uploads unchanged through `photo-story-archive`. For real video, create one canonical normalized derivative before titles or assembly: zero-origin timestamps, target CFR/canvas, compatible pixel format/audio format, and at most one approved denoise/loudness pass. Record hashes and the actual processing report.

**Why now:** all later stages need one stable timebase and one provenance chain. Reprocessing an already titled or assembled derivative compounds quality loss, repeats denoise, and can shift audio/video boundaries.

#### 3. Approve titles, then render each scene through its owner

Resolve each scene independently:

- real video and existing-video titles use the shared title style and safe-geometry helpers;
- one narrative photo is rendered by `still-image-animation`;
- 2–6 photos forming one scene are rendered by `animated-collage`;
- approved scenes may be combined into an editorial beat by `scene-group`;
- voiceover changes are produced as versioned derivatives by `media-voiceover`.

Inspect the actual MP4 for every scene; contact sheets and isolated frames are supporting QA, not substitutes for the scene preview.

**Why before assembly:** crop, motion, title wording, and scene-local audio are cheaper to correct in isolation. Rebuilding the full film for every local correction obscures which artifact was approved and encourages fixes against downstream derivatives.

#### 4. Create and approve platform covers separately

`static-cover-collage` owns cover dimensions, safe zones, text hierarchy, rendered pixels, report, and approval. Generate only the requested platform artifacts. A YouTube API thumbnail, an Instagram cover, and a Telegram first frame are separate deliverables; approval of one does not approve the others or modify scene titles.

**Why separate:** cover APIs and first-frame surfaces have different contracts. Treating every cover as one generic portrait image produces wrong dimensions and makes a cover revision accidentally rewrite the video.

#### 5. Freeze the visual timeline

`shorts-assembly` consumes only verified scene artifacts and approved cover pixels. It fixes editorial order, target CFR, exact scene frame counts, cover insertion frames, and total visual duration. Build a zero-origin visual master and verify every scene boundary by decoded frame number rather than timestamp seeking near cuts.

**Why before soundtrack:** soundtrack duration, transitions, source-audio windows, and final sample count depend on the exact visual frame contract. Changing a cover from one frame to 0.8 seconds after music approval invalidates the score even when all scene files are unchanged.

#### 6. Compose and approve soundtrack against that frozen timeline

Pass the exact visual frame contract to `story-soundtrack`. It owns generated music, source-audio routing, revision previews, loudness decisions, and the hash-bound `USER_APPROVED` audio handoff.

**Why this owner and timing:** assembly should not independently recreate stem gains or mixing rules. One owner keeps subjective revisions, source-audio preservation, and the approved audio hash tied to the same timeline.

#### 7. Assemble and mux without changing approved content

`shorts-assembly` concatenates the verified visual timeline and muxes the exact approved soundtrack handoff. It must not denoise, normalize, duck, trim, regenerate stems, or otherwise reinterpret approved audio during mux.

**Why this narrow boundary:** a final mux should be deterministic. If assembly also edits music, the delivered film is no longer the revision the user approved and its provenance cannot be verified from the handoff hashes.

#### 8. Verify the final master and create transport derivatives

Before delivery, verify full video/audio decode, exact dimensions, CFR, frame count, stream starts, duration, hashes, scene order, title safe zones, cover boundary, and representative frames. Preserve the canonical master. Smaller Telegram copies or alternate containers are explicitly review-only transport derivatives and must not replace the publication master.

**Why verification precedes delivery:** successful encoding or upload does not prove semantic completeness. A file can decode yet contain a stale scene, truncated narration, duplicated frames, or the wrong cover revision.

#### 9. Publish only the verified, explicitly approved package

`social-publisher` validates the exact master/cover hashes, metadata, audience, target account, and duplicate-publication state before any external write. Publication approval is separate from scene, cover, soundtrack, review-master, and chat-delivery approvals.

**Why last:** platform writes are externally visible and may be non-idempotent. Binding publication to the verified package prevents a successful review upload from being mistaken for permission to publish.

#### Invalidation rules

- Changing a source, crop, title, scene duration, scene order, cover pixels, or cover frame count invalidates the visual timeline and every soundtrack/final-master approval bound to it.
- Changing soundtrack routing, stems, source-audio treatment, or gain invalidates the soundtrack handoff and final master, but not approved visual scenes.
- Changing only a review transport derivative does not invalidate the canonical master.
- Reusable behavior belongs in a skill. A short-lived story project stores only originals, specs, reports, approved artifacts, and manifests—never a compatibility copy of a superseded renderer.

## Prerequisites

### Required for local development and media tests

| Tool | Used by |
|------|---------|
| **Python 3.10+** | all skill scripts; PEP 604 union syntax is used |
| **`ffmpeg` and `ffprobe` in `PATH`** | scene rendering, voiceover, soundtrack, assembly and package verification |
| **NumPy** | `story-soundtrack` |
| **Pillow** | `static-cover-collage` rendering and tests |

Quick check:

```bash
python3 --version
ffmpeg -version
ffprobe -version
```

### Title overlays on rendered scenes

`still-image-animation` can burn in a `title` with FFmpeg `drawtext`. Both the font and filter must be available:

1. **A system font** — the renderer searches common Linux and macOS paths (DejaVu, Liberation, Noto, Arial, and similar).
2. **FFmpeg built with `drawtext`** — without it, scenes still render but text is skipped silently.

Check:

```bash
ffmpeg -filters 2>&1 | grep drawtext
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path("skills/media/still-image-animation/scripts")))
from still_image_animation import resolve_font
print("font:", resolve_font() or "not found")
PY
```

**macOS note:** the default Homebrew `ffmpeg` formula often lacks `drawtext`. Install a build that includes libfreetype, for example:

```bash
brew uninstall ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg
```

Optional font package (user fonts land in `~/Library/Fonts/`):

```bash
brew install font-dejavu
```

**Linux note:** install `ffmpeg` from your distro or ensure `libfreetype` was enabled at build time; DejaVu or Liberation packages are usually enough for fonts.

### Optional — publishing and platform adapters

These are not needed to run the unit tests above, but are required for live publication workflows:

| Skill / workflow | Extra setup |
|------------------|-------------|
| `social-publisher` → Telegram Stories (user account) | `telethon`, `python-socks` — see `skills/media/social-publisher/references/telegram-stories.md` |
| `shorts-assembly` → Telegram Bot review delivery | `python-telegram-bot` with proxy extras when a proxy is configured |
| `social-publisher` → YouTube | Google Cloud OAuth — see `skills/media/social-publisher/references/youtube-oauth-setup.md` |

## Test local scripts

Preferred one-command runner:

```bash
PYTHON=.venv/bin/python scripts/test_all.sh
```

The default runner executes the following lightweight and medium suites explicitly:

```bash
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/still-image-animation/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/story/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/animated-collage/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/scene-group/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/media-voiceover/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/static-cover-collage/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/shorts-assembly/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/social-publisher/scripts -p 'test_*.py' -v
```

The long `story-soundtrack` suite is temporarily opt-in and remains available for explicit full verification:

```bash
RUN_STORY_SOUNDTRACK_TESTS=1 PYTHON=.venv/bin/python scripts/test_all.sh
```
