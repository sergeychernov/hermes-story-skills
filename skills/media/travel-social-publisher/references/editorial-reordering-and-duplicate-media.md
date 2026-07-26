# Editorial reordering and duplicate-media exclusion

Use this reference when the user asks to place a clip “before/after” another scene, construct an intentional narrative that differs from capture order, or remove “the other clip” using only a visual description.

## Preserve chronology while allowing editorial order

Keep two separate facts:

1. **Capture chronology** — camera/EXIF creation time when available; otherwise explicitly label filesystem or ingest time.
2. **Editorial order** — the scene position requested by the user.

Never rewrite capture metadata to make a constructed sequence appear chronological. In the journal/manifest, record an editorial position such as `immediately before <material-id>` and state that it is an intentional montage reconstruction when the timing differs or is uncertain. This preserves provenance without blocking creative storytelling.

When inserting a late-arriving clip:

1. Probe and checksum the original.
2. Archive it without transcoding.
3. Inspect a uniformly sampled contact sheet.
4. Add it to the manifest at the requested narrative position, not merely at the end by ingest time.
5. Mark any existing render and verification record stale.
6. Re-render and verify the sequence before claiming the episode is updated.

## Resolve “remove the other clip” safely

A visual description is not a filename. Before removing anything:

1. Inventory candidate media across the active archive and, when relevant, the current ingest cache.
2. Generate a labeled contact sheet with one or more representative frames per candidate. Use filenames in the labels.
3. Identify every candidate matching the description.
4. Compute SHA-256 for visually similar candidates. Two paths with the same hash are exact duplicates and should be treated as one editorial source.
5. Search the journal and manifest for every matching path/hash.
6. Remove or mark excluded in the **manifest/editorial selection**. Preserve originals and cache files unless the user explicitly asks for filesystem deletion.
7. Record the exclusion by stable hash and, if useful, list all duplicate paths so the same clip cannot return under another filename.
8. Verify the requested replacement order in the manifest/contact sheet after the change.

If several non-identical candidates still match, ask the user to choose from a compact labeled contact sheet rather than guessing. If one exact duplicate group is the only plausible match, exclude the whole group editorially and report that duplicate copies were found.

## Compact journal pattern

```markdown
- **Capture time:** 2026-07-26 00:22:19 (UTC+3)
- **Editorial position:** immediately before material 12 by explicit user direction; montage reconstruction, not confirmed chronology
- **Selected source:** `videos/new-scene.mp4`, SHA-256 `<hash>`
- **Excluded source:** visual duplicate group `<hash>` (`cache/a.mp4`, `cache/b.mp4`); excluded from manifest, originals preserved
```

## Pitfalls

- Do not equate “remove from the video” with “delete the only original.”
- Do not silently change creation time to justify an editorial sequence.
- Do not identify a vaguely described clip from filenames alone.
- Do not exclude only one pathname when another exact duplicate can be reselected later.
- Do not claim a montage change is complete until an existing manifest/render is updated and reverified; changing only the journal is bookkeeping, not a finished export.
