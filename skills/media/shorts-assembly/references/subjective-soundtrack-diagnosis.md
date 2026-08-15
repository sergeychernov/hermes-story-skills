# Subjective soundtrack diagnosis by isolated samples

Use this when the user describes an objection through analogy rather than an instrument name: «скрип по пластинке», «мокрый ластик по стеклу», «назойливо», «слишком синтетично».

## Rule: diagnose before recomposing

Do not infer the offending layer from prose and immediately replace the whole arrangement. Familiar elements such as walking bass or drums may be acceptable while one synthesized timbre is the actual problem.

1. Inventory every independently generated layer and sound source in the rejected mix: bass, comping instrument, kick, brush/noise, lead, ornaments, effects.
2. Render each candidate **in isolation** from the exact rejected synthesis implementation. Preserve its oscillator/noise algorithm, register, envelope, modulation, gain family, encoding path, **and global timeline position** closely enough that the artifact remains audible. If the listener supplies a timestamp, first extract the same short window from the full mix, source-only audio, every routed stem, and (when relevant) limiter input/output. Do not substitute freshly synthesized notes starting at `t=0`: absolute-time oscillator bugs can emerge only later in the film.
3. Make samples short and comparable: normally 3–5 seconds, same sample rate/channels, no speech and no other instruments.
4. Number and label the files plainly; attach the actual audio files in one response.
5. Ask the user to identify one or more numbers. Only then remove, replace, filter, or redesign those components.
6. Preserve accepted rhythm, harmony, routing, and loudness unless the user separately rejects them.
7. Render a new **audio-only** full-timeline review under a new filename. Do not mux or republish before explicit listening approval.

## Candidate mapping

Common artifact sources:

- needle/vinyl-like scrape: high-passed pseudo-noise, brush synthesis, discontinuous random state, hard attack/release;
- wet rubber/glass squeak: pitch bend, frequency modulation implemented as `phase = 2π × f(t) × t`, high odd harmonics, narrow high-register lead, exaggerated vibrato. A particularly deceptive failure is `phase = 2π × frequency × vibrato(local_note_time) × absolute_timeline_time`: the nominal vibrato is bounded, but its effective pitch deviation grows with elapsed timeline time. Use bounded local note phase (`2π × f × local_note_time + phase_deviation × sin(2π × vibrato_hz × local_note_time)`) or integrate instantaneous frequency sample by sample;
- irritating repetition: short motif loop, phase restart at scene boundaries, constant offbeat comping;
- harsh pluck: near-zero attack plus strong upper partials;
- clicks: nonzero waveform truncation or gain gates without ramps.

These are hypotheses only. Identification still comes from isolated listening samples.

## Verification

- After identifying the offending stem, change only that layer and prove unrelated stems byte-identical by hash before rebuilding the full mix.
- Provide the repaired version of the same reported timestamp window before spending time on the full timeline.
- For routed melody, measure representative voice windows and assert effective silence where the routing contract says `off`; measure a silent-scene window to prove the repaired lead is actually present.
- Inspect maximum adjacent-sample jump in the repaired stem to catch hard discontinuities.
- Full-decode every sample.
- Confirm expected duration, sample rate, and channels.
- Keep the rejected mix and all diagnostic samples immutable for A/B comparison.
- If using FFmpeg `loudnorm`, remember it may output 192 kHz internally. Use the safe order `loudnorm → aresample=48000 → limiter → apad=whole_len=N → atrim=end_sample=N → asetpts=PTS-STARTPTS`; trimming to a 48 kHz frame count before resampling can accidentally produce one quarter of the intended duration.
- Build a sample-exact PCM master, encode AAC, decode it back to PCM, and assert both master and decoded verification copy contain exactly `N` frames. Probe stream/container duration and measure LUFS/true peak from the final encoded review file; never infer approval duration or loudness from the command alone.
