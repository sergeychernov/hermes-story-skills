# YouTube title-safe policy: correction record

## Durable lesson

A title-safe percentage is a policy, not a per-renderer tuning knob. For Sergey's vertical YouTube workflow:

- the complete title box, including `boxborderw`, must stay out of the lower 28%;
- reserve the right-side controls zone as well;
- use `scripts/youtube_safe_title.py` as the only geometry source for still, video, and collage renderers;
- `middle` is allowed when it avoids faces or story anchors; `bottom` is not a YouTube-safe option;
- start/middle/end JPEGs are internal QA, not a substitute for the corrected MP4 preview requested by the user.

## Regression pattern to avoid

The failed workflow had separate hard-coded formulas in several renderers. A real Shorts screenshot showed that the former 15% clearance left titles under the metadata and promotion controls. Visual inspection without the actual client UI did not prevent policy drift. Centralize constants, test the 1080x1920 and 720x1280 rectangles, then render and fully decode the real MP4 preview.

## Verification checklist

1. Generate geometry with `youtube_safe_title.py`.
2. Confirm `bottom_free == 0.28` and the title box bottom is exactly `0.72 * height` within rounding tolerance.
3. Confirm the title box right edge remains left of the reserved controls strip.
4. Inspect start/middle/end frames for faces, clipping, and composition.
5. Fully decode the MP4.
6. Deliver the MP4 itself; still frames may only supplement it.
