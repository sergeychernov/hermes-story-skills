# Concert burst collage workflow

Use this when several near-adjacent concert photos show one performer, gesture, prop, or visual detail and the user wants an interesting collage rather than four repetitive story scenes.

## Intake and archive

1. Treat the burst as one editorial material with several preserved source assets, not as several independent story beats, when the frames are clearly one moment and the requested output is one composite.
2. Archive every original without recompression and record a checksum for each source.
3. Perform frame-by-frame visual QA before design. Rank frames by:
   - strongest expression for the hero;
   - clearest chronological/action progression for secondary panels;
   - sharpest view of the requested detail for an inset.
4. Do not claim that a tiny detail is visible merely because the user described it. Inspect the source crop and phrase uncertain appearance conservatively.

## Recommended 9:16 composition

For four portrait frames, a reliable 1080×1920 layout is:

- one large hero frame occupying roughly the upper half;
- three smaller sequential frames as a film strip below it;
- one magnified circular or elliptical detail inset overlapping a low-information part of the hero;
- a short callout attached to the inset;
- a dark concert-toned background with one restrained accent colour sampled from the detail.

Keep the original photos unretouched. The collage is a separate derived export under `exports/`.

## Text and safe-zone rules

- Use a concise headline; do not let venue labels or callouts extend beyond their background pills.
- Prefer a short inset label such as `СЛЕД ПОМАДЫ` over an explanatory sentence.
- Important text must remain readable at phone size and clear of platform chrome. Bottom decorative copy is optional and must not carry essential meaning.
- If a title is still awaiting user choice, the image containing one candidate is explicitly a draft. Regenerate the headline if the user selects a different option.

## Verification loop

1. Save the export at exactly 1080×1920.
2. Reopen it and verify dimensions, nonzero size, and checksum.
3. Inspect the rendered image visually—not just the source frames—for:
   - clipped letters or labels;
   - text escaping its pill or panel;
   - cut-off faces or hands;
   - the inset obscuring the main subject;
   - whether the magnified detail is actually legible;
   - weak balance caused by repeated near-identical frames.
4. Correct visible defects and run a second visual inspection before delivery.
5. If the embedded title changes after a user's numbered choice or correction, rerender the export, recompute its byte size and checksum, and atomically update the journal's heading, selected-title field, and derived-file metadata. Do not leave the visual, journal, and hash describing different revisions.
6. Deliver the actual file, then offer exactly three concise title choices unless the user explicitly delegated title selection.

## Montage integration

A collage can replace several repetitive still scenes with one 2.7–3.2 second scene. Recalculate the episode duration after adding it. If a new energetic concert video arrives, prefer replacing part of an earlier concert clip rather than extending an already near-60-second master.
