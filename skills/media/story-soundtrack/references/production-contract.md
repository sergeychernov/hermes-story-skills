# Production contract and regression checklist

This reference captures reusable failure modes found while hardening a timeline-driven story soundtrack pipeline.

## Artifact sequence

Keep the following artifacts distinct:

1. rhythm stem/master and listening derivative;
2. full score master and listening derivative;
3. source-mixed sample-exact PCM master;
4. encoded approval derivative;
5. immutable approval record;
6. locked handoff for final video assembly.

A static-cover audio preview is only a channel fallback. It is never the full mixed story video.

## Strict plan validation

Reject the plan before rendering when any of these occur:

- unknown JSON field;
- path traversal or symlink escape outside root;
- duplicate output path;
- output/input alias;
- missing or ambiguous revision token;
- timeline gap, overlap, scene-order mismatch, or non-integral frame-to-sample mapping;
- `voice` without source audio;
- `silent` with source audio;
- unsupported style, pitch collection, or instrumentation;
- instrumentation that does not map to an actually rendered layer.

A boundary-aware revision matcher must treat `v1` and `v10` as different tokens.

## Source media regression cases

Test WAV, M4A, and MP4 inputs.

- Missing audio stream must fail.
- Short source may be tail-padded, with decoded and padded frames reported.
- Source longer than the scene must fail to avoid cutting speech.
- A small, explicitly bounded codec-padding tail may be trimmed and reported.
- Source presence should be checked with measured energy/RMS in routed windows, not only by successful decode.
- Never use a helper that pads/trims to expected length when verifying the final encoded approval master.

## Raw encoded-master QA

A common false-positive pattern is to decode an AAC through the same helper used for scene normalization. If that helper pads short audio, `decoded_frames == expected_frames` becomes vacuous.

For final approval QA:

1. decode the entire encoded stream raw, without pad or trim;
2. fail when raw decoded frames are shorter than the exact PCM master;
3. permit only bounded codec tail padding;
4. fail when tail padding exceeds that bound;
5. run `ffprobe` duration as an additional check, not a substitute;
6. run full decode, loudness, true-peak, channel, sample-rate, and codec checks.

Include regression fixtures for both truncated AAC and excessive codec padding.

## Immutable approval

- Approval and handoff records are never overwritten.
- Render and mix must refuse when either record exists, even with `--overwrite`.
- Revisions after feedback must get new output paths and reset to the planned state.
- Missing expected hashes must fail closed; do not use optional checks such as `if expected_hash`.
- Modifying the approved audio must invalidate verification.

## Aggregate report transition

Render may write a stem report, and first mix may promote that same report path into an aggregate report. The clean happy path must be:

```text
render without overwrite
→ first mix without overwrite
→ review
→ immutable approval
```

A repeated pre-approval mix may require explicit overwrite. Any post-approval write is forbidden.

## Handoff contract

Verify exact operation sets, not membership of one representative item.

Typical allowed operations:

- video/audio mux with audio copied unchanged;
- container packaging that preserves approved audio bytes where supported;
- separately approved channel-compatible copy.

Typical forbidden operations:

- trim;
- gain change;
- normalization;
- ducking;
- remix;
- replacement;
- unapproved audio re-encode.

## Composition assertions

Tests should prove behavior, not only metadata:

- changing instrumentation changes PCM and reported layer mapping;
- each declared layer gate controls synthesis;
- changing theme energy changes output energy;
- moving `climax_scene_id` relocates the measured climax in a multi-bar fixture;
- rhythm phase stays continuous across scene boundaries;
- melody is absent in voice/source-music windows according to routing.

## Review discipline

Do not treat an implementation agent's green-test claim as evidence. Run tests independently, then use an independent reviewer focused on security, immutable approvals, duration handling, state gates, and doc/code drift. If review fails, harden and repeat. Report long-running progress after each gate so the user is not left wondering whether work continues.
