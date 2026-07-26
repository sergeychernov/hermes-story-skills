# Caption integrity during resumed and selective renders

Use this reference when an episode is rebuilt from cached per-scene MP4s, pre-rendered stills, or a derived render manifest.

## Source-of-truth rule

The current canonical `manifest.json` decides whether a scene has a title or caption. Sidecar files such as `.caption-08-00.txt` are generated artifacts, not evidence that a caption belongs to the current scene.

Never add an overlay merely because a sidecar file exists. A removed or reordered clip can leave a valid-looking stale file at the same numeric index and burn the previous scene's text into an unrelated scene.

## Selective rebuild transaction

When changing one title or accepting a numbered title choice:

1. Reconcile pending title-choice sets in the journal and resolve the selected wording.
2. Update the journal and canonical manifest together.
3. Regenerate any derived render manifest from the canonical manifest, or update the same clip in both while asserting the source path identifies the intended scene.
4. Delete or overwrite that scene's caption sidecars from current manifest data. Remove sidecars for scenes that no longer have `caption` / `captions`.
5. Re-render the affected normalized scene segment.
6. Re-concatenate the master and regenerate every downstream derivative from that master.
7. Run package verification, full decode checks, and exact-timeline visual QA of the changed scene.
8. Update recorded sizes and hashes only after verification.

Completion: the changed scene shows the selected wording, scenes without current manifest captions show no inherited text, and every derivative hash belongs to the rebuilt master.

## Renderer implementation guard

Caption rendering must be conditioned on current semantic data:

```python
if clip.get("caption") or clip.get("captions"):
    render_current_caption_sidecar()
```

Do not use this unsafe condition:

```python
if caption_sidecar.exists():
    render_caption_sidecar()
```

Before a full render, clear stale numbered caption sidecars or generate them in a revision-scoped temporary directory.

## Prevent recovery-script drift

A recovery renderer must reuse canonical typography defaults from `build_episode.py`—position, wrapping, font size, safe horizontal limits, box style—instead of copying magic values such as `h-820`. Prefer importing a shared helper/constants module. If temporary duplication is unavoidable, add a test asserting the recovery filter uses the same global defaults as the canonical renderer.

Likewise, a derived render manifest must not become an independent editorial source. Recreate it after every canonical manifest edit or validate scene identity and caption fields before selective rendering.

## Visual QA checklist

- [ ] Selected title is exact, including punctuation and diacritics
- [ ] Text block uses the current global vertical position
- [ ] Face and primary subject remain unobscured
- [ ] Text is not clipped at frame edges
- [ ] No-caption scenes contain no stale overlays
- [ ] Scenes after an insertion/removal did not inherit index-shifted captions
- [ ] Reel and platform derivatives decode cleanly and match fresh verification hashes
