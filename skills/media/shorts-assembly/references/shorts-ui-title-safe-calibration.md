# Calibrating title-safe placement against the real Shorts UI

Use this when a user screenshot shows burned-in titles colliding with current YouTube Shorts controls, metadata, promotion prompts, or channel text.

## Durable method

1. Treat the user's real-device screenshot as authoritative for the Shorts surface. A clean encoded frame without UI is insufficient evidence.
2. Identify the highest bottom-overlay element that can obscure a title (promotion prompt, channel row, video title, audience row, or share affordance).
3. Choose one centralized proportional boundary for the **bottom edge of the complete title box**, including `boxborderw`; do not tune scenes independently.
4. Update `scripts/youtube_safe_title.py` first, then RED→GREEN tests for its FFmpeg expression and 1080×1920 safe rectangle.
5. Run consumer suites for still-image animation and animated collage; project renderers must import the helper rather than duplicate percentages.
6. Render a representative real scene, fully decode it, and inspect a late-hold frame. When possible, compare that frame against the supplied UI screenshot.
7. Update documentation and search for stale hard-coded expressions in legacy project scripts.

## Current calibrated policy

For Sergey's vertical YouTube Shorts workflow, pin the complete title-box bottom to `0.72 × frame height`, leaving the lower `28%` title-free. Keep the right-side controls reservation unchanged. For 1080×1920, the vertical safe-rectangle height is 1382 px (rounded).

FFmpeg expression with a 24 px box border:

```text
y = h*0.72 - text_h - 24
```

This is a UI-safe overlay policy, not a request to add a blank footer: media still fills the 9:16 frame.

## Regression warning

Do not infer safety from YouTube's conventional custom thumbnail or from a player frame without controls. The watch/search thumbnail, Shorts grid cover, and in-player Shorts UI are separate surfaces. A real screenshot can invalidate a previously reasonable percentage.