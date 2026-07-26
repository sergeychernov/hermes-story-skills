---
name: travel-social-publisher
description: Use when the user sends travel photos/videos over time and wants one approved package for an Instagram carousel/Reel and YouTube Short, followed by publication only after the explicit command “публикуй”. Archives originals, builds vertical video and platform copy, verifies exports, and uses official APIs when credentials are configured.
version: 1.8.28
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [travel, instagram, reels, youtube, shorts, ffmpeg, publishing, approval]
    related_skills: [photo-story-archive]
---

# Travel Social Publisher

## Overview

Turn an ongoing travel media archive into a single reusable publishing package:

- Instagram carousel and Reel;
- YouTube Short from the same edit;
- Telegram delivery as either one editorial Story up to 60 seconds or, when the user wants the complete longer edit, a scene-boundary-aligned sequence of independent ≤60-second Stories prepared from the same approved source edit;
- cover, captions, title, description, hashtags, location notes;
- publication through official APIs only after explicit approval.

This skill currently spans several separable responsibilities. When changing its architecture, extracting image-animation code, or introducing a general story workflow, read `references/skill-decomposition-and-story-boundaries.md`. Preserve the key boundary: **storytelling is domain-neutral; travel is only one optional source of context**. Prefer class-level components with explicit contracts, characterization tests before extraction, and a compatibility façade during migration rather than a big-bang split.

Use `photo-story-archive` while media is arriving. Load this skill when the user asks to assemble an episode, make a Reel/Short, prepare publishing assets, connect a social account, or says **«публикуй»**. If this skill executes when typed but is absent from Telegram's slash-command picker, read `references/telegram-skill-command-visibility.md`: Hermes already converts the canonical hyphenated command to underscores for Telegram, so diagnose menu truncation and dispatch separately before renaming any skill path or metadata. For unlabeled videos, incremental uploads after a draft, pending-title bookkeeping, contact-sheet interpretation, photographed transit displays, geographic/fortification identification, food-photo sensory interpretation, scene captions, vertical reframing, render performance, and text-overlay checks, read `references/media-intake-and-visual-qa.md`. For a potentially identifiable landmark that should appear by name in titles, also read `references/landmark-identification-and-title-grounding.md`: separate user-provided viewpoint provenance from pixel evidence, triangulate candidates with maps, compare the strongest look-alike, state confidence, and preserve identity-bearing features during 9:16 reframing. When several near-adjacent concert photos form one visual beat and the user requests a collage around a small detail, read `references/concert-burst-collage.md`: preserve every original, group the burst as one editorial material, build one verified 9:16 derived asset, and visually inspect the rendered typography and detail inset before delivery. When helping choose an in-trip food stop for both local culture and capture value, read `references/cultural-food-content-routing.md`; verify hard dish constraints before ranking prestige and distinguish the fastest route from the best story route. When deciding whether a traveller should eat before a concert or timed event, read `references/live-event-venue-planning.md`; match the exact current event, separate drinks/snacks/full meals from verified kitchen hours, and base the recommendation on doors, seating, and time pressure rather than menu existence alone. For Telegram Stories, full-screen vertical format, the choice between one condensed Story and a complete multi-part Story sequence, scene-boundary splitting, explicit contacts/public audience, link-only skip behavior, personal-account vs Business-bot authorization, and publication safeguards, read `references/telegram-stories.md`. When Hermes runs in a pod but the user operates from the Kubernetes host, also read `references/telegram-user-api-kubernetes.md`: verify the helper in its real execution context and expose it through an interactive `kubectl exec -it` command rather than presenting a pod/PVC path as host-local. For YouTube classification, metadata hygiene, mobile UI safe zones, real-device overlay QA, and replacement-upload rules, read `references/youtube-shorts-safe-zones.md`. When a published Short has a dull, gray, or poorly cropped cover, or the user asks for a more colorful/clickable one, read `references/youtube-short-thumbnails.md`: use Sergey's vertical-first 1080×1920 workflow, run literal spelling QA against canonical metadata, distinguish API acceptance from actual Shorts-surface display, and never treat a conventional 16:9 CDN rendition as proof of the vertical cover. For cross-platform OAuth credential handoff and quarantine rules, read `references/oauth-account-setup.md`; for the Google console sequence, also read `references/youtube-oauth-setup.md`.

## Core contract

The workflow has two hard-separated states:

1. **PREPARED** — archive, select, edit, render, verify, and show the package.
2. **PUBLISH APPROVED** — entered only when the user explicitly says **«публикуй»** (or an equally unambiguous command naming the platforms).

Never treat “собери”, “подготовь”, “сделай выпуск”, “покажи”, or uploaded media as permission to publish.

### Audience gate

Before publishing to YouTube or Telegram, explicitly ask the user to choose exactly one audience in user-facing terms: **«для своих контактов»**, **«для всех»**, or **«по ссылке»**. Do not infer this choice from a previous package and do not use a script default. Apply the choice consistently:

| User choice | YouTube | Telegram Story |
|---|---|---|
| Для своих контактов | `private` (only explicitly invited Google accounts; this is not the phone contact list) | `inputPrivacyValueAllowContacts` |
| Для всех | `public` | `inputPrivacyValueAllowAll` |
| По ссылке | `unlisted` | do not publish to Telegram; link-only visibility does not exist for Telegram Stories |

The approval command and audience are separate gates. If the user says **«публикуй»** without a current explicit audience choice, ask the audience question before any network write. If the user chooses **«по ссылке»** for a multi-platform publication, upload the unlisted YouTube video and report Telegram as deliberately skipped, not failed.

## Commands to infer

| User phrase | Action |
|---|---|
| “Добавь это”, short scene label + media, or media-only in one active archive | Inspect, archive, append context, classify as selected/optional/archive-only via `photo-story-archive`, then offer exactly three title choices; one must be self-ironic |
| “Новая сессия / новый архив / новая публикация Shorts” | Create a hard package boundary: start a fresh archive and collecting manifest for the named target. If this is a clarification immediately after one upload, carry only that upload into the new package; never backfill earlier chat media or story context. This phrase does **not** authorize rendering or publication. |
| “Собери выпуск …” | Create/edit manifest, render all assets, verify, return previews |
| “Поменяй …” | Update manifest/copy, rerender affected assets, verify again |
| “Публикуй” | Use the latest verified package and publish to configured targets. If that package declares `replaces_youtube_id` or has already been agreed as a replacement, complete the safe replacement transaction: verify the new upload first, then validate and delete the old ID unless the user explicitly asked to retain it. |
| “Публикуй только в YouTube/Instagram” | Publish only to named target |

When selected material arrives after a render, mark the prior package and `verification.json` **stale**. For every newly added **photo**, immediately add its approved/provisional title overlay, configure its animation, render only that still scene, and send an independently playable per-photo preview for approval; do not wait for or rebuild the full episode preview. Keep the full render deferred until all photo previews are approved. For newly added video, avoid rerendering the whole package on every upload while collection is ongoing. Never publish until the canonical manifest is updated and verification has been rerun after the latest selected-source change. Follow `references/incremental-photo-review.md` for the per-photo state machine, invalidation rules, and review gates; see also `references/media-intake-and-visual-qa.md`.

When the user asks to place a late-arriving scene before/after another beat or to remove “the other clip” by visual description, follow `references/editorial-reordering-and-duplicate-media.md`: preserve capture chronology separately from editorial order, label any montage reconstruction, identify candidates with a filename-labeled contact sheet, hash visual duplicates, exclude the whole duplicate group from the manifest without deleting originals, and rerender/reverify any existing package.

When a long package build is interrupted after producing some artifacts, follow `references/resumable-render-and-package-recovery.md`: probe and decode existing outputs, preserve a valid master, resume only missing downstream stages, write replacement MP4s through a temporary file plus atomic rename, then rerun package and exact per-scene midpoint QA after the final manifest write. For selective per-segment rebuilds, reordered clips, or accepted title choices, also follow `references/resumed-segment-caption-integrity.md`: treat the canonical manifest—not numbered caption sidecars or a derived render manifest—as the editorial source of truth, prevent stale/index-shifted captions, reuse canonical typography defaults, rebuild downstream derivatives, and verify the exact changed scene.

### Three-title choice after every media upload

After archiving and inspecting each newly received photo or video, offer **exactly three** concise title choices for that material. Make the options meaningfully different rather than punctuation variants: usually one direct/descriptive, one atmospheric or narrative, and one clearly **self-ironic**. Label the self-ironic option so the tone is obvious. Do not silently select or write one of the proposed titles as final; keep the existing provisional title until the user chooses. When the user replies with a number or wording, update that same material's journal title and relevant draft overlay/caption rather than creating a new asset. If the user supplied a title with the media, preserve it as provenance and may include it among the three choices, but still offer the full set unless they explicitly say the title is final.

**Explicit delegation overrides the choice gate.** If the user says **«придумай сам»**, **«выбери сам»**, or otherwise clearly delegates the final wording, generate the normal three semantic candidates internally, choose the strongest one, persist it immediately as final, and report the chosen title without forcing the user through another numbered round. Record that the assistant selected it at the user's request. This exception applies only to title selection; it never implies render or publication approval.

Do not block later uploads while an earlier material still awaits a title: archive each item and track its pending choice independently. A new upload or scene label does **not** select a title for the prior item. Before applying every bare numeric reply, reconcile and count unresolved choice sets from the archive journal. Interpret a bare number only when exactly one unresolved three-choice set exists. **The fact that one set was shown most recently is not enough** when an older material is still pending: ask which material the number refers to, naming the ambiguous materials, rather than applying it by recency guess. If the user later corrects the referent (for example, “имел в виду предыдущий коллаж”), perform an atomic editorial rollback: restore the mistakenly changed material to pending, apply the choice to the intended material, update all affected headings/title fields, and rerender any derived visual whose embedded title changed before reporting success. Follow `references/title-choice-disambiguation-and-derived-artifacts.md`: visually verify changed typography, update derivative size and SHA-256, resend the current artifact, and retain both materials' candidate audit trails.

Persist the exact three proposed choices in the archive journal at the moment they are shown, including which one is self-ironic. This prevents a compacted or resumed conversation from losing what a later bare `1`/`2`/`3` refers to. When the user says **«вернёмся к предыдущим титрам»**, reconcile from the journal rather than reconstructing from chat memory: find every unresolved material, present **one material at a time** so the next numeric reply stays unambiguous, and reuse its stored choice set verbatim. If an old pending record lacks stored choices, regenerate three options and label them as a new set instead of inventing the historical numbering. After each selection, update both the material heading and its selected-title field while retaining the proposed-choice audit trail; after the queue is complete, scan the journal for pending-title markers before claiming that all titles are resolved.

Ground all three choices in the narrative the user stated, not merely the most conspicuous object in the frame. For example, a tram visible in one clip does not justify implying that the whole day is about tram travel when the user described broader public-transport accessibility. If the user says **«попробуй ещё»** or corrects the intended meaning, regenerate all three choices around the corrected semantic axis rather than lightly paraphrasing the rejected wording. Keep the self-ironic option observational and kind: it must not be more self-deprecating or factually stronger than the source material.

### Content-aware destination recommendations

During an active travel story, a restaurant or attraction recommendation may become the next narrative beat. Before recommending, separate **hard experience constraints** (required dish, no buffet/ready-made food, dietary needs, travel limit) from softer goals (iconic with locals, ceremonial guest venue, photogenic route). Verify mandatory dishes against a current first-party menu whenever possible; prestige never compensates for a missing must-have. When content value matters, compare the simplest route with a more cinematic route and explain the trade-off rather than silently optimizing for either. Use `references/cultural-food-content-routing.md` for the decision order, capture arc, and compact response pattern.

## Package layout

```text
<archive>/episodes/<episode-slug>/
├── manifest.json
├── reel-short.mp4
├── telegram-story.mp4           # single editorial Story, when used
├── telegram-story-01.mp4        # numbered full-sequence parts, when used
├── telegram-story-02.mp4
├── telegram-sequence-build.json # ordered indices, durations, sizes, hashes
├── telegram-story-build.json
├── cover.jpg
├── carousel/
│   ├── 01.jpg
│   └── ...
├── instagram-caption.txt
├── youtube-title.txt
├── youtube-description.txt
├── youtube-tags.txt             # required; one accurate tag per line
├── publish-record.json          # only after successful publication
└── verification.json
```

Originals remain outside `episodes/`; never transcode or overwrite them.

## Preparation workflow

1. **Inventory originals and audit story coverage.** Read the archive journal and probe every media file. Build a short coverage checklist from (a) assets marked selected, (b) explicit user observations/jokes, and (c) promised narrative beats. Cross-check it against the manifest before every render; a technically valid package is still incomplete if a memorable archived scene was omitted. Completion: every selected input exists, has known type/dimensions/duration/checksum, and every intended beat is represented or deliberately excluded.
2. **Choose a narrative arc.** Prefer: hook → place → details → contrast/surprise → quiet closer. Preserve the user’s observations as hooks, but distinguish jokes from facts. Treat playful comparisons such as “башня Мстителей” as editorial jokes, not verified identities.
3. **Write `manifest.json`.** Start from `templates/episode.json`. Use paths relative to the archive root. Completion: title, ordered clips, per-scene captions, crop/contain choices, publication copy, YouTube metadata, location, and output directory are populated. Re-run the coverage checklist after every newly supplied or recalled asset.
4. **Render.** Run:

   ```bash
   python3 <skill-dir>/scripts/build_episode.py \
     --archive <archive-root> \
     --manifest <manifest.json>
   ```

   The main builder creates the 9:16 Reel/Short and, when `telegram_story.enabled` is not false, transcodes an approved master of at most 60 seconds into `telegram-story.mp4`. When the user explicitly requests a longer YouTube version and a condensed Telegram version, declare both hard limits in the manifest, render each canonical scene once, concatenate all scenes for YouTube, and concatenate `telegram_story.clip_indices` for Telegram before the 720×1280 transcode. Keep full speaking scenes in both cuts; remove weaker stills or redundant beats instead. For a complete multi-part sequence, declare `telegram_story.sequence.clip_groups` and run `scripts/build_telegram_sequence.py <episode-dir>`. Treat a target such as 30 seconds as soft: split by semantic chapters, even when durations are uneven. Keep event setup with the event it introduces—for example, walking to a venue and its entrance begin the concert chapter rather than ending the previous sightseeing chapter. The Story reuses the same framing, captions, source segments, and approved audio, but may use a shorter manifest-declared ordering. It is not a square crop or chat video note. Every Story part must remain under 60 seconds. The vertical renderer creates a 9:16 H.264/AAC master, 4:5 carousel images, and a cover.
5. **Verify technically and visually.** Run:

   ```bash
   python3 <skill-dir>/scripts/verify_package.py <episode-dir>
   ```

   Then extract a contact sheet and inspect both it and `cover.jpg` as described in `references/media-intake-and-visual-qa.md`. For Shorts, also apply the UI-overlay gate in `references/youtube-shorts-safe-zones.md`: inspect representative frames beneath a current Shorts UI mask or on a real device. Completion: `verification.json` says `ok: true`; the main video is 1080×1920 H.264/AAC; `telegram-story.mp4` is 720×1280 H.264/AAC, playable, non-empty, ≤60 seconds, and ≤30 MiB; cover and carousel exist; every title is fully visible inside safe margins and remains readable beneath platform chrome; selected scenes contain no real blank frames. A green technical report alone is not publish approval.
6. **Preview.** Deliver `reel-short.mp4`, `telegram-story.mp4`, and `cover.jpg`, followed by the exact Instagram caption, YouTube title, and complete YouTube tag list. Tags are mandatory, must be accurate and episode-specific, and must be approved as part of the exact publishing package. The Story preview is the actual full-screen vertical publish candidate; do not apply a circular mask. Label all previews **draft/prepared**, never published.

## Editing rules

- Default vertical output: **1080×1920, 30 fps, H.264 + AAC, yuv420p**.
- For Sergey's captioned travel Reel/Short, aim the visual center of every burned-in episode title and scene caption around 80% of frame height, but preserve a bottom UI reserve with `y=min(h*0.80-text_h/2,h-text_h-360)`. Keep the text left of the action rail with a right edge no farther than `x=820` on the 1080-wide master. This renderer-wide default is applied by `build_episode.py`; the manifest template must not contain `title_y` or `caption_y`, because those would silently override it. Keep explicit overrides only for an exceptional, QA-proven composition.
- Do not add `#Shorts` to YouTube titles or descriptions by default. Current Shorts classification relies on video geometry/duration, while the redundant tag consumes search/title context. Use it only when the user explicitly requests it or a measured campaign requires it.
- **YouTube thumbnail and opening-frame preference for Sergey's travel Shorts:** every Short must have a truthful **1080×1920 vertical** cover prepared and explicitly approved before publication; never rely on an autogenerated frame. Prefer clear faces, one large readable hook, and a short episode-specific support line. Keep text in its own safe panel and never cover faces. Compare every proper name and headline character-by-character with canonical metadata; visual polish does not excuse spelling errors. Embed that exact approved cover into the encoded video from frame zero for roughly `0.5–0.8` seconds, then transition between visible images—never fade in from black, gray, or transparency. Decode and inspect frames at `0.000`, `0.033`, `0.10`, `0.25`, and `0.50` seconds on the final upload candidate. Treat `thumbnails.set` success as API acceptance only: it may update watch/search/Open Graph while the Shorts grid uses a separate portrait-cover surface. Verify the actual Shorts tab or the user's real-device view before claiming the cover is displayed. Follow `references/youtube-short-thumbnails.md`.
- **Sergey travel-edit default for every still:** a landscape/wide photo must fill the 9:16 frame with `fit_mode: "crop"` and move gently with `motion: "pan_left"` or `"pan_right"`; it must not be fully fitted with `contain`. A portrait/tall photo must use `motion: "zoom_in"` or `"zoom_out"`. Alternate directions across adjacent stills. `motion: "none"` is never an acceptable render-performance workaround. Use `contain` or a static frame only after an explicit per-image composition exception is agreed because cover motion would lose irreplaceable separated subjects.
- Use `focus_x` from `0.0` (left) to `1.0` (right) and `focus_y` to keep the visual anchor throughout the crop. For ordinary portrait photos, use the renderer's 2160×3840 working canvas, cosine easing, and about 9–13% travel. The widest point may reach exact cover/full-source scale (`zoom = 1.0`) when that already fills the 1080×1920 canvas; do not impose a global safety overscan merely to avoid reaching full scale. Use per-clip overscan only when the source itself contains an unwanted outer border, and measure the minimum crop that hides it. For designed vertical collages or text-heavy composites, preserve every embedded heading, side label, and footer at **start, midpoint, and end**; normally use `zoom = 1.0` at the widest point and cap travel around 3–5%. If embedded text is clipped, remove clip-specific overscan before weakening or rewriting the design, then rerender and inspect both endpoints. When the user asks to review photo animation, deliver one independently playable MP4 per still scene—without video scenes, contact-sheet substitution, or a combined montage—and retain scene numbers in filenames so corrections map back to the canonical manifest. When a face is present, place the focus between the eyes; for a close pair, use the midpoint between their faces so neither person drifts out of composition. For formulas, source-to-canvas face-coordinate handling, built-in-border measurement, the mandatory render spike, and video-only duplicate-frame QA, read `references/smooth-still-motion.md`.
- A single legacy `caption` spans the whole scene. For normal timed captions, use `captions: [{"text": "…", "start": 0.3, "duration": 2.5}, …]`: `text` is the visible wording, `start` is seconds from the start of that scene, and `duration` is display time in seconds. `end` remains supported as an alternative to `duration`, but never set both. The renderer clips an overlong interval to the end of the scene and rejects empty/negative intervals. This schema lets the script place and style captions automatically rather than tuning each clip.
- Default still duration is 2.7–3.2 seconds. Keep a travel Short concise; do not stretch weak material.
- Preserve useful original speech. Do not synthesize quotes or transcribe uncertain speech as fact. **Never shorten a speaking clip by setting an arbitrary manifest `duration` without checking the audio boundary:** the builder keeps the first N seconds and can cut a sentence mid-phrase. Prefer the full source duration, or create a derived excerpt whose in/out points were verified by listening or reliable transcription. If the ≤60-second budget is tight, shorten stills, redundant establishing shots, or silence before cutting speech. After rendering, listen across every speaking-clip boundary; midpoint contact sheets cannot detect truncated dialogue.
- Add music only if the user provides a licensed/original track or explicitly asks for generated music or platform-library music. When generating music, keep it original: if the user names an existing song, translate that request into high-level era, tempo, instrumentation, rhythm, and mood; never copy its melody, lyrics, recording, hook, or recognisable arrangement. **Music has its own approval gate:** generate and verify a standalone audio preview first, send it for review, and do not insert or mux it into the video until the user explicitly approves that track. After approval, mix into a new draft revision, promote the exact approved mixed file to that revision's canonical `reel-short.mp4`, derive `telegram-story.mp4` from that same master, rerun package verification so both hashes match the upload candidates, and request video approval separately; publication still requires **«публикуй»**. For Sergey's travel edits, preserve the selected genre/mood but prefer acoustic, live-sounding instrumentation over electronic timbres (natural reeds, accordion where appropriate, acoustic guitar, upright bass, muted brass, and natural or regional percussion). Put the lead melody during still-image scenes and retain only a restrained rhythmic bed during ordinary video scenes; when a video already contains music, mark that canonical manifest clip with `"content_type": "music"` and mute **both** generated melody and rhythm for the entire scene. Build and inspect `music-routing.json` with `scripts/build_music_routing.py` before mixing; its required modes are `melody+rhythm` (still), `rhythm` (ordinary video), and `original-only` (music video). When he requests a fixed-gain convention, apply the same gain to both generated stems without ducking, but treat `volume=0.13` only as an initial audition baseline rather than an established final level. Before sending a level candidate, normalize materially mismatched original scene audio, render a music-only routing diagnostic, and compare rhythm-only LUFS on ordinary video with normalized dialogue; do not assume linear gain alone implies audibility. Distinguish a standalone music preview from a mixed-audio preview: when the user asks for “music mixed with the sounds of the video,” deliver synchronized normalized original audio plus routed music, not the standalone composition. Treat melody and rhythm as separate controllable stems/tracks rather than trying to create this contrast with volume changes alone. Do not call this automatic unless a tested renderer/helper and manifest fields actually implement it. For level conventions, speech ducking, provenance, and verification, read `references/generated-music-and-mix-approval.md`. When a hosted music model is unnecessary or unavailable and a reproducible background bed is acceptable, read `references/deterministic-midi-background.md`: fit whole musical bars to the edit, render separate MIDI stems through a documented SoundFont, measure and rebalance stem levels, normalize only the approval preview, and inspect both statistics and a whole-track spectrogram before delivery.
- Use readable titles in safe zones; avoid lower UI overlays and extreme edges. Pre-wrap long titles through UTF-8 `textfile=` input because FFmpeg `drawtext` does not wrap automatically, then visually inspect the rendered title.
- Instagram carousel exports use 1080×1350 (4:5), preserving the whole image over a blurred background.
- Keep factual place and building names conservative. A playful “похоже на Мстителей” stays a joke unless independently verified.

## Publishing workflow

### Preflight

Before any network write, verify:

- package `verification.json` is green and matches the files being uploaded;
- verification was generated after the latest manifest edit and every selected-source change; stale drafts are never publishable;
- target account/channel is configured and named;
- final media order and exact text are known;
- `youtube-tags.txt` exists, is non-empty, contains only accurate episode-specific tags, and its exact list was included in the approved preview package; `publish_youtube.py` must receive it through required `--tags-file`;
- for every YouTube video or Short, a platform-appropriate thumbnail has been prepared, delivered as a separate preview, and explicitly approved for this exact package; never publish with an unreviewed autogenerated frame, and use a vertical `9:16` cover preview for Shorts;
- the user explicitly chose **для своих контактов / для всех / по ссылке** for this publication; map it through the Audience gate and never rely on script defaults;
- no password, token, cookie, or client secret is present in chat, skill text, manifest, or publish record.

The standalone command **«публикуй»** is the approval gate for the latest package. If multiple packages are plausible, ask which one. If one current package is unambiguous, do not add redundant confirmation.

### Telegram Stories

Use `telegram-story.mp4`, never `sendVideoNote`. Authorize the personal account once with `scripts/setup_telegram_user.py`, then call `scripts/publish_telegram_story.py <episode-dir> --audience {contacts,everyone,link} --approved`. `contacts` sends with `inputPrivacyValueAllowContacts`; `everyone` sends with `inputPrivacyValueAllowAll`; `link` performs no Telegram network write and reports the platform as deliberately skipped because Telegram Stories have no link-only audience. The ordinary Hermes Telegram bot connection is not a user session. Bot API `postStory` is an alternative only for a connected managed Telegram Business account whose bot has `can_manage_stories`; its request does not expose privacy rules, so verify audience behavior before relying on it. Follow `references/telegram-stories.md` and publish only after explicit **«публикуй»**. Record only the returned story ID, account identifier, timestamp, expiry, privacy label, and media hash.

### YouTube

Use `scripts/publish_youtube.py` with both required arguments: `--audience {contacts,everyone,link}` and `--tags-file <episode-dir>/youtube-tags.txt`. It maps the audience to YouTube `private`, `public`, and `unlisted` respectively and refuses an empty tag file. After upload, read back `snippet.tags`; an immediate empty read may be propagation lag, so retry briefly before treating the write as failed. Credentials come only from environment variables or an external secret store:

- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

For first-time authorization, missing credentials, the current Google Auth Platform navigation, and safe one-screen-at-a-time guidance, read `references/youtube-oauth-setup.md`. For any credential-bearing attachment or direct handoff, also follow `references/oauth-account-setup.md`: never expose values, quarantine before rotation decisions, and never destroy the only available copy before resolving the user's storage intent. Enabling YouTube Data API v3 is only the prerequisite: the user must still configure OAuth consent, create a client, authorize the intended channel, and grant `youtube.upload`. Also grant `youtube.readonly` when the workflow must verify and display the connected channel, and `youtube.force-ssl` when it must edit metadata on an existing upload. Use `scripts/setup_youtube_oauth.py` for the loopback OAuth flow; it saves credentials atomically to `$HERMES_HOME/.env` with mode `600` and never prints tokens.

The script refreshes OAuth, initiates a resumable YouTube Data API upload, uploads the verified MP4, and prints JSON containing the video ID and URL. Never print tokens.

YouTube Shorts are not a separate API object or upload endpoint: a qualifying vertical/square upload is still a normal YouTube video ID that YouTube classifies and surfaces as a Short. The same ID can open through both `/watch?v=<id>` and `/shorts/<id>`; a working watch URL does **not** mean the Short is listed in the public channel's **Videos** tab. Studio/content-management views may still list all uploaded video objects together. Verify the public **Shorts** and **Videos** tabs separately before describing placement, and prefer reporting the `/shorts/<id>` URL for confirmed Shorts. After `videos.insert`, follow `references/youtube-publish-verification.md`: poll API processing to a terminal success state, verify title and privacy, check the public page when applicable, and only then write the publish record or report completion.

### Instagram

Use `scripts/publish_instagram.py`. Instagram’s API fetches media itself, so the Reel must first be available at a temporary HTTPS URL reachable by Meta. Required environment:

- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_USER_ID`
- `INSTAGRAM_API_VERSION` (optional; script default is documented inside it)

Pass `--video-url` and the caption file. The script creates a Reel container, polls it until ready, then publishes it. Do not upload to an arbitrary public host without the user’s configured hosting destination.

For carousel publishing, use the same official container workflow only after each item has a public HTTPS URL. If public hosting is not configured, stop after preparing the local carousel package and say exactly what remains.

### Publish record

After each successful target, write `publish-record.json` containing only:

- platform;
- timestamp;
- returned post/video ID and URL;
- SHA-256 of uploaded media;
- visibility.

Do not store credentials or API responses containing tokens.

## Failure handling

- If the messaging platform rejects or omits an attachment before a local path is created because of an upload-size limit, do not infer content and do not ask the user to describe it as a substitute for media QA. State the observed limit and request one actionable retry: send with platform compression, export at 720p, split the clip, or provide an accessible download link. Archive and analyze only after real bytes are available.
- For short live-event clips that do arrive, probe metadata and checksum the original, generate a uniformly sampled contact sheet, identify camera-shake/occlusion intervals, and recommend a stable 5–10 second range rather than using the whole clip by default. Preserve useful original concert ambience unless the user separately approves replacement music.
- One platform can succeed while another fails. Report per-platform state; never claim atomicity.
- A failed upload does not authorize an automatic duplicate. Query returned state or retry only when duplicate risk is ruled out.
- If OAuth/permissions are missing, keep the package ready and report the exact setup gap.
- If Instagram cannot fetch the media URL, verify HTTPS reachability and content type; do not replace the URL with local paths.
- If an API rejects format/length, update constraints from the current official docs, rerender, and verify.

## Current ecosystem note

A search of local skills and GitHub skill files found useful components but no ready-made end-to-end skill combining travel archiving, FFmpeg rendering, Instagram publishing, YouTube Shorts upload, and a hard approval gate. This skill composes the local `photo-story-archive` with official Meta and Google upload APIs rather than importing an unrelated marketing skill.

## Verification checklist

- [ ] Originals preserved and checksummed
- [ ] Manifest lists every chosen asset in narrative order
- [ ] Rendered MP4 passes `verify_package.py`
- [ ] `telegram-story.mp4` is derived from the approved vertical master, is 720×1280 H.264/AAC, decodes cleanly, remains ≤60 seconds and ≤30 MiB, and its SHA-256 is present in `verification.json`
- [ ] Telegram publication targets Stories, never a chat video note; contacts/public audiences use the matching MTProto privacy rule after **«публикуй»**, while link-only deliberately skips Telegram
- [ ] If Telegram delivery is a multi-part sequence, every part is ≤60 seconds, split only at verified scene/audio boundaries, independently decoded and hashed, ordered deterministically, and covered by available active Story slots
- [ ] If setup crosses a Kubernetes host/pod boundary, the helper is verified in the pod/PVC and the user receives a tested `kubectl exec -it` command with namespace, workload, and container derived from real state—not a container path presented as host-local
- [ ] Every scene caption and crop passes midpoint-frame visual QA and still matches the visible subject
- [ ] Every animated still fills the canvas at its widest point; ordinary photos may reach exact cover scale, while bordered composites use only measured per-clip overscan
- [ ] Every text-heavy collage preserves all embedded headings, side labels, and footers at start, midpoint, and end
- [ ] If per-photo animation review was requested, one decoded, scene-numbered MP4 was delivered for each still scene, with no video scenes or contact-sheet substitution
- [ ] After any reordered or selective render, caption presence comes from the current canonical manifest; no stale numbered sidecar or index-shifted text appears on no-caption scenes
- [ ] Recovery/segment renderers reuse the canonical typography defaults rather than copied position constants
- [ ] Any generated `drawtext` expression containing commas has escaped filter separators, passes the unit assertion, and has been exercised by at least one real FFmpeg render
- [ ] Timed-caption QA samples before, inside, and after the requested interval, confirming that `text` / `start` / `duration` control actual visibility
- [ ] Representative title/caption frames pass a current mobile Shorts UI overlay or real-device screenshot check; no essential text collides with the right action rail or lower metadata/navigation
- [ ] YouTube metadata includes a reviewed, non-empty, episode-specific tag list from `youtube-tags.txt`; the upload command received required `--tags-file`; API readback confirms the tags after propagation; redundant `#Shorts` is omitted unless explicitly requested
- [ ] The YouTube Short has a truthful, explicitly approved 1080×1920 vertical cover from authentic source media; faces are unobstructed and every proper name/headline exactly matches canonical metadata
- [ ] The exact approved cover is encoded from frame zero for roughly `0.5–0.8` seconds; decoded samples at `0.000`, `0.033`, `0.10`, `0.25`, and `0.50` seconds contain no black/gray/transparent start or fade from blank
- [ ] `thumbnails.set` acceptance is recorded separately from display verification; the actual Shorts grid or the user's real-device view—not only `maxresdefault.jpg`, Open Graph, or a Telegram preview—confirms what viewers see
- [ ] Cover and carousel are present
- [ ] Exact Instagram and YouTube text shown to the user
- [ ] Any generated/licensed music was previewed as standalone audio and explicitly approved before being inserted into the video
- [ ] Music provenance and rights are clear; no referenced song melody, lyrics, hook, arrangement, or recording was copied
- [ ] When original speech/ambience/embedded concert levels differ materially, source audio was measured and normalized scene-wise before music mixing, with capped boost for very quiet ambience
- [ ] Mixed music level matches the current approval candidate; a routed music-only diagnostic confirms the rhythm bed is measurably audible under ordinary video, with no clipping or abrupt gain jumps
- [ ] Standalone music, mixed-audio, and mixed-video previews are labeled distinctly; a request for music “mixed with video sounds” is never answered with the standalone track
- [ ] Every source video containing music is tagged `content_type: music`; generated routing marks those intervals `original-only`, with both melody and rhythm stems silent
- [ ] No credentials stored in files or chat
- [ ] No publication before explicit “публикуй”
- [ ] Audience was explicitly chosen for this publication; YouTube and Telegram used the documented mapping, and Telegram was skipped for link-only audience
- [ ] For an approved replacement, the new upload is verified before the old ID is validated and deleted; retain the old item only by explicit request
- [ ] Successful external writes backed by returned IDs/URLs and recorded hashes
