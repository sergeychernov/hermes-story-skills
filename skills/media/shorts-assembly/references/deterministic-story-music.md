# Deterministic story music scripts

Use this workflow for an original pentatonic story score when the timeline is already final.

## One-time environment

Do not modify system Python:

```bash
uv python install 3.11
uv venv --python 3.11 .venv-story-music
uv pip install --python .venv-story-music/bin/python numpy
```

## Render stems from a spec

Copy `templates/pentatonic-story-score.json` into the project and change only project data: timeline path, seed, BPM, versioned output paths. Never edit the skill script for one story.

```bash
.venv-story-music/bin/python \
  <shorts-assembly>/scripts/render_pentatonic_story_score.py \
  --root <project> --spec <project>/story-score-v1.json
```

The preset produces original `D–E–F#–A–B` material with one continuous global rhythm phase, separate rhythm/melody WAV stems, a full PCM preview, SHA-256 values and exact frame counts. Existing outputs make the command fail unless `--overwrite` is explicit; normal revisions must use new filenames instead.

## Encode the audio-only approval preview

Copy `templates/story-audio-approval-preview.json`, point it at the generated PCM preview and choose a new M4A/report revision.

```bash
.venv-story-music/bin/python \
  <shorts-assembly>/scripts/encode_story_audio_preview.py \
  --root <project> --spec <project>/story-audio-preview-v1.json
```

The encoder asserts that the PCM frame count equals the timeline, performs measured loudness normalization, inserts `aresample=48000` before `atrim=end_sample`, fully decodes and probes the final AAC, measures achieved LUFS/true peak, and writes provenance. It rejects path traversal, accidental overwrite, wrong PCM format, duration drift, decode failure and peak-ceiling violations.

## Approval delivery gate

Attach `output_m4a` as a playable media attachment in the same response that announces it. Do not proceed to speech-aware routing or video mux until the user approves this exact hash. A path, JSON report or technical summary is not delivery.

## Tests

```bash
.venv-story-music/bin/python -m unittest \
  <shorts-assembly>/scripts/tests/test_story_music_tools.py -v
```

Completion means all tests pass, the project spec/report JSON validates, the final AAC fully decodes, and the attached file hash equals the report.
