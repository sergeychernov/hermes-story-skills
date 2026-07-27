---
name: travel-social-publisher
description: Compatibility facade for existing travel media archives and episode manifests. Routes new storytelling to the domain-neutral story skill, still animation to still-image-animation, and external writes to social-publisher while retaining the legacy package renderer during migration.
version: 2.0.0
author: Sergey Chernov / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [travel, compatibility, migration, story, publishing]
    related_skills: [story, photo-story-archive, still-image-animation, social-publisher, travel-planning]
---

# Travel Social Publisher — compatibility facade

## Status

This skill preserves existing travel episode manifests, archive paths, render scripts, and commands while responsibility moves to composable skills. Do not add new domain logic here.

Storytelling is domain-neutral. Travel is only optional context.

## Route every request

| Request | Load and use |
|---|---|
| Add photo/video, choose titles, form a small story, approve scenes | `story` plus `photo-story-archive` |
| Animate or debug one photo scene | `still-image-animation` |
| Plan a trip, route, venue, or live transit | `travel-planning`, `maps`, or `live-transit-navigation` as appropriate |
| Publish a verified package, configure OAuth, inspect upload state | `social-publisher` |
| Rebuild an existing legacy `episode.json` package | compatibility renderer in this skill |

Loading this facade does not automatically load those skills. Explicitly load the owner before acting.

## Legacy rendering only

Existing archives may continue to run:

```bash
python3 <skill-dir>/scripts/build_episode.py \
  --archive <archive-root> \
  --manifest <manifest.json>

python3 <skill-dir>/scripts/verify_package.py <episode-dir>
```

`build_episode.py` now delegates still motion/filter generation to `still-image-animation`. Publication and OAuth script paths here are compatibility adapters that execute the implementation owned by `social-publisher`.

Do not start new stories from `templates/episode.json`; use the `story` manifest instead. Do not archive or rename this facade until current archives and external references are migrated and parity is verified.

## Preserved invariants

- Preserve originals and stable archive IDs.
- New photos receive three title choices, including one self-ironic option.
- Render and approve one photo scene at a time before any full story render.
- Preserve speech; shorten stills first.
- Music, mixed video, publication, and audience each have separate approval gates.
- Never publish before explicit **«публикуй»**.
- No credentials in Git, manifests, reports, or chat.

For migration contracts and dependency direction, read `references/skill-decomposition-and-story-boundaries.md`.
