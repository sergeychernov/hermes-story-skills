# Full-story preview assembly

Use this when the user explicitly asks to watch every prepared scene as one uninterrupted review video, without imposing a platform duration limit.

## Review-artifact semantics

- Read scene order from the story manifest, never filename sort order.
- Pending approval does not block an explicitly requested review montage; it still blocks final approval and publication.
- Include every expected scene. Rebuild corrupt/missing exports instead of silently omitting them.
- Do not alter archived originals.

## Mixed audio invariant

A reliable concatenation has matching streams for every segment:

- real video: preserve the already cleaned/normalized AAC derivative;
- photo/collage video: add stereo silence (`anullsrc=r=48000:cl=stereo`), trimmed to the exact video duration;
- final: AAC, 48 kHz, stereo throughout.

Do not concatenate MP4s with alternating absent/present audio streams and assume sound will survive.

## Fast stream-copy path

Use when every clip is H.264 with the same width, height and frame rate. Profile metadata or limited/full-range flags may differ, so the final full decode and visual contact sheet remain mandatory.

For an audio-bearing segment:

```bash
ffmpeg -y -i scene.mp4 -map 0:v:0 -map 0:a:0 \
  -c copy -bsf:v h264_mp4toannexb -f mpegts scene.ts
```

For a silent segment:

```bash
DURATION=$(ffprobe -v error -show_entries format=duration \
  -of default=nw=1:nk=1 scene.mp4)
ffmpeg -y -i scene.mp4 -f lavfi -t "$DURATION" \
  -i anullsrc=r=48000:cl=stereo \
  -map 0:v:0 -map 1:a:0 -c:v copy -bsf:v h264_mp4toannexb \
  -c:a aac -b:a 192k -ar 48000 -ac 2 -shortest -f mpegts scene.ts
```

Build a concat-demuxer list in manifest order, then:

```bash
ffmpeg -y -f concat -safe 0 -i concat.txt -c copy \
  -bsf:a aac_adtstoasc -movflags +faststart final.tmp.mp4
```

Decode and probe `final.tmp.mp4`; only then atomically rename it to the final name. If compatibility or decode checks fail, use one normalization encode to common video/audio parameters rather than weakening verification.

Small duration growth from AAC frame boundaries is expected. A practical tolerance is the larger of 0.5 seconds or one 1024-sample AAC frame per segment.

## Interrupted-render recovery

An interrupted command may leave a large `.tmp.mp4` without a `moov` atom. File size is not readiness evidence.

1. Check whether the named final output exists.
2. Check whether the original process is still tracked/running.
3. Probe and full-decode any orphan temp before considering reuse.
4. Delete/restart only when the orphan is invalid; do not launch duplicate encodes blindly.
5. Never tell the user the video is ready while only an unverified temp exists.

Prefer a bounded background process with completion notification for a full re-encode. For a compatible mixed-media preview, the stream-copy path is usually much faster and less exposed to chat-turn interruption.

## Delivery verification

Before attaching the MP4:

- final named file exists;
- `ffprobe` confirms expected dimensions/FPS, H.264 video, AAC 48 kHz stereo;
- full decode exits successfully;
- actual duration is within tolerance of summed scene durations;
- one labelled midpoint frame per scene forms a complete contact sheet in editorial order;
- start, middle and final frames are clean;
- a non-silent window is confirmed inside every real video scene;
- SHA-256 and a report are written;
- report states that the artifact is for review and is not published.

Attach the MP4 itself in the completion response; a last-frame JPEG is supplementary, never a substitute.