# Frame-exact cover-inclusive timeline

Use for any publish candidate that prepends an approved platform cover to a visual timeline.

## Why this exists

MP4 `format.duration` can include AAC encoder padding. For a CFR visual story, the authoritative visual duration is:

```text
video_frame_count / target_fps
```

Do not derive scene boundaries or score routing from container durations.

## Build contract

1. Probe each scene with `ffprobe -count_frames`.
2. For each scene, normalize video to `settb=AVTB,setpts=PTS-STARTPTS,fps=30,setsar=1,format=yuv420p`.
3. Trim real audio and generated silence to the exact `frame_count / 30` before `concat=v=1:a=1`. This removes only codec padding after the final visual frame; it is not an editorial speech trim.
4. Add a cover by exact frame count (e.g. 24 frames at 30 fps = 0.8 s), not a floating `-t` alone.
5. Build the cover plus story with one filter concat and one final encode. Do not use TS/MP4 stream-copy concat as a publish timeline.
6. Hand the resulting cover-inclusive MP4 and exact frame contract to `story-soundtrack`; it is the source of truth for soundtrack length and routing.

## Gates

- `start_time=0`;
- `r_frame_rate=avg_frame_rate=30/1`;
- exact expected frame count: `cover_frames + sum(scene_frames)`;
- full decode passes;
- inspect exact frame indices, not input seeking. For a 24-frame cover, extract `n=0`, `n=23`, `n=24` with `select='eq(n,INDEX)'`. Input-side `-ss` can seek to a keyframe and falsely show the first live frame for a cover timestamp.

## Soundtrack handoff

After the final visual timeline passes these gates, stop soundtrack work in `shorts-assembly`. `story-soundtrack` owns composition, routing, audio-only review and approval against this exact frame-derived timeline. Resume assembly only after receiving its hash-bound approved handoff.
