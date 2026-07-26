# Generated background music: originality, approval, and mixing

Use this workflow when a Reel/Short needs music to prevent the audio energy from collapsing during still-image scenes.

## 1. Originality boundary

When the user references an existing song, treat it as a mood/arrangement reference only. Translate it into high-level traits such as era, tempo, instrumentation, rhythm, production texture, and regional colour. Generate an original composition that does **not** copy the source melody, lyrics, recording, hook, or a recognisable arrangement.

Keep a concise provenance note with:

- generation prompt or deterministic generation script;
- statement that no source audio was sampled;
- output duration and format;
- intended mix levels.

## 2. Automation boundary

A documented convention is not executable automation. Do not say that music is generated or mixed automatically merely because this reference contains preferred parameters.

Before claiming automatic support, require all of the following:

- the renderer or a checked-in helper accepts explicit music-generation and mix settings;
- the manifest records arrangement mode, gain, ducking, source/provenance, and output revision;
- automated tests cover the generated filter/configuration;
- a real render has been exercised and verified.

Until those pieces exist, describe the operation accurately as a manual post-render generation/mix workflow. A one-session generator or preview must stay outside the skill when the user asks not to persist it.

## 3. Mandatory two-stage approval

Music approval and video approval are separate gates:

1. Generate the music as a standalone audio file.
2. Verify duration, channels/sample rate, peak level, and absence of clipping.
3. Send only the standalone audio preview.
4. Do **not** insert, mux, or render it into the video until the user explicitly approves that track.
5. After approval, mix into a new draft revision, verify the video, and send another video preview.
6. Publication still requires the normal explicit **«публикуй»** gate.

If the user says “прежде чем вставлять, покажи аудио”, stop after step 3. Never infer music approval from a request to generate it.

## 4. Arrangement and mixing across stills and speech

Default arrangement for travel edits when the user has not requested otherwise:

- preserve the chosen genre, mood, and tempo, but prefer acoustic/live-sounding timbres over electronic ones: clarinet or another natural reed, accordion when appropriate, acoustic guitar, upright bass, muted brass, and natural drums or regional hand percussion;
- during still-image scenes, allow the main melodic voice and the full rhythmic accompaniment;
- during ordinary video scenes, remove or mute the lead melody and retain only a restrained rhythmic bed, so speech and natural sound remain the focus;
- tag every video whose source audio already contains music with `"content_type": "music"` in the canonical clip metadata. During those intervals mute **both** generated stems—melody and rhythm—so the embedded/source music plays alone;
- tag a video that should contribute no source audio with `"content_type": "nosound"`. Replace its original-audio interval with digital silence **before** normalization, and route it like a still scene so both melody and rhythm continue;
- tag dialogue-led video that needs cleanup with `"content_type": "speech"`. Apply a moderate speech-preserving noise filter before scene loudness measurement/normalization (for example high-pass around 80 Hz, FFT denoise with smoothing, and low-pass around 12 kHz), then route only the restrained rhythm stem behind it;
- generate and inspect the routing before mixing:

  ```bash
  python3 scripts/build_music_routing.py \
    --manifest manifest.json \
    --routing-json music-routing.json \
    --filter-script music-routing.ffscript \
    --gain 0.13 --fade 0.08
  ```

  The generated FFmpeg filter expects original audio as input `0:a`, melody as `1:a`, rhythm as `2:a`, and exposes `[outa]`. Its scene modes are `melody+rhythm` for stills and `content_type: nosound`, `rhythm` for ordinary videos and `content_type: speech`, and `original-only` for `content_type: music`. Verify the `muted_intervals` and every scene mode in `music-routing.json` against the canonical scene timeline before rendering. If the user refers to the “first N videos,” select the first N clips whose manifest `type` is `video`; do not equate them with scene numbers when images may be interleaved;
- implement melody and rhythm as separate stems, MIDI tracks, or independently controllable buses; do not rely on volume ducking alone, because the desired contrast is an arrangement change rather than merely a level change;
- make arrangement changes at scene boundaries with short musical transitions or fades; avoid abrupt cuts and clicks;
- if the user requests one fixed level, keep the same linear gain for both arrangements even though their musical density differs. Treat `volume=0.13` only as an initial audition baseline, not as proof that the rhythmic bed is audible. Render and measure the routed music-only bus against the normalized original before proposing a final value.

Interpret a percentage as linear amplitude unless the user specifies LUFS, dB, or another convention. As a practical starting point:

- still-image scenes: use the requested level (for example, `volume=0.13`, about −17.7 dB);
- original speech/video scenes: duck further (for example, `volume=0.07`, about −23.1 dB), unless the user requests one fixed level;
- use short ramps at scene boundaries rather than abrupt gain jumps;
- preserve original speech and natural sound;
- limit the mixed result conservatively to prevent clipping.

Do not normalize the final mix in a way that defeats the requested relative music level. Normalize or level the standalone music first, then apply the requested gain and mix with `normalize=0` semantics.

### Mixed-audio preview semantics and audibility calibration

Keep three artifacts unambiguous:

1. **Standalone music preview** — generated music only; appropriate for approving composition and arrangement.
2. **Mixed-audio preview** — synchronized normalized original audio plus routed music; this is what the user means when they ask to hear “music mixed with the sounds of the video.” An audio-only MP3 is acceptable for level review, but it must not be mislabeled as the standalone composition or as a mixed video.
3. **Mixed-video preview** — the actual video draft with the approved audio mix muxed in; required before package promotion.

Before sending a mixed-audio level candidate:

- normalize the original scene audio first when speech, ambience, and embedded concert material have materially different loudness;
- render a **music-only routing diagnostic** by feeding digital silence as original input while keeping the real melody/rhythm stems and routing filter;
- measure rhythm-only LUFS inside every ordinary-video interval and compare it with normalized dialogue LUFS. Linear gain alone is not an audibility guarantee: `0.13` is about `−17.7 dB` relative to the stem, but a quiet stem can still land roughly 20 dB below dialogue and become inaudible;
- use the measured difference to produce a new candidate, preserve the same gain on both generated stems when fixed-gain mixing was requested, and remeasure. A rhythmic bed roughly 8–14 dB below dialogue is a reasonable audition range, not a universal final target;
- measure interior points of `original-only` scenes and require generated music to be digital silence there (`-inf` or the analyzer’s silence floor);
- fully decode the candidate and verify duration, peak, NaN/Inf, and checksum before delivery.

Do not silently promote a trial gain into a permanent user default. Record it as an approval candidate until the user accepts the mix.

## 5. Scene-wise normalization of original audio before music

When speech and embedded live music differ sharply in level, normalize the original audio **before** mixing generated stems:

- measure integrated loudness and true peak separately for each video scene; do not use one global loudness pass and do not infer levels from waveform peaks alone;
- as a social-video starting point, target dialogue and embedded concert scenes around `-18 LUFS` with `-1.5 dBTP` ceiling, while preserving artistic dynamics inside each scene;
- cap positive gain for very quiet ambience (for example `+12 dB`) instead of forcing background noise to dialogue loudness;
- use two-pass EBU R128 / FFmpeg `loudnorm` for ordinary speech and loud concert scenes; keep image scenes at digital silence before adding the music bed;
- process canonical scene intervals independently, then concatenate them at their exact declared durations. Short loudness filters can return fewer samples, so append silence and trim each branch by exact sample count before concat (for 48 kHz: `apad,atrim=end_sample=round(duration*48000),asetpts=N/SR/TB`);
- when source packet timestamps contain overlap or gaps, first align to the video clock with `aresample=48000:async=1000:first_pts=0`; do not blindly compact timestamps with `asetpts=N/SR/TB`, which can shift audio relative to video;
- remeasure every normalized video interval, verify the final sample duration, then apply melody/rhythm routing and the requested fixed music gain;
- retain the original unnormalized master and produce a new preview revision for approval.

## 6. Verification

Before sending the standalone preview:

- duration covers the complete edit;
- stereo/mono and sample rate are valid for the target;
- no clipping or truncated container;
- fade-in/out are intentional;
- the audio file plays independently.

Before sending the mixed video preview:

- render the approved mix to a lossless intermediate (for example 48 kHz PCM WAV), then encode that once to the delivery codec while muxing; do not transcode an MP3 audition file into AAC;
- preserve the approved video stream with stream copy when only audio changed. Do not add `-shortest` blindly: a non-zero video start timestamp can cause FFmpeg to drop the final video packet/frame even when nominal durations match. Prefer muxing without `-shortest`, then verify container/stream durations explicitly;
- compare source and preview video packet hashes with FFmpeg `streamhash` and count decoded frames. Equal hashes plus equal frame counts prove that audio replacement did not alter or truncate the video;
- master duration and frame geometry are unchanged;
- speech remains intelligible;
- still-image intervals no longer feel silent;
- music transitions do not pump or click;
- the original no-music master remains available for rollback.

## 7. Promote the approved mix into a publishable package

A post-render audio mix is a new master, not an interchangeable sidecar. A green `verification.json` for the no-music render does **not** authorize uploading the mixed file.

After the user approves the mixed preview:

1. Create a new immutable revision directory; keep the no-music master for rollback.
2. Put the exact approved mixed video at the package's canonical `reel-short.mp4` path. Do not merely leave it as `reel-short-music13.mp4` beside a previously verified master.
3. Copy the approved title, description, cover, carousel, manifest, and a concise mix-provenance record into the new directory.
4. Run `verify_package.py` against that new directory **after** the copy/promotion.
5. Recompute SHA-256 immediately before upload and require it to match the new green `verification.json`.
6. Upload that canonical file exactly once, poll platform processing to success, and write the publish record with the uploaded mixed-master hash.

The mix-provenance record should state the music source, linear gain (and dB equivalent if useful), whether ducking was enabled, normalization semantics, limiter settings, and draft/published state. Never store credentials in it.
