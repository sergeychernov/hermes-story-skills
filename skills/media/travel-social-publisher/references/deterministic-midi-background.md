# Deterministic MIDI background fallback

Use this when a short travel edit needs original generated background music, but a hosted music model is unnecessary or unavailable. This is a reproducible fallback for understated background beds—not a substitute for a commissioned performance.

## Design from high-level traits only

Translate the requested reference into genre, tempo range, instrumentation, energy, harmony, and production texture. Never transcribe or copy the source melody, hook, lyrics, recording, or recognisable arrangement. If source concert audio is available, use it only to estimate broad energy/tempo; short clips produce ambiguous tempo candidates, so select a musically plausible value and record the uncertainty.

Keep provenance stating:

- no source audio was sampled;
- no source melody was transcribed;
- tempo, meter, key centre, form, instruments, and deterministic generator path;
- intended routing and final mix gain.

## Fit the musical form to the edit

Choose whole bars first, then derive a tempo that ends on a bar boundary:

```text
BPM = bars × beats_per_bar × 60 / target_duration_seconds
```

A small adjustment around the estimated concert tempo is preferable to truncating a chord or phrase at the video endpoint. Write an intentional cadence and global fade-out; container padding may make a compressed preview slightly longer than the musical program, so report both when they differ.

## Separate arrangement stems

Generate at least two synchronized MIDI/audio buses:

1. **melody** — lead reed, muted brass, vibraphone, or another natural-sounding voice;
2. **rhythm** — piano/guitar comping, upright bass, and restrained drums/percussion.

Both files must start at timestamp zero, use the same sample rate/channel layout, and cover the complete edit. This enables canonical routing:

- stills: melody + rhythm;
- ordinary video: rhythm only;
- `content_type: music`: neither stem; source audio only.

For acoustic small-club jazz, a practical GM palette is acoustic grand piano, acoustic/upright bass, restrained jazz kit/ride, and tenor sax or muted trumpet. Use rests in the lead; a continuous solo makes a background bed feel synthetic and competes with captions or speech.

## Reproducible rendering

A MIDI writer such as `mido`, a known GM SoundFont, and FluidSynth are sufficient. Keep the generator script, `.mid` files, rendered stems, and provenance together. Prefer a licensed/free SoundFont and record its name/license.

When system-wide installation is not appropriate, packages can be unpacked into a project-local tool directory:

```bash
apt-get download fluidsynth libfluidsynth3 fluid-soundfont-gm
dpkg-deb -x PACKAGE.deb .audio-tools/root
LD_LIBRARY_PATH=.audio-tools/root/usr/lib/x86_64-linux-gnu \
  .audio-tools/root/usr/bin/fluidsynth -ni -F stem.wav -r 48000 \
  .audio-tools/root/usr/share/sounds/sf2/FluidR3_GM.sf2 stem.mid
```

Resolve any additional shared-library packages reported by `ldd`; keep this local bootstrap optional because package names vary by distribution.

## Balance before approval

Do not assume equal MIDI velocities or synth gain yield balanced stems. Sampled GM programs can differ by 10–20 dB.

1. Measure peak and RMS for each rendered stem.
2. Apply fixed, documented gain so melody and rhythm have the intended musical balance.
3. Check the sum for headroom before loudness normalization.
4. Normalize only the standalone approval preview (typical target around −16 LUFS, true peak ≤−1.5 dBFS). Preserve the balanced full-level stems for later fixed-gain routing.
5. Decode the entire preview and verify duration, 48 kHz stereo, peak, integrated loudness, NaN/Inf counts, and absence of clipping.
6. Inspect a whole-track spectrogram for unexpected long silences, hard truncation, missing frequency bands, or persistent narrow-band artifacts.

A preview that technically decodes but has a lead stem 15 dB below the rhythm bed is not ready for approval.

## Approval boundary

Send only the standalone combined audio preview first. Do not mux it into any video until the user explicitly approves the composition. After approval, route the balanced stems through the canonical scene metadata, create a new mixed draft revision, and run audio/video QA again. Publication remains a separate explicit gate.
