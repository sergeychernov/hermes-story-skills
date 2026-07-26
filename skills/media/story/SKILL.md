---
name: story
description: Build a small, domain-neutral story from photos, videos, comments, and optional context. Use for family moments, events, projects, walks, meals, jokes, or travel; coordinates archive, titles, per-scene approvals, rendering, music approval, and handoff to publishing without assuming travel.
version: 1.0.0
author: Sergey Chernov / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [story, storytelling, photos, video, narrative, editorial, orchestration]
    related_skills: [photo-story-archive, still-image-animation, social-publisher, travel-planning]
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

Skills are instruction documents, not callable modules. Load dependencies progressively:

1. **Media intake:** load `photo-story-archive`; preserve and checksum originals before editing.
2. **Still scene:** load `still-image-animation`; render exactly one independently playable MP4 for each new photo.
3. **Travel planning/context:** load `travel-planning`, `maps`, or `live-transit-navigation` only when the story actually needs those facts. Store travel data under `context.extensions.travel`; never add travel-only root fields.
4. **Publication:** load `social-publisher` only after the final package is verified and the user asks to publish.

`metadata.hermes.related_skills` is discovery metadata and does not perform these steps automatically.

## Workflow

### 1. Collect and preserve

- Establish one explicit story/archive boundary.
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

### 6. Music is a separate gate

Generate/select and deliver the standalone track first. Do not mix it into video until explicitly approved. For Sergey's default, prefer acoustic instrumentation, fixed gain without ducking, melody on photos, rhythm on ordinary video, and silence generated stems under source video that already contains music. Video approval and publication approval remain separate.

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
- [ ] Music, video, publication, and audience approvals remain separate
- [ ] No credentials in manifests, reports, or chat
