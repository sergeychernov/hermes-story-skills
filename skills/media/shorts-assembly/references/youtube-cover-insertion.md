# Cover approval and lossless insertion

Use this when inserting an approved cover/thumbnail into a vertical family film or Short before upload (YouTube Shorts, Telegram Stories, Instagram Reels).

## Approval sequence

1. Build the cover as a standalone 1080×1920 JPEG from authentic user media. Keep text on a dedicated panel or another area that does not cover faces/action.
2. Run literal typography and crop QA.
3. Deliver the JPEG by itself and say explicitly that neither video insertion nor upload has occurred.
4. Wait for explicit approval or a command such as «вставь в видео».
5. Only then create a new upload-candidate MP4. Showing a cover is not permission to alter the approved master or publish it.

## First-frame safeguard

Two modes — pick based on how the platform shows previews:

- **Intro mode** (YouTube-style): keep the approved cover visible from frame zero for about 0.5–0.8 s. Verify exact decoded frames at 0.000, 0.033, 0.100, 0.250, and 0.500 s; verify the transition to live video immediately after the cover interval. No first-frame fade from black. When the user wants a coherent soundtrack, do **not** glue a separate ident ahead of an already approved music mix: first form the normalized cover-inclusive video timeline, then compose/render one new soundtrack from its `t=0`. The cover motif must continue naturally into the story theme; preserve source speech and route the new music around it. Do not delegate the composition to a coding agent when the user explicitly requests direct authorship. A short separate ident is only a review asset until the user approves its character.

  **Audio-first approval gate:** after the cover-inclusive visual timeline is frame-verified, render the complete speech-aware **audio-only** mix and deliver it for listening. Wait for explicit approval before muxing it into video, creating an upload MP4, or publishing. For a requested gain adjustment, rebuild and deliver only audio again; do not spend a video encode/mux cycle. Apply exact linear changes (e.g. `+20%` = current linear gain × `1.20`) and record the resulting dB. Independently measure the encoded AAC true peak with `ebur128`: AAC may overshoot a PCM limiter, so retain/rebuild with enough headroom until the delivered audio itself meets the peak ceiling.
- **Single-frame mode** («обложка одним фреймом», Telegram/Instagram-style previews): the cover is exactly ONE video frame (1/fps s — e.g. 1/30 s at 30 fps), just so the platform picks it up as the preview. No intro music. Audio alignment: prepend exactly one frame of silence to the approved mix (`aevalsrc=0:0:d=0.033333:s=48000:c=stereo`, then concat) so every scene keeps its approved timing — never trim or re-time the approved mix. Verify frame 0 (t=0.000) is the full cover and frame 1 (t≈0.034 s) is already live footage.

## Fast insertion without re-encoding the whole film

Re-encoding is the last resort: on the NUC even `veryfast` x264 of ~65 s 1080×1920 exceeds a 600 s foreground command. Copy-concat is allowed **only after a packet-timeline preflight**, not merely because both files report `30 fps`:

- `r_frame_rate`, **exact** `avg_frame_rate`, `time_base`, `start_time`, geometry, pixel format/range, profile and level must match;
- video packet durations must match the intended CFR cadence;
- the master must start at zero. A non-zero video `start_time` (for example `0.021`) or a nominal `r_frame_rate=30/1` paired with a different `avg_frame_rate` means the source is not safely copy-concat compatible;
- B-frame DTS reordering is normal inside one H.264 stream, but the concatenated output must still have strictly increasing packet DTS and an exact expected cadence.

If **any** check differs, do not try to repair it with `-itsoffset`, `-avoid_negative_ts`, or a second remux: use a one-pass CFR normalization encode of the complete new candidate. More importantly, fix the *parent assembler* so a future publish master is born with video and audio both at `PTS=0`: `settb=AVTB,setpts=PTS-STARTPTS,fps=<target>` for video and `asetpts=PTS-STARTPTS` for audio in the final normalizing encode. The cover segment must use the same geometry, frame rate, pixel format, H.264 profile/level, AAC rate, and channel layout as that normalized candidate (add `-video_track_timescale 90000`).

Preferred copy path — concat demuxer with a file list (only after that preflight passes):

```bash
cat > concat.txt <<EOF
ffconcat version 1.0
file '/abs/path/cover-segment.mp4'
file '/abs/path/approved-master.mp4'
EOF
ffmpeg -y -f concat -safe 0 -i concat.txt -map 0:v:0 -c copy -an video-with-cover.mp4
```

Then mux the audio separately with `-c copy` and **without `-shortest`** (see pitfalls).

Legacy copy path — MPEG-TS concat:

```bash
ffmpeg -y -i cover-intro.mp4 \
  -c copy -bsf:v h264_mp4toannexb -f mpegts cover-intro.ts
ffmpeg -y -i approved-master.mp4 \
  -c copy -bsf:v h264_mp4toannexb -f mpegts approved-master.ts
ffmpeg -y -fflags +genpts \
  -i 'concat:cover-intro.ts|approved-master.ts' \
  -c copy -bsf:a aac_adtstoasc -movflags +faststart upload-candidate.mp4
```

Pitfalls observed with copy concat:

- The MPEG-TS path can **silently drop one master frame** when the master has a non-zero video `start_time` (e.g. 0.021 s): the output decodes cleanly but `nb_read_frames` equals master frames instead of master+inserted. Only the frame-count identity check catches this.
- A concat-demuxer copy can appear to succeed yet produce an absurd nominal frame rate (e.g. 240 fps) and non-monotonic DTS warnings when timebases, actual cadence, or start offsets mismatch. A matching `r_frame_rate` alone is insufficient: a master with `avg_frame_rate≈29.89`, `start_time=0.021`, and an intro at exact `30/1` is incompatible. **Never patch this with timestamp-remux flags and retry.** Reject it and run the one-pass CFR normalization path.
- Do not trust decode success as timeline proof: `ffmpeg -f null` can decode a file that has invalid/non-monotonic packet timestamps. Inspect packet DTS monotonicity explicitly.
- Muxing with `-shortest` while the audio track runs longer than video drops the last video frame(s). Mux without it and rely on the frame-count check instead.

## Required verification

- `ffprobe`: exact geometry (e.g. 1080×1920), H.264, AAC 48 kHz stereo, nominal 30 fps. For every copy-concat attempt, also require exact equality of `r_frame_rate`, `avg_frame_rate`, `time_base`, `start_time`, pixel format/range, profile, and level between segments before concat; otherwise choose CFR normalization.
- **Packet-timeline gate**: inspect first/last video packets plus the complete DTS series. Reject equal/decreasing DTS, unexpected gaps, any non-zero output start offset, or a resulting `avg_frame_rate` that differs from the requested CFR.
- **Frame-count identity**: `ffprobe -count_frames -show_entries stream=nb_read_frames` must equal master frames + inserted frames. Any mismatch means a frame was silently dropped — rebuild, do not deliver.
- Full decode with `ffmpeg -v error -i upload-candidate.mp4 -f null -`. This is necessary but never substitutes for the packet-timeline gate.
- Reject any output with non-monotonic DTS, implausible `r_frame_rate`, or decode errors.
- Build a first-frame contact sheet covering the cover interval (intro mode: 0.000–0.750 s; single-frame mode: exactly 0.000 and ≈0.034 s) and inspect it visually.
- Recompute SHA-256 and create a fresh package verification record; inserting a cover changes the upload media hash.
