# YouTube title-safe placement: exact 28% means exact

## Durable rule

For Sergey's vertical 9:16 exports, the complete title box—including `boxborderw`—must end exactly at the 72%-of-height boundary. The lower 28% must contain no title pixels. This is an exact placement rule, not merely a minimum clearance.

## Shared geometry

Use `scripts/youtube_safe_title.py` as the only source of title geometry for stills, video, and collages:

```text
y = h*0.72 - text_h - boxborderw
```

Because FFmpeg `drawtext` addresses the text origin, subtracting `text_h` and `boxborderw` pins the complete box bottom to `h*0.72`.

Do not combine this with another aesthetic anchor such as:

```text
y = min(h*0.70-text_h/2, h*0.72-text_h-boxborderw)
```

That silently lifts short or multiline titles above the requested line.

## No implicit per-scene exceptions

The shared lower position is the default invariant. Do not switch a scene to `middle` merely to avoid covering incidental pedestrians, background crowds, or other non-story subjects. Such people may be covered when the title preserves the named subject and action. Use `middle` only when the user explicitly requests it or when the lower position would obscure a primary story subject that cannot be protected by crop/layout; disclose the exception before rendering.

## Media fill is independent

Title-safe placement must not create a black footer or empty caption band. Preserve aspect ratio and use content-aware `cover` for edge-to-edge media unless the user explicitly approves `contain`. Never stretch.

## Verification

1. Assert `bottom_free == 0.28`.
2. Assert `title_y + text_h + boxborderw == 0.72 * frame_height` within rounding tolerance.
3. Assert the complete title box remains left of the configured controls strip.
4. Inspect start/middle/end for crop, faces, clipping, black gaps, and title position.
5. Fully decode and deliver the actual MP4 preview; JPEGs are internal QA only.
