# Frame-exact YouTube Shorts cover timeline

Use for Sergey's YouTube Shorts publication candidate. Other platform intros are separate edits and must not reuse this report contract.

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
4. Render exactly four cover frames at 30 fps. Frames `0..3` are the same approved cover and frame `4` is the first live frame. One-frame and longer intervals are invalid for this publication path.
5. Build the cover plus story with one filter concat and one final encode. Do not use TS/MP4 stream-copy concat as a publish timeline.
6. Hand the resulting cover-inclusive MP4 and exact frame contract to `story-soundtrack`; it is the source of truth for soundtrack length and routing.

## Gates

- `start_time=0`;
- `r_frame_rate=avg_frame_rate=30/1`;
- exact expected frame count: `cover_frames + sum(scene_frames)`;
- full decode passes;
- inspect exact frame indices, not input seeking: extract `n=0`, `n=1`, `n=2`, `n=3`, and `n=4` with `select='eq(n,INDEX)'`; require high SSIM among `0..3` and require frame `4` to differ from the cover. Input-side `-ss` can seek to a keyframe and falsely show the wrong boundary.

## Soundtrack handoff

After the final visual timeline passes these gates, stop soundtrack work in `shorts-assembly`. `story-soundtrack` owns composition, routing, audio-only review and approval against this exact frame-derived timeline. Resume assembly only after receiving its hash-bound approved handoff.
