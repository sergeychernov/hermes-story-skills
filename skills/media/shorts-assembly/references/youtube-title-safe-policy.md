# YouTube title-safe policy

For Sergey's vertical 9:16 exports, the complete title box, including `boxborderw`, must end exactly at the 72%-of-height boundary. The lower 28% must contain no title pixels. Reserve the configured right-side controls zone as well.

Use `scripts/youtube_safe_title.py` as the only geometry source for still, video, and collage renderers. Do not duplicate percentages or formulas in project scripts.

## Geometry

For FFmpeg `drawtext`, where `y` addresses the text origin:

```text
y = h*0.72 - text_h - boxborderw
```

This pins the complete box bottom to `h*0.72`. Do not combine it with a second aesthetic anchor that silently lifts the title.

`middle` is allowed only when explicitly approved or when the lower position would obscure a primary story subject that cannot be protected by crop or layout. `bottom` is not a YouTube-safe option.

## Media fill

Title geometry does not authorize a black footer or empty caption band. Preserve aspect ratio and use content-aware `cover` for edge-to-edge media unless the user explicitly approves `contain`. Never stretch.

## Verification

1. Generate geometry with `youtube_safe_title.py`.
2. Confirm `bottom_free == 0.28`.
3. Confirm `title_y + text_h + boxborderw == 0.72 * frame_height` within rounding tolerance.
4. Confirm the complete title box remains left of the configured controls strip.
5. Inspect start, middle, and end frames for crop, faces, clipping, black gaps, and title position.
6. Fully decode and deliver the actual MP4 preview; JPEGs are internal QA only.
