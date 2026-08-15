# Audio routing and normalization for mixed-media stories

Use this when a vertical story combines spoken video, music-bearing video, and silent photo scenes.

## 1. Classify before mixing

Assign every scene exactly one audio class:

- `voice`: dialogue, congratulations, reactions, ambient speech.
- `music`: source video already containing a song or musical performance.
- `silent`: animated still or collage with no source audio.

Do not apply one continuous melodic bed to the whole timeline. Render separate `rhythm` and `melody` stems when scene classes require different routing. For Sergey's family-film workflow:

- `voice` -> cleaned/normalized source audio + quiet generated rhythm; generated melody must be silent.
- `music` -> normalized source music only; both generated stems must be silent.
- `silent` -> generated rhythm + melody may play at full scene level.

Build and retain separate gated rhythm and melody stems so routing can be verified independently of the final mix.

## 2. Processing by class

Preserve the archived original unchanged. For Sergey's derived story videos, every real video receives class-appropriate noise cleanup plus measured loudness normalization: speech-safe denoising for `voice`, and only non-destructive rumble/noise cleanup for `music`. Do not treat `-c:a copy` as satisfying this requirement.

Never use a noise gate, `silenceremove`, or pause deletion as routine cleanup. They can remove quiet consonants, syllables, and phrase endings even when the waveform looks like silence.

### Voice not previously cleaned

Use conservative speech-safe cleanup, then loudness normalization:

```text
highpass=f=80,afftdn=nr=6:nf=-50:tn=1,loudnorm=I=-16:TP=-1.5:LRA=11
```

Prefer measured/two-pass `loudnorm`. For noisier phone recordings, increase denoising only after comparing the full spoken phrases before and after; do not tune from a short loud excerpt.

### Voice already denoised

Do not stack another `afftdn`; repeated denoising can damage consonants and word endings. Apply loudness normalization only.

### Music-bearing source video

Do not apply speech-oriented `afftdn` blindly to music because it can damage harmonics. Satisfy the noise-cleanup requirement with a conservative rumble cut and, only when verified against the source, mild broadband reduction; then normalize:

```text
highpass=f=35,loudnorm=I=-16:TP=-1.5:LRA=11
```

If source music is already clean, document that the high-pass cleanup and normalization were the complete treatment rather than inventing a denoising claim.

### Silent photo scenes

Supply a stereo silent track during normalization/concatenation, then add the generated soundtrack only in these timeline windows.

## 3. Preserve complete spoken timelines

A video contact sheet proves visual content, not speech boundaries. Before shortening an audio-bearing clip, probe and inspect the full audio timeline. Dark lead-ins, camera turns, and visually repetitive sections may contain the setup sentence that makes the reveal intelligible.

- Default to the full source for spoken clips. If full duration is required, omit `-ss`, `-t`, `-to`, `trim`, and `atrim` entirely rather than reconstructing a nominal `0…duration` range.
- Apply a source range only after explicit approval of those exact timestamps or after audio inspection proves that speech and context remain complete.
- Rebuild every revision from the untouched original, not from a previously trimmed or titled export.
- Re-encoding AAC can add tens of milliseconds of encoder padding. Compare source/output format duration plus audio and video stream start/end; do not demand byte-identical duration, but investigate missing source time or large A/V offsets.
- When `loudnorm` upsamples internally for true-peak analysis, explicitly set the delivery sample rate (normally `-ar 48000`) so AAC does not silently become 96 kHz.
- Measure the encoded result. AAC can overshoot the filter target by a few tenths of a decibel; if a strict `≤ -1.5 dBTP` ceiling is required, normalize toward a slightly lower target such as `-2.0 dBTP`, encode, and measure again.
- If the user reports missing words, do not adjust the cut heuristically. First rerender the full source with no temporal filters, verify complete start/end coverage and phrase completion, then update hashes and invalidate stale manifest ranges.

## 4. Background-music gating

Compute window boundaries from the durations of the actual normalized segments, not from remembered source durations. Route each stem independently:

- rhythm: quiet in `voice`, full in `silent`, exactly zero in `music`;
- melody: full in `silent`, exactly zero in both `voice` and `music`.

Apply 150–200 ms fades to generated stem windows. Apply about 20–30 ms fades to original audio at hard segment joins to prevent clicks.

Conceptual FFmpeg volume envelope for one window:

```text
between(t,START,END)*min(1,min((t-START)/0.18,(END-t)/0.18))
```

Sum envelopes per stem. The melody expression must evaluate to exactly zero in `voice` and `music`; the rhythm expression must evaluate to exactly zero in `music`. Mix with `amix=normalize=0`. When using `alimiter`, set `level=false` and keep the final ceiling near `-1.5 dBFS`; otherwise the limiter can auto-amplify back toward 0 dBFS.

## 5. Rhythm requirement

A recognizable melody is not the same as rhythmic backing. If the user requests rhythm, specify and render an explicit pulse: BPM, kick pattern, backbeat/clap, and subdivisions. If the user asks for swing, use actual long–short eighths, 2/4 brush or snare accents, walking bass, and laid-back lead phrasing; straight eighths with percussion are not swing.

“По мотивам” means an original improvisation that hints at contour, pickup, meter, or isolated intervals—not a note-for-note quotation of the reference melody. If a generated draft is immediately identifiable as the original tune played straight, rewrite the lead before delivery.

For photo/video alternation, full melody belongs on photos; voice videos retain only quiet rhythm; source-music videos retain neither generated stem.

## 6. Verification

Never claim normalization from filter settings alone.

- Measure each processed source clip after encoding. A practical target is about `-16 LUFS`, with peaks at or below `-1.5 dBTP`; short clips can miss the target and need measured gain correction plus limiting.
- Probe isolated stems in representative intervals: melody must be effectively silent in `voice` and `music`; rhythm must be audible-but-quiet in `voice`, full in `silent`, and effectively silent in `music` (for AAC, around `-90 dB` mean is acceptable).
- Decode synthesized stems to PCM and inspect adjacent-sample jumps. Add attack/release ramps to every note and percussion hit; avoid abrupt truncation and raw full-band pseudo-noise that can sound like crackle.
- Probe each `silent` interval and confirm both soundtrack stems are audible.
- Decode the complete final file with FFmpeg and verify dimensions, frame rate, sample rate, channel count, duration, and peaks.
- Disclose which clips were denoised, which were only normalized, and where generated music is active.
