# Frame-exact cover-inclusive timeline

Use for any publish candidate that prepends a YouTube/Telegram cover and then composes a score.

## Why this exists

MP4 `format.duration` can include AAC encoder padding. For a CFR visual story, the authoritative visual duration is:

```text
video_frame_count / target_fps
```

Do not derive scene boundaries or score routing from legacy container durations.

## Build contract

1. Probe each scene with `ffprobe -count_frames`.
2. For each scene, normalize video to `settb=AVTB,setpts=PTS-STARTPTS,fps=30,setsar=1,format=yuv420p`.
3. Trim real audio and generated silence to the exact `frame_count / 30` before `concat=v=1:a=1`. This removes only codec padding after the final visual frame; it is not an editorial speech trim.
4. Add a cover by exact frame count (e.g. 24 frames at 30 fps = 0.8 s), not a floating `-t` alone.
5. Build the cover plus story with one filter concat and one final encode. Do not use TS/MP4 stream-copy concat as a publish timeline.
6. Use the resulting cover-inclusive MP4 as the source of truth for score length and voice/silent routing.

## Gates

- `start_time=0`;
- `r_frame_rate=avg_frame_rate=30/1`;
- exact expected frame count: `cover_frames + sum(scene_frames)`;
- full decode passes;
- inspect exact frame indices, not input seeking. For a 24-frame cover, extract `n=0`, `n=23`, `n=24` with `select='eq(n,INDEX)'`. Input-side `-ss` can seek to a keyframe and falsely show the first live frame for a cover timestamp.

## Whole-timeline score

Compose after the final visual timeline passes these gates. The cover ident must be the opening phrase of the same stems, never an appended audio fragment followed by a delayed old mix. Shift every scene boundary from the frame-derived visual timeline and keep speech source plus rhythm/melody routing explicit.
