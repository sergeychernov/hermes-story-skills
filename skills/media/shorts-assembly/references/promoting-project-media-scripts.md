# Promoting project media scripts into the skill

Use this when an agent is about to create or substantially rewrite a project-local media script for behavior that can recur across stories.

## Promotion trigger

Stop and promote the implementation when any condition holds:

- the same workflow has already produced a second project script;
- the script contains no story-specific creative decision except paths, seed, timing, text, gains, or layout parameters;
- a prior session had to rediscover an FFmpeg ordering rule, duration fix, verification probe, or delivery gate;
- reproducibility depends on code that exists only in one draft directory.

Do not promote genuinely one-off creative data. Scene names, selected sources, exact titles, seed, BPM, routing windows, revision names, and output paths belong in a project JSON spec.

## Target shape

Put reusable behavior under the governing class-level skill:

```text
scripts/<action>.py       deterministic implementation
templates/<spec>.json     copyable declarative input
references/<topic>.md     contract, commands, pitfalls
scripts/tests/test_*.py   behavioral and regression tests
```

The project should retain only versioned specs. Do not leave a second implementation or forwarding wrapper in the project.

## TDD migration

1. Write a skill-level test for the wished-for CLI/spec contract and observe it fail because the reusable script is absent.
2. Implement the smallest script that passes.
3. Add fail-closed tests for unknown spec keys, path traversal, aliased outputs, accidental overwrite, wrong media format, duration drift, and decode failure where relevant.
4. Run the complete skill suite, not only the new test.
5. Delete the project-local implementation after the skill suite passes.
6. If an active project exists, point its next revision at the skill script and verify that output normally; do not keep a shim for inactive projects.

## Provenance contract

A reusable renderer report should record enough to explain future hash changes:

- input/spec paths and hashes;
- implementation SHA-256;
- seed and all creative parameters;
- exact frame/sample counts;
- runtime/library versions that affect encoded bytes;
- output hashes and measured properties;
- approval/mux/delivery state.

Unknown JSON fields must fail instead of being ignored: a misspelled parameter is nondeterminism disguised as a default.

## Completion criteria

Promotion is complete only when:

- the skill owns the implementation, template, reference, and tests;
- project-specific paths and choices exist only in project specs;
- the project-local implementation is removed;
- any active project revision using the promoted skill has passed normal output verification;
- the project manifest points to the new versioned artifacts;
- any announced approval media is attached as the actual playable/viewable file.
