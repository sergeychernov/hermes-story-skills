---
name: story
description: Build a small, domain-neutral story from photos, videos, comments, and optional context. Use for family moments, events, projects, walks, meals, jokes, or travel; coordinates archive, titles, per-scene approvals, rendering, music approval, and handoff to publishing without assuming travel.
version: 1.2.0
author: Sergey Chernov / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [story, storytelling, photos, video, narrative, editorial, orchestration]
    related_skills: [photo-story-archive, still-image-animation, animated-collage, scene-group, media-voiceover, static-cover-collage, story-soundtrack, shorts-assembly, social-publisher, travel-planning]
---

# Story

## Core boundary

Build **small stories from media**. A story may concern a family event, meal, concert, project, repair, joke, walk, or trip. Travel is optional context, never the parent domain.

Use neutral beats such as:

```text
hook → setup → development → turn/payoff → closing
```

All beats are optional. A three-scene story may be `setup → surprise → reaction`.

This skill owns narrative arc, scene order, title choices, editorial state, approval gates, and orchestration. It must not implement image-motion geometry, archive storage, OAuth, or platform API calls.

## Explicit skill delegation

Skills are instruction documents, not callable modules. Load dependencies progressively and keep ownership explicit:

1. **Media intake:** load `photo-story-archive`; preserve and checksum originals before editing.
2. **One still scene:** load `still-image-animation`; render exactly one independently playable MP4 for each new photo.
3. **Multi-photo scene:** load `animated-collage`; keep originals immutable and let that skill own card geometry, motion and collage QA.
4. **Reusable scene unit:** load `scene-group` when several approved scenes become one editorial beat; group state, composition and duration belong there.
5. **Voiceover:** load `media-voiceover`; preserve the exact recording, prepare only versioned derivatives and approve audio independently from visuals.
6. **Cover:** load `static-cover-collage` for a designed still cover, then `still-image-animation` only when that approved cover must become a timed video scene.
7. **Soundtrack:** after the visual timeline is frame-locked, load `story-soundtrack`. It exclusively owns style, themes, multitrack composition, rhythm/full/source-audio previews, feedback revisions and the hash-bound audio approval handoff.
8. **Final video assembly:** load `shorts-assembly` only for visual concatenation, format/duration delivery and exact mux of the approved `story-soundtrack` handoff. It must not recompose, reroute, normalize or otherwise alter approved audio.
9. **Travel planning/context:** load `travel-planning`, `maps`, or `live-transit-navigation` only when the story needs those facts. Store travel data under `context.extensions.travel`; never add travel-only root fields.
10. **Publication:** load `social-publisher` only after the final package is verified and the user asks to publish.

`metadata.hermes.related_skills` is discovery metadata and does not perform these steps automatically.

## Workflow

### 1. Collect and preserve

- Establish one explicit story/archive boundary.
- Treat a concise kickoff such as `Story <title>` as an explicit request to start a new empty story with that title, even when no media is attached. Create the durable archive layout, an empty valid manifest in `collecting` state, and a journal; do not import earlier media implicitly. Confirm briefly and invite the first photo or video.
- Inspect and archive each real media file; never infer unavailable media.
- Preserve capture chronology separately from editorial order.
- Record user comments as provenance; distinguish jokes from verified facts.

### 2. Title each material

After every new photo or video, offer exactly three concise choices:

1. direct/descriptive;
2. atmospheric/narrative;
3. clearly self-ironic, observational and kind.

Persist the exact choice set. Do not apply a bare number if multiple materials still have unresolved choices. If the user explicitly delegates the choice, select and record the strongest candidate without another round.

### 3. Build the narrative

- Create a version-1 manifest from `templates/story.json`.
- Use only neutral root fields.
- Put domain-specific data in `context.extensions.<domain>`.
- Give each scene a stable, non-empty string `id` and `media_id`; surrounding whitespace is normalized away.
- Keep story state independent from chat memory.

Validate it:

```bash
python3 <skill-dir>/scripts/validate_story.py draft.json --output story.json
```

### 4. Review each photo scene

For every newly added photo:

1. configure title, crop, focus, and motion;
2. delegate one-image rendering to `still-image-animation`;
3. verify and visually inspect start/middle/end;
4. send the individual scene preview;
5. mark the scene approved only after the user's approval.

Do not render or resend the full story while any photo scene remains pending. New video may be inspected and staged without rebuilding the whole package.

### 5. Assemble and verify

Only when `render_ready: true`:

- assemble approved scenes in editorial order;
- preserve speech; shorten stills and redundant beats before cutting spoken phrases;
- keep vertical stories at 9:16 and ≤60 seconds unless the user chooses another target;
- split longer outputs at semantic boundaries;
- verify exact scene order, titles, audio boundaries, dimensions, duration, hashes, and representative frames.

During migration, the rendering portion of `travel-social-publisher` may be used as a compatibility adapter, but its travel assumptions and publishing steps do not become part of this skill.

### 6. Soundtrack is an independent production and approval flow

Do not compose, route or mix music inside `story` or `shorts-assembly`. Once the visual timeline is frame-locked, load `story-soundtrack` and pass it the exact timeline plus an evidence-based JSON map of source audio, themes, style and declared climax.

The required checkpoints are:

1. approve the composition plan: style, instrumentation, themes, dramatic development and climax;
2. render and actually attach the mixed rhythm-section preview;
3. render and actually attach the complete score preview;
4. mix that score with the preserved audio from the video scenes and attach the audio-only source-mixed preview;
5. accept user objections as a revision loop: preserve prior artifacts, create a new numbered spec/output revision, change only requested targets and repeat the affected previews;
6. after explicit user approval, bind the exact mixed-audio hash, timeline hash, duration and PCM frame count into the `story-soundtrack` approval/handoff manifest;
7. only then load `shorts-assembly` and allow visual assembly plus exact mux. No denoise, loudness normalization, ducking, stem routing, trimming or other audio transformation is permitted after handoff.

A path, manifest entry, report, waveform or technical summary is not delivery. Every checkpoint file must be a real playable attachment in the response asking for approval. Container fallback may change M4A to MP3 or audio-transport MP4, but it must preserve the exact checkpoint content; a static-cover visualizer never substitutes for the requested full story or source-mixed audio.

Music approval, source-mix approval, video approval and publication approval remain separate. Any style, theme, source-audio, routing, gain, timeline or duration change invalidates downstream soundtrack approval and returns the workflow to the affected `story-soundtrack` checkpoint.

### 7. Publication handoff

A prepared/verified story is not publication permission. On an explicit publishing request, load `social-publisher`, pass the exact verified package, and complete its separate audience and approval gates.

## State model

```text
COLLECTING → TITLE_REVIEW → SCENE_REVIEW → READY_TO_RENDER
→ RENDERED → VERIFIED → PUBLISH_APPROVED → PUBLISHED
```

Any selected-source, title, order, crop, audio, or metadata change makes downstream render verification stale.

## Verification checklist

- [ ] Story works without any place, route, destination, or trip field
- [ ] Originals preserved and checksummed
- [ ] Exact three title choices persisted per material
- [ ] Every photo has an independently reviewed scene preview
- [ ] `validate_story.py` passes and reports no pending scene IDs before full render
- [ ] Speech boundaries and representative frames inspected
- [ ] Rhythm-section, full-score, source-mixed audio, video, publication, and audience approvals remain separate
- [ ] Approved soundtrack handoff hash and exact PCM frame count match the audio muxed by `shorts-assembly`
- [ ] No credentials in manifests, reports, or chat
