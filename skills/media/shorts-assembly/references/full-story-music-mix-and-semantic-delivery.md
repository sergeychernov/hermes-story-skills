# Full-story music mix and semantic delivery

Use this when the requested review artifact is the actual story video with generated music plus preserved source sound or narration.

## 1. Preserve the requested artifact semantics

A delivery fallback may change only transport properties: container, codec, bitrate, resolution, or attachment type. It must not change the requested content.

- If the requested deliverable is an audio-only score preview, an MP3 or static-cover H.264/AAC MP4 is a valid compatibility fallback.
- If the user asks for a mixed story, full video, or “music plus story sounds,” a static-cover visualizer is **not** a fallback. Assemble and deliver the real story timeline with its scene audio.
- Treat “I expected that as the second file” as evidence that the wrong semantic artifact was delivered, not merely that Telegram rejected a container.

## 2. Audit active artifacts before assembly

The active timeline can still point to early visual/group exports while later narrated revisions exist.

For every scene:

1. resolve the active artifact;
2. search the project manifest/reports for the latest valid narrated revision;
3. confirm title/caption preservation;
4. count decoded video frames;
5. reject a narrated replacement whose frame count changes the approved timeline accidentally.

When a valid narrated preview has one extra video frame because audio padding or copy-mux extended the container, preserve the current exact-frame titled visual and mux the approved audio-first track onto it with an explicit visual duration. Never let AAC padding redefine scene length.

Record the selected scene path, hash, frame count, audio class, and source-audio policy in a versioned mix spec.

## 3. Build the source-audio timeline sample-exactly

At 30 fps and 48 kHz, each video frame corresponds to exactly 1600 audio samples. For each scene:

- `expected_samples = decoded_video_frames × 1600`;
- `silent`: synthesize 48 kHz stereo silence and trim to the exact sample count;
- `voice` / source audio: decode, resample once to 48 kHz stereo, append silence if short, then `atrim=end_sample=expected_samples`;
- concatenate the exact scene audio segments in editorial order.

Do not use MP4 `format.duration` as the authority. Use decoded CFR video frame count.

## 4. Route continuous stems without ducking

Generate rhythm and melody once across the complete final timeline. Change gain envelopes only; never restart or concatenate stems per scene.

Default family-story routing:

- `silent`: full rhythm and melody;
- `voice`: source audio at unity, rhythm `0.456`, melody off;
- `source_music`: source audio only, generated stems off.

Use roughly 300 ms smooth routing transitions, `amix normalize=0`, `dropout_transition=0`, and no automatic ducking unless explicitly requested. A final limiter may protect headroom, but set `level=false` so it does not auto-amplify the mix.

## 5. Render PCM before AAC

Do not render a complex story mix directly to AAC and infer success from `-t`. AAC priming/padding can produce a misleading probe duration and a decoded sample count off by part of a codec frame.

Required sequence:

1. render a PCM WAV master;
2. assert its exact sample count;
3. encode AAC from that PCM with explicit 48 kHz resampling and `atrim=end_sample=...`;
4. probe and fully decode the AAC;
5. record both PCM and AAC hashes.

Keep a rejected direct-AAC attempt as a rejected revision; never overwrite it silently.

## 6. Build a zero-origin visual master

Normalize each selected scene in one FFmpeg filter graph:

```text
settb=AVTB,setpts=PTS-STARTPTS,fps=30,setsar=1,format=yuv420p
```

Then filter-concat the scenes, encode the exact expected frame count, and verify:

- start time `0`;
- `r_frame_rate = avg_frame_rate = 30/1`;
- exact decoded frame count;
- 1080×1920 or declared target canvas;
- full decode.

Mux the already verified AAC via stream copy. Do not use `-shortest`; use the explicit authoritative timeline duration so the final voice ending and hold cannot be truncated.

## 7. Verify voice integrity with exact sample windows

Timestamp seeking with input-side `-ss` is not sample-authoritative for AAC and can yield misleadingly low correlation. For evidence-based checks:

1. fully decode the final audio;
2. extract scene windows with `atrim=start_sample=...:end_sample=...`;
3. compare them with the exact narrated scene audio;
4. allow a small measured AAC/filter delay when computing correlation;
5. verify the final narration window has the full expected sample count.

This verifies that narrated audio reached the final timeline. It does not replace human listening for intelligibility or mix preference.

## 8. Delivery and report

Before attachment, verify non-zero size, channel size limit, stream codecs, duration, exact frame count, full decode, and representative frames for every scene. The report should contain:

- ordered scene paths/hashes/frame counts/classes;
- routing gains and transition duration;
- `ducking`, `amix_normalize`, limiter settings;
- exact PCM sample count and hashes;
- final AAC loudness/true peak;
- visual and final-video hashes/probes;
- exact-window voice-integrity evidence;
- publication approval state.

Attach the real mixed MP4 in the same response that announces completion.