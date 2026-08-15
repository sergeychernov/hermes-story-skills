# Cover-inclusive timeline and score

Use this for a YouTube Short whose opening cover must control platform previews.

## Order of operations

1. Preserve originals; create canonical normalized scene derivatives at ingest.
2. Assemble a zero-origin CFR master.
3. Render the visual timeline first: cover (`24` frames / `0.8 s` at 30 fps) + master in one filter graph.
4. Verify the cover-inclusive video before composing music:
   - `start_time=0`;
   - `r_frame_rate=avg_frame_rate=30/1`;
   - expected frame count = cover frames + master frames;
   - full decode succeeds;
   - inspect cover at 0.000, 0.033, 0.100, 0.250, 0.500, final cover frame; inspect first live frame at 0.800.
5. Compose rhythm and melody stems against the exact new duration from `t=0`. The intro motif is the first phrase of the score, not a separately appended ident.
6. Make cover an explicit `silent` routing window. At first live `voice` frame, keep continuous rhythm at the approved speech level and set melody to zero; silent scenes receive full rhythm + melody.
7. Create a new full music bed and speech-aware mix. Do not delay/reuse a pre-cover mix.

## Timeline pitfalls

- H.264 B-frame DTS can be negative and is not itself failure. The publish gate is presentation timing: video/audio origins must be zero and output cadence must be exactly CFR.
- MPEG-TS `h264_mp4toannexb` stream-copy assembly can preserve per-scene PTS offsets. A file may decode successfully while its video begins after audio or its effective cadence differs from nominal metadata.
- `concat` requires matching SAR. Normalize every input using `setsar=1`; phone clips may decode to near-1:1 ratios such as `20255:20252`.
- Never accept a candidate only because FFmpeg exits successfully. Reject missing duration, frame-count mismatch, non-monotonic packet timing, non-zero video start, or an unexpected average frame rate.

## Final reporting

Record input hashes, cover duration/frame count, exact final duration, stream timing/cadence, score seed or composition source, scene routing windows, audio loudness/peak, and full-decode status.
