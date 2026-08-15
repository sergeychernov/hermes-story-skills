---
name: media-voiceover
description: Use when adding approved voiceover to a scene or group.
version: 1.0.0
author: Sergey Chernov / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [video, voiceover, own-voice, audio-policy, ffmpeg, mix, qa]
    related_skills: [scene-group, story, shorts-assembly]
---

# Media Voiceover

## Overview

Add an **approved recording of the user's own voice** to either one scene or one rendered group. This skill owns narration preparation, source-audio policy, mixing, and QA. It never groups scenes and never synthesizes or substitutes TTS.

## When to use

Use when a finished target with `kind: scene` or `kind: group` needs the user's recorded narration. Do not use for grouping, text-to-speech, automatic ducking, or modification of originals.

## Workflow

### 1. Choose the target

Set `target.kind` to `scene` or `group`, and `target.path` to its explicit rendered MP4 under `--root`.

Completion: target path and hash identify the exact media version to narrate.

### 2. Preserve and prepare the user's recording

The input is the user's own voice file or voice message.

1. Preserve the original recording and record SHA-256.
2. Inspect duration, sample rate, channels, clipping, leading/trailing silence, and intelligibility.
3. Apply conservative noise reduction to the derivative by default for Sergey's own voiceovers (for example a restrained FFT denoiser with noise tracking), unless he explicitly asks to preserve the recording untreated. Avoid aggressive gates or silence removal that can damage quiet syllables. Then apply only explicitly requested trims, fixed gain, loudness normalization, or format conversion. Never overwrite the original.
4. Record the exact denoise filter and parameters in the report or story journal.
5. Deliver the prepared **audio-only** derivative.
6. Wait for explicit approval.
7. Set `voiceover.path` to that exact approved file.

Never generate or substitute TTS. Completion: the approved audio-only derivative hash matches `voiceover.path`.

### 3. Set target source-audio policy

| `source_audio` | Behavior |
|---|---|
| `preserve` (default) | Keep target audio at its existing level; missing audio becomes explicit silence |
| `remove` | Replace target audio with silence |
| `lower` | Apply required fixed non-positive `gain_db` to target audio |
| `boost` | Apply required fixed positive `gain_db` to unusually quiet target audio |

There is no automatic ducking. For narration over live sound, choose an explicit fixed reduction.

### 4. Validate and render

Start from `templates/voiceover.json`:

```bash
python3 <skill-dir>/scripts/validate_media_voiceover.py \
  --root <media-root> --spec <media-root>/voiceover.json
python3 <skill-dir>/scripts/render_media_voiceover.py \
  --root <media-root> --spec <media-root>/voiceover.json
```

The renderer locks output to decoded target video duration, mixes at fixed gains without ducking, emits H.264 `yuv420p` plus AAC 48 kHz stereo, verifies source immutability and full decoding, and atomically writes output/report.

Completion: report has `status: ok`, target/recording/output hashes, source-audio policy, exact duration, and `full_decode_verification.ok: true`.

### 5. Review

Listen through the final result. Check phrase completion, timing against visual boundaries, source-audio behavior, clipping, intelligibility, and final AAC properties. Record the narrated derivative in the story without changing target identity or group membership.

## Common pitfalls

1. **Grouping here.** Use `scene-group`; this skill processes one target.
2. **Substituting TTS.** Narration must be the user's own approved recording.
3. **Mixing before audio approval.** Audio-only approval precedes video mux.
4. **Assuming ducking.** Use explicit `lower` and `gain_db`.
5. **Overwriting the voice recording.** All preparation produces derivatives.
7. **Default `amix` normalization changes ambience after speech.** FFmpeg `amix` defaults to `normalize=1`, which attenuates both inputs while narration is present and restores the background when narration ends, creating an unnatural jump. Build and verify the final audio track first, use `normalize=0`, apply one fixed source gain over the whole scene, then mux that approved audio into the video. Never let narration presence change the background gain.

## Verification checklist

- [ ] explicit target kind/path/hash
- [ ] user's original recording preserved and checksummed
- [ ] prepared audio-only derivative explicitly approved
- [ ] exact approved recording hash used
- [ ] source-audio policy recorded
- [ ] output duration matches decoded target authority
- [ ] H.264 `yuv420p`, AAC 48 kHz stereo
- [ ] full decode and full listening QA passed
- [ ] originals unchanged
