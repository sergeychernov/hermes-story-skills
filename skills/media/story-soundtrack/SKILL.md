---
name: story-soundtrack
description: Use when composing and mixing a story soundtrack.
version: 1.0.2
author: Hermes Curator
license: MIT
metadata:
  hermes:
    tags: [story, soundtrack, multitrack, audio-mix, approval, shorts]
    related_skills: [story, media-voiceover, shorts-assembly, project-artifact-delivery]
---

# Story Soundtrack

Class-level orchestration skill for creating, reviewing, revising, approving, and handing off a story soundtrack. Use after the visual timeline is frame-locked and before final video mux.

## Ownership boundary

| Responsibility | Owner |
|---|---|
| Narrative order, scene approval, visual timeline | `story` |
| Composition, stems, source-audio routing, audio revisions and approval | `story-soundtrack` |
| Final video mux/container/format after audio approval | `shorts-assembly` |
| Delivery of review artifacts | `project-artifact-delivery` |

Do not compose or route soundtrack audio inside `story`. Do not let `shorts-assembly` alter an approved master.

## Required checkpoints

1. **Plan the multitrack score.** Read the locked timeline and a strict JSON sound map describing scene boundaries, existing source audio, voice, source music, themes, style, energy arc, and climax.
2. **Deliver the mixed rhythm section separately.** This is a real playable artifact, not a path or report.
3. **Deliver the complete score separately.** Include rhythm, melody, harmony, accents, and atmosphere selected by the style contract.
4. **Deliver the score mixed with source audio from the video.** Preserve voice and intentional source sound according to evidence-based routing.
5. **Run a user revision loop.** Record objections and requested changes, create a new immutable revision, rerender, verify, and redeliver until explicitly approved.
6. **Hand off only after explicit approval.** Bind the approved audio hash and exact duration/frame contract, then transfer control to `shorts-assembly` for mux/copy only.

Standalone rhythm, standalone full score, source-mixed audio, mixed video, and publication are independent approval gates.

## State and revision model

The versioned plan remains immutable and starts as `PLANNED`. State transitions live in hash-bound artifacts:

```text
PLANNED
  → STEMS_RENDERED
  → SOURCE_MIX_REVIEW
  → USER_APPROVED
  → HANDED_OFF_TO_SHORTS
```

The rhythm/full-score listening step is a human checkpoint while the artifact remains `STEMS_RENDERED`.

Every correction creates a new revision. Never overwrite an approved revision. Existing approval or handoff artifacts must block render and mix even when an overwrite flag is present.

## Input contract

Require a strict JSON contract with unknown fields rejected. It must include:

- story id and positive revision;
- fps, total frames, exact timeline path, and contiguous scene frame ranges;
- one audio class per scene: `voice`, `silent`, or `source_music`;
- source media path when required;
- style brief, supported preset, tempo, meter, tonal center, pitch collection, instrumentation, and deterministic seed;
- named themes with scene mapping and energy;
- explicit climax scene;
- unique, revisioned output paths;
- QA targets and tolerances.

Constrain every input and output under the project root. Resolve paths before access and reject traversal, symlink escape, input/output aliasing, duplicate outputs, and ambiguous revision tokens (`v1` must not match `v10`).

## Composition and routing

- Compose against one global timeline from `t=0`; rhythm phase must not restart at scene boundaries.
- Instrumentation declared in JSON must change the rendered layers; reject unsupported values rather than silently ignoring them.
- Theme energy and declared climax must measurably influence the output.
- `voice`: preserve approved voice, melody off, rhythm reduced; default starting rhythm gain may be `0.456` when the project contract calls for it.
- `silent`: rhythm and melody active.
- `source_music`: preserve source audio and disable generated rhythm/melody.
- Determine the class from reports and actual source contents, never from filenames alone.
- Use smooth envelopes around transitions; no automatic ducking unless explicitly requested.
- Mix additively without hidden normalization. If using NumPy summation, report that accurately; do not claim FFmpeg `amix` was used.
- Never use `-shortest` where it can truncate speech or timeline audio.

## Subjective timbre diagnosis

When the user describes an irritating sound by analogy rather than naming an instrument, diagnose before recomposing. Export short numbered isolated samples from every plausible layer of the exact rejected implementation, preserve accepted stems, and revise only the identified source. Keep absolute timeline position when the artifact may be time-dependent. Follow `references/subjective-soundtrack-diagnosis.md`.

## Source media duration policy

Accept common audio/video media such as WAV, M4A, and MP4 through deterministic decode.

- A source shorter than its visual scene may receive explicit tail-silence padding; record decoded and padded frame counts per scene.
- A source longer than its scene must fail rather than cut speech.
- Only bounded codec padding may be trimmed, and the trimmed count must be reported.
- Preserve original files; all processing creates versioned derivatives.

## Required review artifacts

Deliver, in order:

1. rhythm-section WAV or compatible listening derivative;
2. full-score WAV or compatible listening derivative;
3. source-mixed sample-exact WAV;
4. source-mixed approval M4A or compatible derivative;
5. report JSON with hashes, exact frames, routing, phase provenance, source padding, loudness, and peaks.

Before claiming delivery: check nonzero size, probe, full decode, make a channel-compatible derivative, attach it, and name the artifact explicitly.

## Approval and handoff

Approval must bind:

- exact source-mixed audio SHA-256;
- exact PCM frame count and sample rate;
- aggregate report hash;
- story/revision identity;
- explicit user approval note.

The handoff to `shorts-assembly` must set `audio_processing_locked: true`.

Allowed downstream operations are limited to container-safe mux/copy and channel-compatible packaging. Forbid trim, gain change, normalization, ducking, remix, replacement, and audio re-encoding unless the user explicitly revokes approval and starts a new soundtrack revision.

Final AAC QA must use a raw full decode that cannot hide truncation through padding or trimming. Probe duration is an additional check, never a substitute. Reject decoded audio shorter than the approved PCM duration; allow only explicitly bounded codec tail padding.

## Verification gates

Before approval or handoff, verify:

- strict schema and root confinement;
- timeline agreement immediately before mix;
- exact sample count of PCM masters;
- stereo/sample-rate contract;
- source-audio presence in routed windows;
- theme and climax mapping;
- mandatory hashes and phase hashes;
- loudness and true peak against declared tolerances;
- full decode of WAV and encoded review master;
- immutable approval and exact downstream operation sets.

See `references/production-contract.md` for regression cases and failure modes.

## Runtime and executable contracts

Production logic lives in the bundled scripts; do not replace it with project-local one-off code.

- `scripts/render_story_score.py` — deterministic multitrack stems, rhythm/full previews, stem report.
- `scripts/mix_story_audio.py` — source-media decode, evidence-based routing, sample-exact source mix and encoded QA.
- `scripts/apply_feedback_revision.py` — strict, root-confined immutable revision creation.
- `scripts/approve_story_soundtrack.py` — hash-bound immutable approval and handoff.
- `scripts/verify_story_soundtrack.py` — pre-approval and pre-handoff verifier.

The host system Python may not contain NumPy. Bootstrap the pinned isolated runtime once. Do not rely on an unqualified `python3`: explicitly select an interpreter satisfying `scripts/requirements.lock` (for the current lock, Python 3.13), and keep the runtime cache versioned so an incompatible earlier venv is never silently reused:

```bash
STORY_SOUNDTRACK_PYTHON=3.13 scripts/bootstrap_runtime.sh
```

After bootstrap, verify the selected interpreter, import the pinned NumPy, run `py_compile`, and execute the installed-copy test suite before declaring the skill ready. If the interpreter or dependency lock changes, advance the runtime cache revision instead of mutating an existing environment in place. See `references/runtime-bootstrap-and-install-verification.md`.

Then invoke production scripts through the allowlisted wrapper:

```bash
scripts/run.sh render_story_score.py --root <work> --spec <spec>
scripts/run.sh mix_story_audio.py --root <work> --spec <spec>
scripts/run.sh verify_story_soundtrack.py --root <work> --spec <spec>
```

`run.sh` rejects arbitrary script paths. NumPy is pinned in `scripts/requirements.lock`; FFmpeg and ffprobe must be available in `PATH`.

Templates:

- `templates/story-soundtrack.json`
- `templates/story-soundtrack-feedback.json`

Detailed contracts:

- `references/json-contract.md`
- `references/revision-and-approval-flow.md`
- `references/production-contract.md`
- `references/subjective-soundtrack-diagnosis.md`
- `references/tdd-log.md`

## Long-running work communication

Soundtrack generation and real media QA can take several minutes. Do not disappear during multi-cycle implementation or review. Send a concise progress update after each major gate—design, first green test suite, independent review, hardening, installation—and immediately report any blocker or timeout. Distinguish tool-reported claims from independently verified results.

## Completion definition

The task is not complete when code or a report exists. It is complete only when:

- the requested audio artifacts are generated and independently verified;
- the user has actually received the current review artifact;
- explicit approval is recorded for the exact hash;
- the locked handoff is accepted by `shorts-assembly` without audio alteration.
