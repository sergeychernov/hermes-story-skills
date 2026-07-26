# Decomposing Story Creation and Social Publishing

Use this reference when `travel-social-publisher` is being refactored, when animation code needs independent testing, or when deciding which skill owns a new rule.

## Core boundary

**Storytelling is domain-neutral. Travel is only one possible source of context.** Do not create a `travel-story` abstraction or require location, route, destination, or trip metadata in the canonical story model.

A small story may concern a family event, concert, meal, project, walk, repair, joke, or trip. Model its narrative with neutral beats such as:

```text
hook → setup → development → turn/payoff → closing
```

Every beat is optional; a three-scene story may simply be `setup → surprise → reaction`.

## Target responsibilities

| Skill/component | Owns | Must not own |
|---|---|---|
| `travel` | Itinerary, places, routes, schedules, traveller constraints, optional capture suggestions | Story assembly, animation, publishing |
| `story` | Narrative arc, scene order, title choices, per-scene approvals, story state, coordination of renderers | Travel-specific assumptions, platform credentials |
| `photo-story-archive` or future `media-story-archive` | Preserved originals, checksums, stable material IDs, journal, chronological and editorial ordering | Rendering, OAuth, network publication |
| `still-image-animation` | One image plus motion specification to one verified video scene | Episode order, travel context, publication approval |
| optional `story-renderer` | Concatenating approved scenes into a verified master | Narrative decisions, external publication |
| `social-publisher` | Platform adapters, OAuth, audience and explicit publication gates, read-back verification | Story composition and image animation |

Dependency direction should remain one-way:

```text
travel ──optional context/capture ideas──▶ story
story ──scene specification──────────────▶ still-image-animation
story ──verified package─────────────────▶ social-publisher
```

`story` must not need to know whether its context originated in `travel`.

## Skill composition semantics

A skill is an instruction document, not a callable software module. For staged orchestration, the `story` skill should explicitly tell Hermes which other skill to load at each phase. Do not preload OAuth/publishing instructions while merely ingesting media.

Use a bundle only for workflows that truly need the same skills loaded together every time. A bundle does not install dependencies and missing skills are skipped. `metadata.hermes.related_skills` aids discovery but does not guarantee loading.

## Canonical contracts

Prefer explicit, versioned JSON contracts between components.

### Still-image animation input

```json
{
  "schema_version": 1,
  "source": "photo.jpg",
  "output": "scene-004.mp4",
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "duration": 3.0,
  "fit_mode": "crop",
  "motion": "pan_right",
  "focus_x": 0.55,
  "focus_y": 0.42,
  "title": "Optional scene title"
}
```

The renderer returns a machine-readable report containing dimensions, duration, codec, hash, decode status, and visual checks. It must not infer story order or publication state.

### Domain-neutral story state

Keep travel-only fields optional under context rather than required at the root:

```json
{
  "schema_version": 1,
  "id": "story-id",
  "title": "Small story",
  "status": "collecting",
  "story_type": "moment",
  "arc": {"beats": ["setup", "surprise", "reaction"]},
  "scenes": [],
  "context": {
    "occasion": null,
    "people": [],
    "places": [],
    "source": "conversation"
  },
  "publication": {"status": "not-approved"}
}
```

## Testing the extracted still renderer

Use three layers:

1. **Pure unit tests:** focus clamping, pan/zoom geometry, easing, frame count, escaping, invalid modes.
2. **CLI contract tests:** schema validation, safe paths, overwrite policy, stable result schema, actionable failures.
3. **Real FFmpeg integration tests:** render generated landscape/portrait fixtures, decode the MP4, probe geometry/fps/duration, and inspect start/mid/end frames for blank edges, real movement, focus retention, and safe-zone placement.

Do not use an exact MP4 hash as a visual regression oracle because encoder output can vary across FFmpeg versions. Compare extracted frames with tolerances or SSIM. Generate fixtures deterministically so tests do not depend on private travel media.

Existing tests that only assert fragments of an FFmpeg filter string are useful unit coverage but do not prove that FFmpeg accepts the graph or that the rendered motion is visually correct.

## Safe migration sequence

Avoid a big-bang rewrite:

1. Add characterization tests around the current renderer, including at least one real FFmpeg render.
2. Extract pure motion geometry and a single-image CLI without changing output behavior.
3. Make the existing episode builder call the extracted implementation through a thin compatibility adapter.
4. Introduce the domain-neutral `story` orchestrator and canonical state contract.
5. Extract platform/OAuth code into `social-publisher` while preserving approval and audience gates.
6. Narrow the archive to originals, metadata, journal, stable IDs, and order.
7. Keep `travel-social-publisher` temporarily as a compatibility façade or bundle; archive it only after consumers and references migrate.

Each step should be independently reviewable and leave the old path working until parity is verified.

## Pitfalls

- Do not replace one monolith with many tiny one-session skills; each extracted skill must have a reusable class-level contract.
- Do not name the story orchestrator `travel-story`; that incorrectly makes travel the parent domain.
- Do not copy shared rules into every skill. Assign one owner and link to it.
- Do not let the orchestrator implement renderer internals or platform API calls.
- Do not claim delegation merely because `related_skills` is present.
- Do not move scripts before characterization tests establish observable parity.
