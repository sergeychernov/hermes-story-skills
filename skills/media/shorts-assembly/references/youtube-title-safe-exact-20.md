# YouTube title-safe placement: exact 28% means exact

## Durable rule

For Sergey's vertical 9:16 exports, the complete title box—including `boxborderw`—must end at the 72%-of-height boundary. The lower 28% is reserved for delivery UI and must contain no title pixels.

"At least 15%" is not equivalent to "15%" when the user expects efficient use of the frame. Do not add an undocumented aesthetic lift.

## Correct vertical expression

For `drawtext`, where `y` addresses the text and the box extends by `boxborderw`:

```text
y = h*0.72 - text_h - boxborderw
```

This makes the box bottom exactly `h*0.72`.

Avoid:

```text
y = min(h*0.70-text_h/2, h*0.72-text_h-boxborderw)
```

The first branch is a second stylistic constraint. With a typical two-line 1080×1920 title (`text_h≈109`, `boxborderw=24`), it places the box bottom around `y=1423`, leaving about 498 px or 25.9% clear—roughly 114 px / 5.9 percentage points more than requested.

## Horizontal controls zone

Keep the complete box left of the configured right-side controls boundary. Account for `boxborderw`, not just `text_w`.

## Composition and aspect ratio

Title-safe placement is independent from media fill:

- use aspect-preserving `cover` when the frame must be edge-to-edge;
- do not use `contain` with black padding merely to create a caption area unless the user explicitly approves that design;
- never use non-uniform scale;
- inspect whether `cover` crops faces or key action before delivery.

## Verification gate

1. Obtain actual `text_h` for the rendered title or make the renderer's geometry deterministic.
2. Compute the complete box bottom: `title_y + text_h + boxborderw`.
3. Assert it equals `0.72 * frame_height` within rounding tolerance.
4. Assert the complete box is left of the right-controls boundary.
5. Inspect start/middle/end frames for crop, faces, and empty/black areas.
6. Deliver the actual MP4 preview; JPEGs are internal QA only.
