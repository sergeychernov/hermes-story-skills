# Review-first, aspect-safe story assembly

Use this when revising or assembling mixed photo/video stories, especially when one scene is flagged after a full preview.

## Geometry invariant

Never normalize a source with bare anisotropic scaling such as `scale=1080:1920` unless its decoded display aspect ratio already equals 9:16. That command silently deforms 3:4 and other sources.

Probe every video before rendering. Preserve geometry with one of these deliberate modes:

- **Cover:** `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1`. Use only when the crop retains faces, hands, text, and the story object.
- **Contain/title-safe composition:** `scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:0:color=black,setsar=1`. This keeps the complete frame at the top and creates a lower title-safe band. Prefer it for 3:4 talking selfies when cover would enlarge a face and put the lower-fifth title across the mouth.

After either mode, inspect start, middle, and end frames. Confirm natural face/object proportions and title clearance. `width=1080,height=1920` in `ffprobe` proves canvas size, not preservation of source geometry.

## Review before rebuilding

When the user flags one scene in an already assembled story:

1. Mark the full preview stale because its scene hash no longer matches.
2. Rebuild only the affected scene.
3. Deliver separate start/middle/end JPEGs, not a contact sheet and not another full-story render.
4. Wait for approval of those frames before rebuilding the full sequence.

This is both faster and easier to review. Never spend time recomposing or re-encoding the entire film while the local scene decision remains unresolved.

## Mixed-media concatenation

Give every segment the same stream topology. Preserve the cleaned AAC audio of real videos; add silent AAC 48 kHz stereo to photo/collage segments. Concatenate in editorial manifest order, never filename order.

When H.264 dimensions, frame rate, and time base are compatible, a fast review build can stream-copy video via MPEG-TS intermediates while adding audio only to silent scenes. Verify SPS/pixel-format changes are decodable across boundaries. Otherwise normalize and re-encode deliberately.

Always use an atomic temporary output. Before delivery, require full decode, `ffprobe`, ordered midpoint evidence, and non-silent audio probes inside every source-video interval.

## Delivery preflight

Before attaching a long preview, inspect its actual byte size and distinguish platform rejection from transport failure. For Telegram, re-check the current official `sendVideo` contract; as of Bot API 10.x it accepts MPEG4 video up to 50,000,000 bytes and returns a `Message` on success. Preserve the full-resolution publication master separately and use a smaller review-only derivative when desired or when the official/adapter size cap requires it. Do **not** recompress merely because delivery failed: inspect the active gateway log first. `Request Entity Too Large` is a size problem; `Timed out` requires proxy/connect/media-write-timeout diagnosis. Require full decode, exact frame/fps/duration preservation, matching copied-audio packet hash, first/middle/last visual QA, and a returned Telegram `message_id`. Never place the chat derivative into the publication package or replace the canonical master path with it. See `telegram-bot-review-delivery.md`.
