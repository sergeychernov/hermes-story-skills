# Title preflight and horizontal-still composition

## Long-title preflight

`drawtext` renders explicit newlines but does not wrap text. A technically successful render can therefore clip a long line at the right edge.

Before rendering:

1. Keep the approved wording exact.
2. Estimate or measure each line against the canonical safe width, including `boxborderw` and the right-side controls reservation.
3. Insert semantic 2–3 line breaks; prefer balanced lines over reducing the branded font.
4. Render and inspect start, middle, and end frames.
5. Reject if any glyph or box edge is clipped, or if the box covers a face, measurement, sign, label, or story-critical object.
6. Move the complete title block or revise crop/motion before changing approved wording or typography.

Typical correction:

```text
Too long:
Оказалось, мы тоже
местная достопримечательность

Safer:
Оказалось, мы тоже
местная
достопримечательность
```

## Horizontal stills in 9:16

Sergey's default delivery policy is: no stretch, no blurred filler, and no empty bands.

Preference order:

1. Use a subject-preserving 9:16 crop with all essential people/actions retained.
2. If the whole horizontal image is essential, design a non-blurred canvas/layout using real image content or a deliberate graphic treatment.
3. Treat `contain` over a blurred duplicate only as an explicit, separately approved exception—not a silent default.

Always inspect start/middle/end for subject clipping, black gaps, filler artifacts, and title overlap.