# Resumable render and package recovery

Use this when a long episode build is interrupted after some outputs have already been produced. The goal is to resume from the last verified stage rather than rerendering an expensive master blindly.

## Stage-aware recovery

1. **Inventory outputs before retrying.** Probe every existing MP4 with `ffprobe`; file existence or non-zero size is not sufficient. A killed MP4 encode can lack its final `moov` atom and be unusable.
2. **Keep a valid vertical master.** If `reel-short.mp4` probes correctly, matches the manifest's intended duration, and decodes with `ffmpeg -v error -i ... -f null -`, do not rebuild it merely because a later Telegram transcode or still export was interrupted.
3. **Resume downstream stages independently.** From a verified master, rebuild `telegram-story.mp4`, then create the cover, carousel, copy files, and `build-result.json`. Run the normal package verifier only after every required artifact exists.
4. **Write video outputs atomically.** Transcode into a temporary filename in the destination directory, probe and decode it, then rename it to the canonical filename. Remove an invalid partial canonical output before retrying.
5. **Re-verify after manifest changes.** Editorial notes, exclusions, reordered clips, or new selected media make an earlier `verification.json` stale even if the video bytes did not change. Run verification again after the final manifest write.

## Telegram Story fallback

Prefer `build_telegram_story.py`. If a constrained runner requires a direct fallback, derive the Story from the already-verified 1080×1920 master, not from individual clips:

```bash
ffmpeg -y -v error -i reel-short.mp4 \
  -vf 'scale=720:1280:flags=lanczos,fps=30' \
  -c:v libx264 -preset fast -crf 23 \
  -profile:v high -level:v 4.1 -g 30 -keyint_min 30 -sc_threshold 0 \
  -tag:v avc1 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -ar 48000 -movflags +faststart \
  telegram-story.tmp.mp4
```

If runtime is the limiting factor, a faster preset is acceptable only when the result still passes visual QA and the Story constraints. Do not claim success until all are verified:

- 720×1280, H.264 + AAC, playable and fully decodable;
- duration no longer than 60 seconds;
- size no greater than 30 MiB;
- content, captions, ordering, and audio match the approved master;
- temporary file atomically promoted to `telegram-story.mp4` only after checks pass.

## Midpoint visual QA after recovery

Generate one frame at the exact midpoint of every manifest clip using cumulative clip durations, tile them in editorial order, and inspect scene numbers, captions, crop, faces, landmarks, blank frames, and safe zones. A periodic `fps=1/3` sheet may miss short clips and is not a substitute for this scene-complete gate.

Also inspect the cover separately and run an audio-level probe on the final master. Preserve original speech and live ambience; do not add music during recovery unless the music approval gate was already completed.
