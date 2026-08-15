# Spoken-video audio integrity

Use this when a story clip contains speech or the user asks for denoise/normalization.

## Preserve the speech contract

- Archive the original unchanged.
- Default to the full source timeline for conversational clips. Never infer that a visually dark, shaky, or inactive section is disposable: it may contain speech.
- Trim only after explicit approval of the exact range. A later instruction to keep the whole clip invalidates every earlier `start`, `end`, `-ss`, `-t`, or silence-removal decision.
- Avoid `silenceremove`, hard noise gates, and aggressive thresholds that can remove quiet consonants, word endings, or low-level speech.

## Conservative derivative chain

A practical FFmpeg baseline for spoken social video is:

```text
afftdn=nr=12:nf=-35:tn=1,loudnorm=I=-16:LRA=11:TP=-1.5
```

Encode the derivative audio as AAC stereo and explicitly force `-ar 48000`; `loudnorm` may otherwise produce a 96 kHz intermediate/output depending on the filter graph. Treat these values as a baseline, not a substitute for listening: back off denoise when the voice sounds metallic or pumps.

## Verification

1. Probe source and output with `ffprobe`; compare container and per-stream `start_time` and `duration`.
2. For a full-clip render, output audio must span the complete source audio timeline, allowing only codec/frame rounding. Confirm video and audio start alignment rather than checking container duration alone.
3. Measure the finished encoded file, not only the pre-encode filter output. Use EBU R128/`ebur128=peak=true` or equivalent to record integrated loudness and true peak. AAC encoding can raise measured peaks slightly; require no clipping and leave practical headroom.
4. Decode the whole output successfully. Inspect beginning, middle, and end; listen to or transcribe the complete speech when tools permit, especially the first and last words.
5. Record the exact filter chain, measured loudness/peak, source range, output duration, and verification result in the scene manifest.

## Failure patterns

- **Words disappear after a visual trim:** restore the full source and rerender; do not try to reconstruct speech from the trimmed derivative.
- **Output is unexpectedly longer/offset:** inspect stream start times. Input-side fast seeking plus copied audio can preserve pre-roll from a previous keyframe. If a trim is explicitly approved, decode/re-encode both streams and verify alignment.
- **Peak target differs after AAC:** measure the encoded file and lower the loudnorm true-peak target if more headroom is needed; never report the configured target as the measured result.
