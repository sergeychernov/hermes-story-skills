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

### Quick how-to: make a Short in chat

1. **Upload the source media.** Send the original video clips and photos in the best available quality. If order matters, send the files in that order or label them `1`, `2`, `3`. You may also upload your own music, narration, logo, or a preferred cover image.
2. **Describe the result in one message.** Say what the Short is about, where it will be published, the desired duration, language, tone, and anything that must be preserved. For example:

   > Make a YouTube Short under 60 seconds. Use the files in upload order. Keep the original speech, do not cut the camera pans, animate the two photos as one collage, and propose short Russian titles.

3. **Review the proposed story plan.** The assistant should return the scene order, approximate duration, title text, treatment of each photo/video, source-audio policy, and required platform covers. Correct the plan before rendering.
4. **Approve scene previews.** Review each scene as a short MP4. Approve or request changes to crop, motion, title, duration, and voiceover. A contact sheet alone is not scene approval.
5. **Approve covers separately.** Ask for only the platforms you need. A YouTube thumbnail, Instagram cover, and Telegram first frame are different artifacts; approving one does not approve the others.
6. **Choose the audio treatment.** You can:
   - keep only the original clip audio;
   - upload a music track and say where original speech/sounds must remain audible;
   - ask for generated background music and describe mood, pace, and instruments;
   - upload narration or ask to add voiceover to selected scenes;
   - ask for denoise, but the original audio must remain unchanged and the cleaned version must be reviewed separately.
7. **Approve the audio mix before final video assembly.** Listen to the mixed audio or soundtrack revision with its declared scene timing. Request gain, music, or source-audio changes here—not after final mux.
8. **Ask for the final master.** Once scenes, covers, and audio are approved, say which approved cover belongs in the timeline and request final assembly. Review the delivered video from beginning to end.
9. **Approve publication explicitly.** Delivery in chat is not permission to publish. Name the platform, account/channel, audience, metadata, and exact approved master when asking to publish.

A useful compact first message is:

> Build a 9:16 Short for `<platform>`, up to `<duration>`. The files are in `<order>`. The story is `<one sentence>`. Keep `<speech/sounds/movements>`. Use `<uploaded/generated/no>` music. Put `<title idea>` on `<scenes/cover>`. First show me the scene plan and titles; do not publish.

### Concrete user recipes

| What you want | What to upload | What to write in chat | Approval sequence |
|---|---|---|---|
| Short from existing video clips | Original clips | “Use upload order; keep original speech; propose cuts and titles; target `<platform/duration>`.” | Plan → titled scene previews → cover → audio → final master |
| One photo as a narrative scene | One original photo | “Turn this into a `<duration>` scene; use a gentle `<pan/zoom>` focused on `<subject>`; title: `<text>`.” | Motion preview → title/safe-zone preview → scene |
| Animated collage from 2–6 photos | Original photos, preferably labeled in order | “Make these photos one collage scene; emphasize `<hero photo>`; title: `<text>`; avoid cropping `<people/object>`.” | Layout still → animated MP4 → scene |
| Photo cards over a video | Base video plus card photos | “Keep the base video moving; show these photos as cards at `<moments>`; do not cover `<subject/title area>`.” | Timing/layout preview → scene |
| Several approved scenes as one beat | Approved scene previews | “Group scenes `<IDs>` in this order as one beat; preserve their audio and do not add new mixing.” | Group preview → grouped scene |
| Add narration or voiceover | Target scene/group plus narration file, or approved text for TTS | “Add this voiceover to `<scene>`; `<preserve/lower/remove>` source audio; review the mix separately.” | Voiceover audio mix → revised scene |
| Keep original sound and add uploaded music | Original clips plus music file | “Keep speech audible in scenes `<IDs>`; use this music underneath; lower or mute it at `<moments>`.” | Audio routing plan → mixed-audio preview → final mux |
| Generate background music | Approved visual timeline | “Generate `<mood/tempo/instruments>` music for the frozen timeline; avoid vocals; preserve `<named source sounds>`.” | Music revision → source/music mix → approved audio handoff |
| Clean noisy speech | Original clip | “Create a denoised derivative, preserve the original unchanged, keep natural pauses, and send the audio mix for approval before video.” | Original/cleaned audio comparison → derivative scene |
| Platform cover | Candidate photos and final title/subtitle | “Create a cover for `<YouTube API/Instagram/Telegram>` using `<photo>`; title `<text>`; keep `<subject>` unobstructed.” | Platform-specific still → cover approval |
| Replace only the cover | Approved final video plus newly approved cover | “Replace only the `<platform>` cover/first-frame segment; keep the approved timeline audio locked.” | Boundary preview → final master verification |
| Review copy in Telegram | Approved master | “Send a Telegram review copy; keep the canonical master unchanged.” | Review delivery only; no publication approval |
| Publish the finished package | Exact approved master, covers, and metadata | “Publish this exact package to `<platform/account>` for `<audience>` with `<title/caption/tags>`.” | Package summary → explicit publish approval → verified link/record |

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
