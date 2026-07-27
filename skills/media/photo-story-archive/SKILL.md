---
name: photo-story-archive
description: Build a durable chronological photo/video journal, prepare Instagram and YouTube Shorts packages, and enforce explicit approval before publishing.
version: 1.1.4
metadata:
  hermes:
    tags: [photos, video, journal, instagram, reels, youtube-shorts, publishing, archive, travel]
---

# Photo and Video Story Archive

Use this skill when the user sends photos or videos over time and asks to preserve them for an Instagram post, carousel, Stories/Reel sequence, YouTube Short, travel diary, or similar narrative package.

## Goal

Preserve original media durably, keep conversational context in chronological order, and progressively assemble reusable cross-platform publishing material without claiming that anything was posted.

## Workflow

1. **Resolve the archive root and archive boundary.** Prefer a user-specified project or vault. Otherwise use the domain-neutral durable root `~/stories/YYYY-MM-DD-topic/` (`/opt/data/home/stories/` when Hermes runs with its standard homelab `HOME`). Keep every story's originals, previews, music, renders, and publishing packages inside that story directory; do not create platform-named sibling roots or a global music-preview root. Never treat a cache/upload path as the archive. When the user explicitly says **“new archive”**, create a separate root even if another archive exists for the same date or city—do not silently merge by temporal or geographic similarity. If the boundary is supplied as a clarification immediately after one media upload, include that single upload because it prompted the clarification; do not also import media from earlier user turns merely because it is visible nearby in the conversation. If inclusion is genuinely ambiguous, ask once rather than importing older context wholesale.
2. **Preserve the original.** Copy images without recompression into `photos/` and videos without transcoding into `videos/`. Use `YYYY-MM-DD_HH-MM-short-scene-name.ext` and never overwrite a prior upload.
3. **Verify the copy.** Compare source and archive SHA-256. For images, record byte size and dimensions using `scripts/archive_photo.py`. For videos, use `ffprobe` to record duration, dimensions, codecs, frame rate, audio streams, creation time and size; generate a separate contact sheet only for review.
4. **Label time honestly.** Prefer embedded EXIF/container creation time when present. Otherwise record chat receipt/archive time and label the source—do not imply it came from the camera.
5. **Describe conservatively and keep the user's title distinct from analysis.** Identify visible subjects, composition, and mood. When media arrives with a short user-supplied phrase, preserve it verbatim as the material's comment and use it as the display title by default (allowing only minimal capitalization normalization). If the active publishing workflow or user preference requires title choices, treat the phrase as a working title instead: archive first, offer exactly the configured number and style of choices, mark the title as awaiting selection, and patch the journal heading plus title field only after the user chooses. Never silently select a title for them. Put any more specific visual interpretation in the neutral description, not in a replacement title. If the user later renames the material, patch the journal heading and every current manifest/preview label derived from it without renaming the preserved original file unless explicitly requested. Do not assert exact species, people, buildings, brands, or locations unless visually certain or corroborated. Preserve a user's playful comparison as a quote/joke, not as factual identification. When the user explicitly asks **what a visible object or dish is**, answer that identification request before the routine archive confirmation and title-choice step: give the most likely identity, calibrated confidence, and the visible features that distinguish it from plausible alternatives. Preserve the user's wording as provenance, but store uncertain identification as qualified analysis rather than silently upgrading it to fact. For food, distinguish the city where it was served from the dish's regional origin; a dessert photographed in Istanbul is not automatically Istanbul-origin cuisine.
6. **Maintain two kinds of order: stable archive identity and editable story chronology.** Keep one Markdown story file for the trip/event rather than disconnected notes. Every asset gets a stable global material number plus type-specific number and records time, place, filename, scene, mood, orientation, editing/carousel role and draft copy. If the user later supplies an earlier event (for example, arrival after morning scenes were already archived), preserve existing material IDs but move the new scene to its true narrative position and update the manifest's explicit editorial order. Never confuse upload order, receipt time, capture time, and montage order; label each separately. A later clarification such as “this happened before X” overrides earlier inferred sequencing without requiring renumbering all archived assets.
7. **Treat short media messages as continuation—unless the user declares a boundary.** During an active archive sequence, text such as “кактусы на улице”, “пасутся гуси” or “видео приветствие” normally supplies the title/context and means append it. Do not repeatedly ask where to save or whether to continue. However, phrases such as **“новая сессия”**, **“новый архив”**, **“новая публикация”**, or clear equivalents are hard reset markers: start a separate archive/package with the media attached to that boundary message (or the immediately following media), and do **not** backfill preceding chat images, videos, captions, inferred locations, or story context unless the user explicitly asks to import them. A new publishing target (for example, “новая публикация Shorts”) sets the target and collection state; it does not itself authorize publication.
8. **Preserve the journey context within the current archive boundary.** Summarize route and preceding events only from material belonging to that archive, distinguishing confirmed details from assumptions. Mark inferred locations explicitly and invite correction.
9. **Stage social copy and treat corrections as editorial direction.** Add concise post copy, a Stories overlay, and the asset's role. For video, record whether it is a hook, greeting, establishing shot, transition, detail, voiceover bed or ending. Preserve the user's own observation as the strongest hook. When the user adds a detail or correction after an asset—such as noticing riders on the rear step, explaining that an award-sign shot leads into an ordinary tea stop, or noting that a transit ride had no view because it was underground—patch the existing asset record, caption, and adjacent scene relationship instead of creating a duplicate or defending the first interpretation. Prefer a two-shot setup/payoff when the correction naturally creates one. Refine one combined narrative after enough media arrives instead of regenerating a full caption for every upload. Treat visible signage as evidence for exact displayed text, not for stronger claims: a Michelin Guide plaque does not by itself prove a star.
   **Handle reminders and resends as integrity checks.** When the user asks “ты про это не забыл?” or resends an earlier image, hash the new upload and compare it with archived originals. If identical, do not create another material: verify both the story entry and its explicit manifest position, then answer with that evidence. If the bytes differ, preserve it as a distinct original and determine whether it is a better export, crop, or separate shot.
10. **Prepare cross-platform exports.** When the user asks to assemble the story, create an Instagram package and a vertical Reel/YouTube Shorts package from the same source set. Follow `references/video-and-publishing-pipeline.md` for render layout, metadata manifest, audio rights and verification.
11. **Enforce the approval gate.** “Собери”, “подготовь” and “покажи черновик” never authorize publication. Publish only after showing the final manifest and receiving explicit approval such as “публикуй”; any later material edit invalidates that approval.
12. **Publish only through a verified path.** Prefer official platform APIs with credentials held outside the skill/project. If account/API access is unavailable, deliver a complete upload-ready package and state that it was not published.

## Recommended layout

```text
~/stories/
└── YYYY-MM-DD-topic/
    ├── story.md
    ├── photos/                 # untouched image originals
    ├── videos/                 # untouched video originals
    ├── previews/               # review-only contact sheets/thumbnails
    ├── music/                  # preview and approved tracks for this story
    ├── exports/                # rendered platform deliverables
    └── publish-manifest.md     # exact approved revision and status
```

Use `references/archive-schema.md` for journal metadata, `references/video-and-publishing-pipeline.md` for video inspection, cross-platform exports, approval and publishing, and `references/editorial-corrections-and-late-chronology.md` for late-arriving early scenes, duplicate resends, signage-based captions, and setup/payoff corrections.

## Response style

For each additional photo or video, reply briefly with:

- confirmation that it was archived;
- its sequence number and short title;
- one sentence describing its story/editing role.

Do not repeat the archive explanation or full path on every asset unless requested.

## Pitfalls

- Cache paths are temporary; always create a durable copy.
- Keep story assets under `~/stories/<story>/`; do not revive legacy platform-specific roots.
- Do not overwrite assets that share an upload filename.
- Do not silently alter orientation, crop, color, resolution or audio.
- Do not equate ingestion order with story order: late-arriving media may belong at the beginning, while stable material IDs should remain unchanged.
- When a user's correction changes the meaning of two neighboring scenes, update both the corrected scene and their editorial transition/setup-payoff.
- For short clips, choose contact-sheet sampling from actual duration; a fixed interval can produce black/empty tiles.
- Do not confuse archived, rendered, approved and published states.
- Do not expose absolute local paths as public URLs.
- Do not turn a user's visual joke into an unverified factual identity, brand or building claim.
- Do not embed passwords, tokens, cookies or OAuth credentials in the skill, archive or manifest.
- Avoid music without clear rights and location tags that reveal sensitive/private places without user intent.

## Completion check

- [ ] Every original copied to durable storage without transcoding
- [ ] Source and destination checksums match
- [ ] Image/video metadata and time source recorded
- [ ] Chronological journal updated with global and type-specific sequence numbers
- [ ] Location and object-identity certainty represented honestly
- [ ] User wording/jokes preserved without turning them into factual claims
- [ ] Caption/Stories copy and editing role staged
- [ ] Requested platform exports verified end to end
- [ ] Final manifest revision explicitly approved before publication
- [ ] Each successful publication verified by returned ID/URL; failures reported per platform
