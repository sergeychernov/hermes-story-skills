# Incremental per-photo review

Use this workflow whenever a new still image is added to an active travel episode. Its purpose is to catch crop, motion, embedded-text, and overlay problems without repeatedly rebuilding the full episode.

## Required sequence

1. **Archive and register the photo.** Preserve the original; add the photo to the canonical manifest with its scene number and selected/provisional title.
2. **Configure the complete still scene immediately.** Set its duration, cover crop or collage framing, focus point, motion path, easing, and title/timed captions. A review clip without the actual titles is not representative of the final scene.
3. **Render only the affected photo scene.** Use the same renderer, canvas, typography, frame rate, and motion math that the eventual full episode will use. Do not rebuild the full episode at this stage.
4. **Verify the individual result.** Decode the complete clip and inspect start, midpoint, and end. Require full canvas coverage at the widest point; check faces and focal subjects; for designed collages, keep every embedded heading, side label, and footer visible throughout.
5. **Deliver one independently playable preview.** Send the scene-numbered MP4 for that photo immediately. Do not substitute a contact sheet, a single frame, a combined montage, or the full episode.
6. **Apply feedback locally.** Change and rerender only that photo scene, then resend that scene's preview. Preserve other approved photo previews.
7. **Promote only after approval.** Record per-photo approval in the canonical manifest. Once all photo scenes are approved, build the full episode once, mux the approved audio, regenerate verification for the exact publication candidate, and send the full preview.

## State and invalidation

- A new or changed selected photo makes the prior full render and package verification stale.
- Approval belongs to the exact scene render settings and title text, not merely to the source photo.
- A title change, motion change, crop change, or typography change invalidates that photo's approval and requires a new individual preview.
- Never publish a full candidate whose hash is absent from the current green verification record, even if its video and audio were separately decoded during ad-hoc QA.

## Common pitfalls

- Rendering all scenes after every photo correction makes review unnecessarily slow.
- Sending animation-only clips without the actual titles postpones typography failures until the expensive full render.
- Global overscan can hide source borders but crop text-heavy collages; ordinary photos may reach exact cover scale, while bordered composites need measured per-clip handling.
- Sampling only one endpoint misses zoom-in text loss and zoom-out edge exposure; always inspect start, midpoint, and end.
