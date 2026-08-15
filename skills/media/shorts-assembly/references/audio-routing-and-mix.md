# Soundtrack routing, cleanup, and verification

Use this when a multi-scene edit combines speech, source-music video, and silent photo scenes.

## 1. Classify before mixing

Assign every segment exactly one audio class from evidence in the assembled scene report:

- `voice`: any video with dialogue, reactions, ambient speech, or other original/source audio that must remain intelligible.
- `source_music`: only a clip whose own singing/music is explicitly part of the story; never infer this class merely because the material is video.
- `silent`: photos, animated stills, collages, **and video without source audio**.

When the user says all videos are voice-bearing, classify every source-audio video as `voice`; do not invent `source_music` or treat photo scenes as “music videos.” Melody belongs on photos, collages, and silent video—not on voice scenes.

Build the timeline from the **actual normalized segment durations and `source_audio` flags**, not assumed source lengths or filename heuristics. Assert every scene was classified and record `kind`, `source_audio`, and routing in the machine-readable report.

## 2. Separate generated music into stems

Render at least two independent stems:

- `rhythm`: a musically complete rhythm section—drums/brushes plus walking bass, acoustic guitar comping, or equivalent harmonic pulse—not percussion hits alone;
- `melody`: lead line and optional melodic ornaments.

For a continuous travel bed, generate the rhythm stem once across the entire final duration on one global beat/phase timeline. **Never cut, loop-restart, regenerate, or concatenate rhythm per scene.** Route it with a smooth gain envelope: full on silent material, quieter but clearly nonzero under every `voice` scene. Scene boundaries may change gain, not phase or pattern continuity.

Default routing for Sergey's family Shorts when background music is requested:

| Segment class | Original audio | Rhythm stem | Melody stem |
|---|---:|---:|---:|
| `voice` | full, cleaned | quiet but continuous | off |
| `silent` (photo/collage/silent video) | silence | full | full |
| `source_music` | full, normalized | off | off |

Use explicit smooth gain ramps at routing boundaries; around 300 ms is a proven starting point when a continuous bed moves between foreground and speech levels. Do not use automatic ducking unless requested. Keep routing machine-readable in a JSON timeline/report.

### Calibrate the speech-bed rhythm audibly

Do not equate “quiet” with nearly inaudible. For Sergey's acoustic travel mixes:

- current default for a complete rhythm section: **`0.456`** (about **`-6.82 dB`**) under unity original speech, melody off.

The `0.456` setting preserves a clearly audible continuous bass/guitar/drums pulse on phone speakers while leaving dialogue intelligible. A generic attenuation such as `-22 dB` can make bass, guitar, and brushes disappear even though RMS is technically nonzero. Start comparable acoustic travel mixes at `0.456` and tune from the actual recording when speech needs more headroom.

When the user requests a relative adjustment such as «добавь ещё 20%», apply it to **linear amplitude**, not percentage points and not decibels. Render to a new review filename, verify representative voice-scene rhythm RMS increased by the requested ratio, and remeasure final loudness/true peak. Preserve all unrelated routing levels.

## 3. Speech and source-music treatment

Preserve every original file. Process only derived segments.

- Ordinary speech starting point: `highpass=f=80,afftdn=nr=6:nf=-50`, then loudness normalization near `-16 LUFS`, true peak at or below `-1.5 dBTP`.
- Already denoised speech: do not stack another denoiser; normalize only.
- Source-music video: do not apply speech denoising. A gentle `highpass=f=35` plus loudness normalization is safer.
- Measure the resulting file, not merely the first-pass prediction. Short clips can miss the target; correct and remeasure.

Report actual integrated loudness and true peak for each audible segment.

## 4. “Inspired by” is not note-for-note

If the user asks for music “по мотивам” a familiar tune, treat the reference as mood, contour, pickup gesture, meter, or selected intervals—not as permission to repeat the complete note sequence. Compose new phrases and variations. If the first version is recognizably one-to-one, replace it with an original improvisation before delivery.

For a requested swing arrangement, encode actual swing mechanics:

- long–short eighths (approximately 2:1);
- brushes or snare emphasis on beats 2 and 4;
- walking bass or equivalent quarter-note pulse;
- acoustic guitar/comping that participates in the continuous rhythm section;
- slightly laid-back lead phrasing.

A straight melody over evenly spaced percussion is not swing. A few isolated drum hits are not a rhythm section.

For a requested regional pentatonic character, specify the exact pitch collection and compose an original theme rather than scattering random scale notes. A convincing expressive lead should normally include a recognizable 1–2 bar motif, repetition with variation, call-and-response, register/dynamic development, and idiomatic ornaments or descending answers. Keep those culturally suggestive elements integrated into the composition without quoting a known melody. In the routed mix, this expressive lead still follows the audio classes: full on photos/collages/silent video, off on `voice` unless the user explicitly requests otherwise.

## 5. Prevent clicks and crackle

- Give every synthesized note and percussion hit both attack and release ramps; never truncate a nonzero waveform abruptly.
- Avoid raw full-band pseudo-noise for brushes/cymbals. Smooth or band-limit it, or synthesize controlled metallic partials.
- Add about 20–30 ms fade-in/fade-out to original audio at hard segment joins.
- With FFmpeg `alimiter`, set `level=false`; otherwise the limiter can auto-amplify back toward 0 dBFS. Keep the final ceiling near `-1.5 dBFS`.
- Create a new filename for each review iteration so messaging clients do not serve a cached earlier file.

## 6. Verification

Verify the routed stems independently before mixing:

- melody during `voice` and `source_music`: effectively silent (for example around `-90 dB` after AAC), not merely “very quiet” when the routing rule says off;
- melody during every photo, collage, and silent-video scene: audible;
- rhythm during every `voice` scene: audible but quiet, with nonzero window RMS near each scene midpoint;
- continuous-rhythm provenance: one exact-duration stem and one global beat phase, with envelope-only routing rather than per-scene stem concatenation or restart;
- both generated stems during `source_music`: effectively silent;
- final stream decodes, has the expected duration/sample rate/channels, and stays below the declared peak ceiling.

Measure representative windows for **every routing class**, and save those values in the report. Also assert exact PCM frame count before AAC encoding.

For synthesized stems, decode to PCM and inspect adjacent-sample jumps. Compare any flagged jump against the extracted original audio at the same timestamp: if location and magnitude match, report it as a source transient rather than falsely blaming the generated music. Generated rhythm, melody, and their gain-enveloped versions must independently remain below the click threshold.
