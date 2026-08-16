# Runtime bootstrap and installed-copy verification

Use this when the soundtrack scripts have pinned Python dependencies or are being installed on a new host/profile.

## Durable pattern

1. Read `scripts/requirements.lock` and determine its Python compatibility before creating the venv.
2. Select the interpreter explicitly; do not assume the first `python3` resolved by a tool is compatible.
3. Store the runtime in a versioned cache directory, for example `story-soundtrack/v2/venv`.
4. If the interpreter or dependency lock changes, create the next cache revision rather than repairing an incompatible venv in place.
5. Sync the exact lock with `uv pip sync`.
6. Verify the interpreter and dependency import.
7. Run shell syntax checks, Python compilation, the complete installed-copy test suite, and one wrapper-level demo pipeline.
8. Declare installation complete only after the public wrapper produces stems, a source mix, and verifier output `ok: true` from the active skill directory.

## Example

```bash
export STORY_SOUNDTRACK_PYTHON=3.13
export STORY_SOUNDTRACK_RUNTIME="$XDG_CACHE_HOME/story-soundtrack/v2"
scripts/bootstrap_runtime.sh "$STORY_SOUNDTRACK_RUNTIME"
"$STORY_SOUNDTRACK_RUNTIME/venv/bin/python" -m py_compile scripts/*.py
"$STORY_SOUNDTRACK_RUNTIME/venv/bin/python" -m unittest discover -s scripts/tests -v
```

Then exercise the allowlisted wrapper in a temporary project root:

```bash
scripts/run.sh make_demo_sources.py --root "$TMP"
scripts/run.sh render_story_score.py --root "$TMP" --spec "$TMP/demo/spec-v1.json"
scripts/run.sh mix_story_audio.py --root "$TMP" --spec "$TMP/demo/spec-v1.json"
scripts/run.sh verify_story_soundtrack.py --root "$TMP" --spec "$TMP/demo/spec-v1.json"
```

Treat a successful verifier followed by a failing ad-hoc filename assertion as a verification-script bug: inspect the spec's declared output paths and rerun the exact artifact checks. Do not misreport the production pipeline as failed when its own states and verifier succeeded.
