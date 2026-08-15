---
name: shorts-assembly
description: Collect clips into titled 9:16 Shorts compilations.
version: 1.5.2
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [shorts, youtube, vertical-video, titling, ffmpeg, assembly]
    related_skills: [story, story-soundtrack, still-image-animation, social-publisher]
---

# Shorts Assembly

## When to use

Assembling YouTube Shorts (or Telegram Stories) from a sequence of vertical video clips and still photos.
Typical trigger: user sends clips one-by-one with captions like «first gift, 6 AM» and wants them collected,
titled, and concatenated into a single Shorts compile for a channel.

## Workflow

### 0. Load skills BEFORE touching media (critical)

This step exists because agents repeatedly start rendering without loading this
skill, then hand-roll ffmpeg with `borderw=3` titles instead of the skill-styled
box overlay, waste a FLUX 3 credit on a child photo, and skip animation — all
failures the skills already warn about. Load these first:

1. **`shorts-assembly`** (this skill) — project layout, title choices, assembly.
2. **`still-image-animation`** — for every narrative still-photo scene. Approved static cover insertion is the exception: this skill renders the approved pixels for the exact target frame count without inheriting animation duration or fades. For narrative stills, `animate_still.py`
   imports `scripts/brand_title_style.py`; current `sergey-vertical-title-v2` is DejaVu Sans Bold, fontsize 54, line_spacing 12, boxborderw 24, boxcolor black@0.406, complete box bottom at 72%. The helper and font SHA-256 make this reproducible across sessions.
3. **`story`** — if building a narrative arc across clips (optional for simple
   compilations).
4. **`story-soundtrack`** — required when generated music or source-audio mixing is involved. Load it before any soundtrack work and accept only its approved handoff for final mux.

Do NOT hand-roll drawtext commands with `borderw=3`. That style is outdated;
the skill-styled semi-transparent box from `still-image-animation` is the
correct look. For video clips (not stills), apply the same box-style drawtext
manually — see `references/ffmpeg-titling-recipes.md` for the recipe.

### 1. Set up project folder

```
<workdir>/<event-slug>/
  clip01-<slug>.mp4      # original video
  clip01-titled.mp4      # titled version
  clip02-source.jpg      # original still
  clip02-titled.mp4      # animated + titled version
  ...
```

### 1a. Canonical normalization at ingest (required)

Before titles, animation, trimming, collage work, or assembly, preserve the upload under `originals/` and create a single canonical derivative under `normalized/`. This is the only ordinary stage that may perform video/audio normalization: zero-origin PTS for both tracks, CFR 30 fps, 1080×1920, SAR 1:1, `yuv420p`, AAC 48 kHz stereo, and class-appropriate **single-pass** conservative noise cleanup plus loudness normalization. Store the source/output hashes, audio class, actual filters, stream starts, duration, and post-encode measurement in a normalization report.

All later renderers must consume `normalized/` only. Titling may re-encode video but must stream-copy the already normalized AAC (`--audio-already-normalized`); assembly must not apply `afftdn` or `loudnorm` again. Archived originals are immutable. Never use a noise gate, `silenceremove`, or pause trimming during routine ingestion. If a source is already denoised, normalize loudness only and record that fact.

This makes every later operation faster and prevents temporal drift or repeated denoising. The same normalization gate applies before still/video mixing: silent derivatives receive an explicit 48 kHz stereo silent track only when joined into a mixed timeline.

#### Rebuilding an existing story or a later part

When a user asks to rebuild scenes that predate this rule, stop any in-flight part assembly first: its output is stale. Audit every selected scene by type. For real video, create a fresh canonical derivative from the preserved archived source, then title it with `--audio-already-normalized`; never normalize a prior titled export. For a multi-photo scene, recreate the collage directly from archived photos through the current `animated-collage` skill rather than merely converting an old collage MP4. Re-render a single-photo scene from its archived source through `still-image-animation` as well. Only after every selected scene meets the current contract may a new review master be assembled. If the user changes a part's narrative order, store and pass an explicit ordered scene list for that part; do not silently mutate archive chronology.

### 2. Per-clip titles

Offer exactly three concise title variants per clip (per Sergey's preference):
1. direct/descriptive
2. atmospheric/narrative
3. self-ironic, observational and kind

**Mandatory title gate:** a short phrase sent with new media (for example, «За столом» or «Крестная фея поздравляет») is working scene context, not approval of a final on-screen title. Offer the three variants and wait for the user's explicit choice **before rendering or changing a title**. Treat it as an approved title only when the user clearly says «титр …», «ставь …» or selects one of the offered choices. User corrections about a title always supersede prior wording.

User picks by number. Record the choice. **The choices must be present in the same message**—use `clarify` when available; never ask «выберите титр» without rendering the three selectable variants. After the choice, render and deliver the requested derived clip rather than leaving the asset unsent.

**Rapid choice correction:** if the user sends a second numbered choice while the first response or render is interrupted/in flight, the latest explicit choice is authoritative. Before patching the journal/manifest or launching the renderer, re-read the unresolved scene's current title state and apply only the newest choice. Do not render or briefly persist the stale first number, and do not ask for another confirmation when the corrected number is unambiguous.

### 2a. Audio treatment, routing, and disclosure

**Soundtrack ownership boundary:** when the story needs generated music, themes, multitrack stems, rhythm/full-score previews, source-audio routing, or user-led soundtrack revisions, load `story-soundtrack` and stop soundtrack work in this skill. `shorts-assembly` may proceed only after `story-soundtrack` emits a valid hash-bound `USER_APPROVED` handoff. It may concatenate/encode the visual timeline and mux the exact approved audio, but must not apply loudnorm, denoise, ducking, gain, stem mixing, duration-changing trim, or any other audio transformation. Verify that the muxed audio hash/decoded PCM duration satisfies the handoff before delivery. The remaining paragraphs in this section govern canonical source-audio ingest only; they are not authority to compose or revise a soundtrack.

Preserve every original video untouched. For Sergey's derived story-video workflow, apply conservative denoising and loudness normalization **once, at canonical ingestion** unless he explicitly requests untouched audio. Every later export must reuse that normalized AAC without a second noise/loudness pass. Never apply audio processing to the archived original. Disclose the actual treatment and verify it from the encoded normalized output rather than merely reporting filter targets.

Speech integrity outranks visual brevity. A dark, shaky, or visually anticipatory lead-in may contain necessary words, so a visual contact sheet alone is not evidence that a range is safe to remove. Keep spoken clips full by default; trim only when Sergey explicitly approves the exact source range or when full-timeline audio inspection proves that no speech or required context is removed. Never use an aggressive gate, `silenceremove`, or threshold-based pause cutting for routine cleanup: these can erase quiet consonants, syllables, and phrase endings.


After every audio-bearing render, compare source and export stream start/end and duration, confirm AAC/sample rate/channels, measure integrated loudness and true peak **from the final AAC/MP4**, check for clipping, and verify phrase completion from the full timeline. A PCM limiter target is not final proof: AAC can overshoot a `-1.5 dB` limiter by several tenths. If a strict `≤ -1.5 dBFS` final ceiling is required, leave encoding headroom (for example limit PCM around `-2.0 dB`) and re-measure after AAC encoding. Representative frames are not audio QA. If the user reports missing words, invalidate the previous render and manifest range, rebuild from the full preserved source first, and re-run both audio and visual QA.


**Report provenance must match the command path.** When a title renderer uses `--audio-already-normalized` / `-c:a copy`, its report must say that AAC was stream-copied and set `audio_processed: false`; never reuse the ingestion filter description merely because the output contains audio. Before assembly, reject contradictory reports such as “stream copied” plus “denoised/loudness normalized.”



**Project-script promotion gate:** before creating a repeated project-local media renderer, check whether its behavior belongs in this skill. Promote reusable implementation into `scripts/`, move story-specific choices into a versioned JSON spec, add tests/templates/reference documentation, and verify the migrated artifact against the previous revision before switching the manifest. Follow `references/promoting-project-media-scripts.md`; do not leave duplicate implementations in both the skill and project.

### 3. Title overlay: two paths

#### Path A — still photo: use `still-image-animation` (preferred)

Write a JSON spec (see `templates/animation-spec.json` in that skill) with the
`title` field set to the multi-line title string. Run:

```bash
python3 <still-image-animation-skill-dir>/scripts/animate_still.py \
  --root <project-folder> --spec <clip-spec.json>
```

This produces a correctly styled, animated, verified MP4 in one step. The title overlay imports `scripts/brand_title_style.py`; never duplicate its parameters. Current `sergey-vertical-title-v2` uses `box=1:boxcolor=black@0.406:boxborderw=24`, DejaVu Sans Bold, fontsize 54, line_spacing 12 at 1080 px width.
Position is generated by the shared `scripts/youtube_safe_title.py` policy — proportional to height, not fixed pixels. For Sergey's vertical-video workflow, align the **bottom edge of the complete title box** (including `boxborderw`) exactly to the 72%-of-height boundary so the lower 28% is free **without an extra hidden lift**. Do not combine that boundary with a second stylistic anchor. Keep the box left of the reserved right-side controls zone. Project renderers must import this helper instead of copying an FFmpeg expression.

#### Path B — existing video: ffmpeg drawtext with box style

For titling an existing video clip (not a still), use ffmpeg drawtext with the
**box style** matching `still-image-animation`, NOT the old `borderw=3` style.

For an active story that will receive multiple clips or revisions, wrap this path in a reusable project script rather than repeatedly assembling terminal commands. The script should accept explicit root/input/output/title arguments, write the title to a textfile, and emit a report containing the output hash, dimensions, duration, source range, decoded audio streams, integrated loudness, true peak, plus middle and late QA-frame paths. For canonical `normalized/` input, use `-c:a copy` so no denoise/loudness pass is applied twice; only archived/unprocessed input may receive the class-appropriate ingestion audio chain. This keeps title and audio corrections deterministic and makes preservation/processing claims verifiable.

**Critical pitfall:** `drawtext` `text=` breaks on colons and certain special
characters because they delimit filter options. `text='6:00 AM'` → parse error.

**Fix:** write title lines to a single textfile with `\n` separators and use
`textfile=`:

```bash
python3 <shorts-assembly-skill-dir>/scripts/youtube_safe_title.py \
  --position lower_fifth --width 1080 --height 1920
```

Import the returned/shared expressions in every renderer rather than copying constants. The policy reserves exactly the lower 28% and the right-side controls zone, including `boxborderw` in the bounds. For existing video, use the reusable project renderer with that helper; do not hand-roll a separate `drawtext` geometry.

Measure the encoded output; filter targets and expressions are not proof of achieved placement, loudness, or peak.

Key parameters:
- `scripts/brand_title_style.py` — canonical machine-readable source. Current `sergey-vertical-title-v2`: `box=1:boxcolor=black@0.406:boxborderw=24`, DejaVu Sans Bold, fontsize 54, line_spacing 12 at 1080 px; report the resolved font SHA-256.
- `line_spacing=12` — multi-line text in a single drawtext
- `fontsize=54` — slightly larger than old 52
- `scripts/youtube_safe_title.py` — single source of truth for both axes. It keeps the complete title box above `h*0.72` (the lower 28% is title-free) and left of the right-side YouTube controls zone. Do not duplicate percentages or FFmpeg expressions in project renderers.
- Keep the safe policy consistent across the whole story. For Sergey's vertical-video workflow, every ordinary scene uses the exact 72%-height box-bottom anchor; incidental passers-by, crowds, cars, pavement, and background objects may be covered and are not reasons to move a title to the middle. Redesign crop/layout only for a story-critical subject, and ask before breaking the shared anchor. Verify the title box on start/middle/end frames and deliver the MP4 preview.

**Semantic title-zone QA:** a title is not valid merely because it is readable and inside the platform safe zone. FFmpeg `drawtext` does not wrap automatically: before rendering, measure or conservatively preflight every line against the safe width and insert semantic 2–3 line breaks. Prefer balanced wrapping over shrinking the canonical brand font. Inspect start/middle/end frames and verify that the complete title box is not clipped at either horizontal edge and does not cover faces, primary action, measurements, signs, labels, or other evidence the scene is meant to show. Start with `lower_fifth`; use `middle` only when the actual middle band is semantically empty. If a title obscures content, reposition it or revise crop/motion and rerender. For grouped scenes, remove any baked local title before adding one group-wide title; never stack or ghost two title layers.

**Horizontal-still composition:** Sergey's default forbids blurred filler, stretched media, and empty bands. Prefer a subject-preserving 9:16 crop. If the whole horizontal frame is story-critical, use an explicitly designed non-blurred canvas/layout; do not silently fall back to `contain` with a blurred duplicate. Any exception must be shown as a scene-local preview and explicitly approved.

**Brand-version propagation:** `scripts/brand_title_style.py` is the sole source for typography and title-box parameters. A user-requested visual change such as box opacity creates a new style version; every title-capable renderer must import the helper, and previously approved scenes that are rerendered with the new style return to pending review.

### 4. Still photos → animated video clips

**Always use `still-image-animation`** (`animate_still.py`) for still photos.
Do NOT create static stills with bare ffmpeg. The script provides:
- pan/zoom motion (verified `motion_detected: true`)
- skill-styled title overlay with semi-transparent box
- fade in/out (0.2s each)
- JSON verification report (dimensions, hash, decode check)

Write a spec JSON:

```json
{
  "schema_version": 1,
  "source": "clip02-source.jpg",
  "output": "clip02-titled.mp4",
  "width": 720, "height": 1280, "fps": 30, "duration": 5.0,
  "fit_mode": "crop",
  "motion": "pan_left",
  "focus_x": 0.35, "focus_y": 0.50,
  "pan_easing": "focus_dwell",
  "title": "Multi-line\\ntitle\\ntext",
  "overwrite": true
}
```

**Choosing motion for still photos:**

- **`pan_left` / `pan_right`** — for scenes implying movement (riding, walking,
  running). Pan creates the impression of travelling through the scene. Choose
  direction by narrative: `pan_left` (camera moves left) feels like moving
  forward into the scene; `pan_right` reveals from subject outward. Set
  `focus_x` to the subject's normalized coordinate in the **source image**.
  The pan must cross the full horizontal crop range: move fast at the edges,
  decelerate while the crop passes the subject, then accelerate toward the far
  edge. Do not pre-crop the source merely to keep the subject permanently in
  frame. Inspect a start frame, a frame at the focus crossing, and an end
  frame; a brief view of the far-edge background is intentional when the
  narrative calls for a complete sweep.
- **`zoom_in`** — for static, contemplative scenes (portraits, objects). Not
  for movement scenes — a zoom on a child sitting on a bike feels wrong; pan
  conveys the riding impulse.
- **`zoom_out`** — for establishing or reveal shots.
- **`none`** — only when motion is explicitly unwanted.

**Title-safe still composition:** visual QA must protect the named object/action as well as faces. If the lower-fifth title covers lifted food, hands, a toy, a foreground bowl, or another story anchor, do not accept the render merely because the face is clear. First try a content-aware zoom and vertical crop offset that keeps the frame photo-filled; change from pan to zoom when the scene is inherently static. Use a designed title-safe canvas only when crop/zoom cannot preserve all anchors, and keep any tonal extension as small and intentional as possible rather than leaving a large blank footer. See `references/title-safe-single-still-composition.md`.

### 4a. Animated photo collages

When the user asks for an **animated collage**, treat it as a designed 9:16 video scene, not a static JPEG. Preserve each original, then render the panels in one FFmpeg filter graph from those originals.

**Renderer gate:** use an existing skill/project animation script when one is available. Do not replace it with an inline terminal filter graph or a one-off bespoke layout. If the project has no suitable renderer, create a reusable script plus explicit inputs/title/output configuration, run that script, and retain its verification report. A correction such as «используй скрипты для анимаций» means rebuild through this scripted path rather than defending an earlier ad-hoc render.

- Default to a full-frame grid/strip layout that keeps faces visible; visually inspect every panel and use a per-image crop offset for portrait inputs rather than center-cropping blindly.
- **Source fidelity:** build a new collage from the images the user just supplied. Do not substitute frames from an earlier video merely because it is already in the project. If the requested source set is unclear, identify the available asset groups before rendering.
- **Batch boundary from conversation flow:** a consecutive run of images, even when each was followed by a per-image inspection question, followed by an unqualified «сделай коллаж» normally forms one collage source group. Archive every image in that run and apply one three-title gate to the collage, not one gate per image. Do not pull in older approved scenes. Ask which assets only when another unresolved image group overlaps or the user explicitly changes topic.
- **Mixed orientations:** make the finished collage dense. By default, every card must be filled edge-to-edge with an actual photo — **no blurred duplicate backgrounds and no empty fields**. Use deliberate aspect-fill crops and per-image crop offsets that retain faces, children, and the story object (for example, an RC car); do not center-crop blindly. Use a blurred-card treatment only when the user explicitly asks for it.
- If a timed entrance is requested, animate the *panel position* with `overlay` expressions, not a zoom of the finished collage. For a “fly in over 2 seconds, hold 3 seconds” request, stagger panel arrivals from distinct sides during `t=0…2`, then pin every `x/y` coordinate for `t=2…5`; do not add a fade-out that shortens the requested still hold.
- The collage title must use the **same lower-fifth semi-transparent box style** as every other clip. Never create a bespoke top header for a collage unless the user explicitly asks for one, and do not leave unused header space after moving a title into the common style. Design the panel layout around the caption: keep faces and the primary action in uncovered panels/areas (for example, put a trampoline scene above a lower caption rather than behind it).
- **Use space according to the actual subjects, not a blanket no-overlap rule.** Inspect every source before choosing the grid. When the lower-fifth area contains no face, person, readable sign, or critical action, let the standard title box overlay a photo and fill the rest of the 9:16 canvas with real panels. Do not reserve a large title-only band or decorative background merely to avoid overlap. For four landscape images, test a dense layout such as `wide hero → two middle panels → wide bottom panel under the title`; reject it only when visual QA shows a meaningful crop or obstruction.
- Verify a mid-entrance frame, one frame just after the final panel arrives, and a late hold frame. Confirm that the late frames have no remaining panel motion, every panel is photo-filled, and the title is readable without clipping or covering the main subject.

### 4b. Stop-frame photo-card overlays

When the user supplies a **video and one or more photos in the same message** and asks for a *«стоп-кадр»* / stop-frame treatment, preserve the whole video first, then freeze its final decoded frame and use it as the background for animated photo cards. This is a mixed-media scene type, not a substitute for a photo collage.

- Normalize the source video to CFR before choosing the final frame. Hold the final frame for a deliberate reviewable duration (normally 2.5–3.0 s); do not fade to black.
- Build each card from its supplied original: aspect-fill scale and crop to its declared inner dimensions, then add an even `pad` frame (default `7 px`, `white`). Keep the helper reusable: it should return both the FFmpeg filter fragment and the outer dimensions so entrance coordinates cannot drift from the frame thickness.
- Animate cards from fully off-canvas, typically from alternating edges, and pin them at their final positions after entry. Inspect one mid-entry and one settled frame: both cards must be complete, photo-filled, and leave the frozen background subject recognizable.
- Give the held part an audio stream that matches its visual duration. Preserve original audio through its source range and append explicit silence to the frozen tail; never let a shorter AAC stream silently truncate the scene.
- A user-provided phrase marked as a **title/caption** is an explicit title override: render it in the shared lower-fifth box style after the freeze begins, record it, and invalidate the prior derived hash. It does not imply approval to assemble or publish the wider story.

See `references/stop-frame-photo-cards.md` for filter-graph structure, reusable frame helper contract, and QA points.

### 4c. Animated inset/card overlays

When one photo must enter as a smaller card over another photo, keep the base image full-frame and animate only the inset card. Treat entrance edge, motion direction, subject facing, final position, and card size as separate decisions.

- **Head/front must lead.** Inspect the actual source pixels before deciding whether to use `hflip`; never infer facing direction from memory or filenames. For left-to-right motion, the subject's head/front must be on the card's right side. For right-to-left motion, it must be on the left side.
- A request such as «с другой стороны» normally changes the entrance edge, not necessarily the final resting position. Preserve the approved final composition unless the user also asks to move the resting card.
- Animate from fully off-canvas: left entrance starts at `x=-card_w`; right entrance starts at `x=canvas_w`. Pin the card at its final `x` after arrival so the requested hold is truly static.
- When the user asks to enlarge the inset, scale it visibly (roughly 20–30% is a useful first revision), then re-check occlusion of the base image's main subjects. A larger card is not successful if it hides the comparison object.
- **Direction QA requires a mid-slide frame.** The final frame proves composition but cannot prove which side the card entered from or whether the head led. Inspect at least one frame while the card crosses the edge and one after arrival; verify direction from pixels, not from the filter expression alone.
- Record card dimensions, entrance edge, motion direction, facing direction, arrival interval, final position, and output hash in the render report.

See `references/animated-inset-card-overlays.md` for reusable FFmpeg expressions and the direction/facing QA checklist.

### 5. FLUX 3 child photo rejection

**FLUX 3 (`bfl_flux3_image_to_video`) rejects photos containing children** with
`status: Request Moderated`, reason `Protected Content`. This wastes a generation
credit.

Do NOT attempt FLUX 3 animation for any photo showing a child.
Use `still-image-animation` (`animate_still.py` with pan/zoom) instead — it is
not subject to content moderation and produces better results for known subjects.

### 6. Concatenation and duration intent

Once all clips are titled and approved, first distinguish a platform-limited Shorts cut from a user-requested full story. A request such as “full version”, “keep everything”, or “leave it around 100 seconds” overrides the normal 60-second Shorts target. Never trim approved scenes solely to force a full-story request under 60 seconds; create a separate short cut only when the user asks for one.

An explicit request to **assemble everything for review** is a review-artifact override, even when per-scene approvals are still pending. Assemble every existing, decodable scene in manifest editorial order, but do not mark scenes approved, publish-ready, or published. Missing or corrupt scene exports must be rebuilt and visually checked before inclusion; do not silently omit them.

**Review assembly includes the current cover when one was requested and generated as part of the same story.** A later instruction such as «собери историю полностью для просмотра» authorizes placing that already-created cover at frame zero in the review artifact; do not reinterpret it as scene-only assembly or require a redundant «вставь обложку» command. This is review inclusion, not publication approval. Keep the standalone-cover gate when the user merely asks to see/revise the cover or explicitly requests a cover-free preview. Use intro mode (normally 0.5–0.8 s), then verify exact decoded frame numbers: every intended cover frame is the cover and the next frame is scene 1 with no black transition. Timestamp seeking (`-ss`) is not frame-authoritative near a cut; use `select='eq(n\,N)'` for boundary QA.

**Aspect-ratio gate:** probe each source before normalization. Never use bare `scale=W:H` when the decoded display aspect ratio differs from the target; a technically valid 9:16 canvas can still contain visibly deformed faces. Choose deliberate aspect-preserving `cover` or `contain/title-safe` composition and inspect start/middle/end. For a 3:4 talking selfie, top-aligned contain with a lower title-safe band is often preferable to enlarging/cropping the face or drawing a caption across the mouth.

**Local-revision gate:** if the user flags one scene after assembly, mark the assembled preview stale but do not immediately rebuild it. Re-render only that scene and deliver the corrected scene as an actual MP4 preview—not JPEGs or a contact sheet as a substitute. Static start/middle/end frames remain internal QA evidence and may be attached only in addition to the MP4. Reassemble the full film only after the local geometry/title decision is accepted.

**Telegram attachment gate:** treat size/format failures and transport timeouts as different problems. The current official Bot API `sendVideo` contract says Telegram clients support MPEG4 video, other formats may be sent as Document, and bots can currently send videos up to **50 MB**; keep practical headroom below that external limit. Preserve the full-resolution master and create a versioned review-only derivative when the master is too large or a smaller chat preview is desirable. However, never assume every failed upload is a size failure. Before rerendering, read the active Hermes gateway error (normally `/opt/data/logs/gateway.log`): `Request Entity Too Large` authorizes size reduction, while `Timed out` requires checking Telegram proxy/connect and `HTTPXRequest.media_write_timeout`/per-call `write_timeout`. Recompressing an already-compliant file does not repair a transport timeout. For Hermes Telegram, confirm the running gateway loaded a media write timeout greater than PTB's 20-second default; restart a stale gateway after that configuration/source changes. Delivery counts as successful only when Telegram returns a `Message`/`message_id`, not merely when local encoding succeeds or no immediate UI error appears. Before attachment still require: `stat`, MP4/H.264/yuv420p compatibility where native video is intended, exact source frame count/fps/duration, full video/audio decode, matching AAC packet-payload hash when audio was copied, and independent first/middle/last visual QA. Identify the preserved master separately. A Telegram/chat derivative is **review-only**: never put it into the publication package, never replace the canonical `video_mix`/master path with it, and never interpret successful chat delivery as publication approval.

Use the bundled orchestration script rather than hand-writing FFmpeg and Bot API commands:

```bash
python3 <shorts-assembly-skill-dir>/scripts/deliver_telegram_review_video.py \
  --input <canonical-master.mp4> \
  --derivative-output <versioned-telegram-preview.mp4> \
  --chat-id <telegram-chat-id> \
  --width 720 --height 1280 --review-max-mib 18
```

This single entrypoint owns the full review-delivery path: it invokes `make_review_delivery_copy.py` only when the input exceeds the review budget, preserves the master, enforces the official 50,000,000-byte `sendVideo` cap and MP4/H.264/yuv420p/AAC baseline, performs full video/audio decode, reads the latest exact-artifact failure from `/opt/data/logs/gateway.log`, distinguishes size failures from timeouts, discovers the live gateway token/proxy without logging secrets, sends with explicit connect/read/media-write timeouts, retries only rate limits and failures proven to occur before an upload could be accepted, suppresses blind retry after ambiguous read/write timeouts, and succeeds only after Telegram returns `message_id`. It writes an atomic delivery report with `review_only: true` and `publication_eligible: false`; failed delivery is recorded as `delivery-failed` using only the exception type, never credential-bearing exception text. Use `--dry-run` for preflight without credentials or network delivery. Independent first/middle/last visual QA remains mandatory before a non-dry-run send.

For mixed video plus silent photo/collage scenes, every segment needs a compatible audio stream. The authoritative duration is decoded video frame count divided by the target CFR—not MP4 `format.duration`, which may include AAC encoder padding. Before `concat=v=1:a=1`, trim every real or generated audio segment to the exact visual duration; otherwise a longer AAC tail can extend a segment and duplicate video frames. Preserve already-cleaned AAC from real video scenes and add 48 kHz stereo silence to silent scenes. Assemble a publish/master via one zero-origin filter concat; fast MPEG-TS stream-copy is review-only and must never be used as a future cover-insertion base. See `references/full-story-preview-assembly.md` and `references/review-first-aspect-safe-assembly.md`.

```bash
printf "file 'clip01-titled.mp4'\nfile 'clip02-titled.mp4'\n" > concat.txt
ffmpeg -y -f concat -safe 0 -i concat.txt -c copy final.mp4
```

**Semantic delivery gate:** preserve the requested artifact, not merely its media format. A compatibility fallback may change container, codec, bitrate, resolution, or attachment type, but it must not replace a requested mixed story with an audio-only track or static-cover visualizer. Static-cover MP4 is valid only as a transport fallback for an explicitly audio-only approval preview. When the user asks for “music plus story sounds,” a full mixed story, or equivalent, audit narrated scene revisions and deliver the actual assembled timeline. Follow `references/full-story-music-mix-and-semantic-delivery.md`.

**Delivery gate:** never answer “video is ready” until the final named MP4 exists (not only a temporary file), `ffprobe` sees the expected video/audio streams, a full decode succeeds, and representative start/middle/end plus ordered scene frames are inspected. After an interrupted render, treat orphan `.tmp.mp4` files as unknown; inspect their `moov`/decode state before reuse and restart only when they are invalid. Attach the MP4 itself in the same response that announces completion. Keep QA commands fail-fast but avoid optional trailing utilities that can turn a successful artifact build into a misleading failed process; probe files with `ffprobe` or an equivalent required tool rather than appending a nonessential `file` call. When constructing shell loops over `name:value` pairs, iterate one variable and split it (`name=${item%%:*}` / `value=${item#*:}`); Bash does not support tuple syntax such as `for name,value`.

### 6a. Editorial tail trims after a reaction or reveal

When the user asks to shorten the footage **after** the camera leaves a person, reaction, or reveal:

1. First inspect the full audio timeline and determine whether the requested area contains speech. A visual contact sheet cannot authorize a spoken cut: dark or repetitive footage may carry the setup sentence. If speech is present and exact cut points were not approved, keep the full clip. Only then build a timestamped contact sheet at roughly 2 fps and identify three visual moments: subject enters, camera leaves the subject, and the first natural endpoint after a short return beat.
2. Preserve the named moment and a brief visual resolution; remove repetitive lingering footage rather than cutting exactly on the camera move. For a return to a train, door, stage, or landscape, keep enough of that return to re-establish the object, then end before an unrelated foreground subject dominates.
3. Rebuild the revision directly from the untouched original with an explicit source range (for example `0.0–8.2 s`) in the reusable renderer. Never trim the already titled/rendered revision.
4. Apply the current audio policy to the rebuilt derivative. For Sergey's workflow, perform class-appropriate noise cleanup plus measured normalization; use `-c:a copy` only after an explicit untouched-audio request. Record the exact source range, output duration, hash, decoded audio stream, integrated loudness, and true peak in the report.
5. Inspect the late frame as composition evidence, but also inspect the last 0.5–1.0 seconds or a short contact strip: a technically clean final frame can still be an editorially weak ending.

This is an editorial trim, not permission to shorten dialogue, music, or a requested full-story cut elsewhere.

### 6b. Platform cover approval and insertion

Delegate static cover generation to `static-cover-collage`; it owns current platform dimensions, layout presets, safe-zone provenance, reports and approvals. Do not copy pixel dimensions into this skill.

For a story targeting YouTube Shorts, Instagram Reels and Telegram Stories, request one artifact per target:

1. `youtube_api_thumbnail` — native wide 3840×2160 thumbnail uploaded through YouTube Data API `thumbnails.set`;
2. `instagram_reels_cover` — separately selected Instagram Reel cover photo;
3. `telegram_story_cover` — exact first-frame artifact inserted into Telegram Story media, because Telegram exposes no separate Story cover upload.

An optional portrait `youtube_shorts_cover` is a different owner-facing/mobile surface. Generate it only when explicitly requested and never pass it to `thumbnails.set`. Encodings such as PNG/WebP are delivery derivatives, not more platform covers.

Deliver each requested platform artifact as a separately labelled image with dimensions, report and SHA-256. Obtain explicit approval for each platform before video assembly or platform writes. Any changed text, crop, safe area or pixels invalidates approval for that artifact.

A request merely to see or revise one platform cover is not approval to modify the video or another platform. After the Telegram first-frame cover is approved, a later request to assemble the full story authorizes including that exact first frame in the **local review artifact** unless the user explicitly asks for a cover-free version. This is not publication permission and does not bypass soundtrack or audience gates.

**Cover hierarchy versus scene titles.** Cover subtitle changes are cover metadata. Keep approved scene titles unchanged unless the user identifies a scene title to replace. Render the requested hierarchy and visually check literal Russian text, contrast, safe-zone compliance and cropping on every requested platform before approval.

**Safe zones.** Use the machine-readable platform contract emitted by `static-cover-collage`. Numeric UI-safe margins are locally calibrated or conservative policies unless the cited platform source explicitly publishes them; never present local percentages as official specifications.

Choose cover duration by *target surface*, not merely by a request to “hit the preview”: a one-frame cover is valid only when explicitly requested, but is not reliable for YouTube Shorts or Telegram link cards after YouTube transcoding. For a YouTube replacement intended to control previews, use **intro mode** and keep the cover visible from frame zero for roughly **0.5–0.8 seconds** (24 frames at 30 fps for 0.8 s), with no black/gray lead-in. Verify exact decoded frames at 0.000, 0.033, 0.100, 0.250, 0.500, the final cover frame, and the first post-cover frame.

If the intro needs a new musical sting, request it from `story-soundtrack` and wait for its approved hash-bound handoff before spending time on video assembly.

**Local cover swap with locked audio:** when the user asks to replace only the opening cover in an already mixed master, do not automatically rebuild the soundtrack or shorten the cover to match a stale manifest. Probe the encoded master, preserve its actual cover-frame count and total frame contract, replace video frames only, and stream-copy the existing audio. Enforce explicit CFR timebase/output settings and verify identical audio packet payloads plus the exact `N-1 → N` boundary. Follow `references/cover-swap-with-locked-audio.md`.

**Whole-timeline soundtrack handoff:** once the cover duration is approved, finalize the full video timeline and pass its exact frame contract to `story-soundtrack`. That skill composes from `t=0`, delivers rhythm/full/source-mixed audio revisions, and binds the approved result to the timeline. Do **not** append an ident, regenerate stems, change routing, or normalize the approved audio inside `shorts-assembly`. After a valid handoff, build the zero-origin visual timeline and mux the exact locked audio only.

On low-power systems, do **not** use MPEG-TS or direct-MP4 stream-copy concat for a cover-inclusive publish candidate merely because its streams look compatible. A nominal 30 fps master can carry a non-zero video PTS, B-frame DTS reordering, or a different effective cadence; copy concat can then emit non-monotonic DTS, a bogus nominal rate, or silently lose duration. Build the final visual timeline in one FFmpeg filter graph: normalize every input with `settb=AVTB,setpts=PTS-STARTPTS,fps=30,setsar=1,format=yuv420p`, then `concat`; hand the resulting zero-origin CFR video to `story-soundtrack` as the fixed timeline. Check `start_time=0`, exact `r_frame_rate=avg_frame_rate=30/1`, expected frame count/duration, and full decode before handoff. See `references/cover-inclusive-timeline-and-score.md`.

**Publication-package handoff must follow the actual publisher parser, not a locally invented schema.** Before declaring a YouTube package ready, inspect or locally invoke the target publisher's no-network parsers. In the current publisher contract, green verification requires `ok: true` and `video: {"sha256": "<exact upload hash>"}`; `status: "green"` plus a top-level `video_sha256` is not interchangeable. Write one complete YouTube tag per non-empty line: a comma-separated list on one line is parsed as one tag. Run the exact hash/tag/title/description preflight before OAuth or upload. If this local gate fails, no upload began; after fixing only schema/format and confirming the unchanged media hash, the next call is the first factual upload rather than a duplicate-risk retry.

### 7. Verify

- Check dimensions: all clips must be 720×1280 (9:16)
- Check duration against the requested deliverable: `≤60s` for an actual Shorts cut; preserve full duration for an explicitly requested full story
- Extract a preview frame from each clip to visually confirm titles are
  readable AND positioned correctly (lower fifth, ~66–71% of height for 720p)
- Send assembled file to user for approval

## Pitfalls

- **Starting without loading skills:** The single most common failure mode. An
  agent that skips Step 0 will hand-roll ffmpeg with wrong title style, waste
  FLUX 3 credits on child photos, and skip animation. Always load
  `shorts-assembly` and `still-image-animation` before any rendering.
- **Old title style (`borderw=3` or `black@0.58`):** Deprecated. The canonical machine-readable style is `sergey-vertical-title-v2` from `scripts/brand_title_style.py`: `box=1:boxcolor=black@0.406:boxborderw=24`, DejaVu Sans Bold, fontsize 54, line_spacing 12 at 1080 px. Never copy these values into project renderers; import the helper so later brand revisions propagate.
- **Exact-vs-minimum safe margin:** Align the complete title-box bottom exactly to `h*0.72`; do not merely enforce `>=15%` while also centering around another anchor. The latter silently lifts titles and wastes composition space. Verify the actual box edge numerically.
- **Duplicated title-safe constants:** Do not embed percentages independently in still, video, and collage renderers. Import or invoke `scripts/youtube_safe_title.py`. For Sergey's YouTube workflow the lower 28% must remain entirely free of the complete title box, and the right controls zone must also remain clear.
- **JPEGs presented as video previews:** Start/middle/end JPEGs are QA artifacts, not user-requested preview clips. When reviewing a corrected scene, attach the actual MP4; include stills only as supplementary evidence.
- **Unapproved per-scene title exceptions:** Do not switch an ordinary scene to `middle` merely because the standard box overlaps incidental people. Random passers-by and background objects may be covered; the shared 72%-height anchor wins. Protect only story-critical subjects/actions, and ask before breaking the common title line.
- **Safe zone versus media fill:** Never create a black footer or empty caption band merely to satisfy title geometry. Title placement is an overlay constraint; preserve aspect ratio and use content-aware `cover` for edge-to-edge delivery unless the user explicitly approves `contain`.
- **Static narrative stills:** Never create a narrative still-to-video scene with bare ffmpeg. Always use `still-image-animation`'s `animate_still.py` for pan/zoom motion and verification. Approved static cover frames are not narrative still scenes: follow `references/platform-cover-timeline-insertion.md` and render the exact assembly-owned frame count with no inherited animation fade or duration.
- **drawtext colon crash:** Never use inline `text=` with colons. Always
  `textfile=` with a single multi-line textfile.
- **drawtext expression commas:** When a scripted `filter_complex` embeds an
  expression such as `y=min(a,b)`, escape the separator as `min(a\,b)` for the
  FFmpeg filter parser. Otherwise parsing may fail later at `box=1` with a
  misleading `No option name near ...` error. Keep this escaping inside the
  reusable renderer instead of fixing individual terminal commands.
- **Long or repetitive titles:** FFmpeg `drawtext` does not auto-wrap. Before rendering, read titles in editorial order, measure or preflight every line against the canonical safe width, and fit the complete box inside the canvas and reserved controls strip. Semantically wrap exact approved wording into balanced 2–3 lines before considering a smaller font; if it still cannot fit, get approval for a shorter phrase. Inspect start/middle/end for edge clipping. Reject adjacent captions that repeat the same lead phrase or fact without adding a new beat. See `references/title-fit-editorial-and-rebuild-gates.md`.
- **Stale final after interrupted rebuild:** A corrected standalone scene does not prove the assembled film changed. After assembly, fully decode the final MP4, extract the corrected scene from that final MP4, and confirm the final hash or modification state changed before delivery.
- **Long title clipping at 720×1280:** The default 54–58 px style can overflow
  narrow frames; a semi-transparent box does not make clipped letters valid.
  Before delivery, inspect a representative title frame. If any character is
  cut at an edge, preserve the wording but split it semantically and/or use a
  smaller 42 px title treatment with the same box style. Render a clean
  no-title animation first, then apply that fitted title once — never burn a
  second title over an already titled clip.
- **FLUX 3 child photo rejection:** Do not send child photos to FLUX 3 video
  generation. Wastes a credit. Use `still-image-animation` instead.
- **ffmpeg preset timeout:** `-preset slow` on 720×1280 with drawtext can
  exceed the 180s terminal timeout. Use `-preset veryfast -crf 20` for video
  titling, or run via a background shell script.
- **Shell quoting:** Complex ffmpeg filter chains with backslash continuations
  can break in inline `terminal()` commands. Write to a `.sh` script file under
  the project workdir and run with `bash script.sh` for reliability.
- **Write safety:** `write_file` to `/tmp` may be blocked by
  `HERMES_WRITE_SAFE_ROOT`. Write scripts under the project workdir instead.
- **Dialogue pause removal:** Never trust a single aggressive `silencedetect`
  threshold. Quiet syllables and word endings are easily classified as silence.
  Start conservatively (for ordinary phone audio, probe around `-50 dB` with a
  minimum silence duration of `0.45 s`), compare against less-conservative
  probes, and cut only intervals confirmed across the evidence. Keep at least
  `0.10–0.15 s` of audio/video on both sides of each cut. If the user names the
  words around a gap, map and cut that one interval first. **Every revision must
  be rebuilt directly from the preserved original in one filter graph** — never
  trim `v2` into `v3` into `final`, because the final then contains hidden
  accumulated source fragments and its rhythm becomes impossible to diagnose.
  Before delivery, state the count and ranges of original-source fragments,
  verify decoding, and scan for remaining long inner silences; do not promise
  that phrases are intact without transcript or human playback review.
- **Audio policy drift:** Canonical `normalized/` input has already received the one permitted class-appropriate noise/loudness pass. Every later title/render export must reuse its AAC (`-c:a copy`) rather than repeat processing; the archived original remains untouched. Verify the normalized output's stream start/end, sample rate, LUFS, true peak, and phrase completion. For still-to-video clips with no audio, consider approved accompaniment or leave silent.

## References

- `references/title-preflight-and-horizontal-stills.md` — explicit drawtext wrapping preflight and Sergey's no-blur/no-stretch/no-empty-band policy for horizontal stills.
- `references/frame-exact-cover-timeline.md` — frame-authoritative assembly, AAC-padding trimming, exact cover-frame QA, and soundtrack handoff.
- `references/platform-cover-timeline-insertion.md` — consume an approved platform cover, insert it frame-exactly, and verify the upload-candidate timeline.
- `references/title-fit-editorial-and-rebuild-gates.md` — title-box fit, adjacent-title continuity, incidental-subject overlap policy, and proof that a corrected scene reached the rebuilt final film.
- `references/youtube-title-safe-exact-15.md` — authoritative exact 28% rule, box-edge math, exception policy, media-fill separation, and verification gate.
- `references/youtube-title-safe-exact-20.md` — historical filename retained for compatibility; current rule is exact 28%.
- `references/youtube-title-safe-policy.md` — centralized 28% bottom/right-controls policy, regression history, and MP4-preview verification checklist.
- `references/shorts-ui-title-safe-calibration.md` — screenshot-driven calibration against the real Shorts player UI; current 72% box-bottom boundary and cross-renderer regression workflow.
- `references/ffmpeg-titling-recipes.md` — concrete drawtext textfile commands,
  title positioning table, still-to-video recipe, FLUX 3 child photo rejection
  details.
- `references/motion-pan-vs-zoom.md` — pan-vs-zoom choice guide, pan direction
  cheat sheet, JSON spec example for movement scenes, skills repo source path.
- `references/animated-collage-renderer-contract.md` — scripted collage inputs,
  lower-fifth title invariant, FFmpeg escaping, report fields, and three-frame QA.
- `references/dense-animated-collage-layouts.md` — dense four-/five-photo layouts,
  title-over-panel rules, reusable scripted rendering, and occupancy-focused QA.
- `references/full-story-music-mix-and-semantic-delivery.md` — audit narrated revisions, build sample-exact source/music mixes, verify exact voice windows, and preserve requested artifact semantics across Telegram fallbacks.
- `references/review-first-aspect-safe-assembly.md` — aspect-preserving video layouts,
  scene-local frame review before reassembly, mixed-audio concat, and delivery preflight.
- `references/telegram-bot-review-delivery.md` — official `sendVideo` contract provenance,
  size-vs-timeout diagnosis, explicit media-write timeouts, the unified delivery script,
  and `message_id`-based success evidence.
- `references/editorial-reaction-tail-trimming.md` — timestamped contact-sheet method,
  source-range cuts after a reaction/reveal, original-source rebuild, and ending QA.
- `references/animated-inset-card-overlays.md` — reusable entrance expressions,
  head-first orientation rules, size-revision checks, and mid-slide QA.

## Tools

- **ffmpeg + ffprobe** — titling (existing video), concatenation, inspection
- **still-image-animation (`animate_still.py`)** — required for narrative still-photo scenes; pan/zoom, title overlay, verification. Not used for assembly-owned static cover frames unless the user requests an animated cover.
- **vision_analyze** — verify title readability and position on preview frames
- **bfl_flux3_image_to_video** — DO NOT use for photos with children; rejected
  with Protected Content