# Title-choice disambiguation and derived-artifact consistency

Use this procedure whenever several photos, videos, collages, or other derivatives can have unresolved title choices.

## Before applying a bare number

1. Reconcile unresolved title markers from the archive journal; do not rely only on the latest chat turn.
2. Count unresolved choice sets.
3. Apply `1` / `2` / `3` automatically only when exactly one unresolved set exists **and** no intervening upload, regenerated choice set, or explicit reference makes another target plausible.
4. If two or more sets remain unresolved, ask which material the number refers to. The most recently displayed set is not sufficient evidence by itself.
5. Persist the shown candidates verbatim so a later selection can be mapped without reconstructing options from memory.

## When the user corrects the target

If a number was applied to the wrong material:

1. Revert the mistakenly updated material to `Титр ожидает выбора` and restore its unresolved title field.
2. Apply the selected option to the material the user named.
3. Keep both materials' candidate audit trails intact.
4. Re-scan the journal for unresolved markers before saying which titles remain.

## Derived images with embedded titles

A collage, cover, carousel card, or rendered frame may contain the provisional title in pixels. A journal-only edit is incomplete.

When its title changes:

1. Regenerate or edit the derivative so the exact selected wording appears in the image.
2. Check that every line is fully visible, faces are not newly covered, and the design still fits the target aspect ratio and safe zones.
3. Recompute byte size and SHA-256 and patch those values in the journal/manifest.
4. Deliver the updated artifact again; the previously sent preview is stale.
5. Never alter preserved source originals while updating a derivative.

## Compact response pattern

- On ambiguous number: `К какому материалу относится вариант 2: к коллажу или к последнему видео?`
- After correction: confirm the corrected material, state that the mistaken material is pending again, and resend any derivative whose embedded text changed.
