# TDD Log — story-soundtrack

Строгий RED→GREEN для каждого обязательного поведения. Команды запускались из корня репозитория с `.venv/bin/python`.

## 1. strict unknown-field rejection

**Test:** `test_rejects_unknown_top_level_field`

```bash
.venv/bin/python -m unittest media.story-soundtrack.scripts.tests.test_story_soundtrack.StorySoundtrackTests.test_rejects_unknown_top_level_field -v
```

**RED (до `story_soundtrack_contract.py`):** `ModuleNotFoundError: No module named 'story_soundtrack_contract'`

**GREEN:** `validate_spec_dict` отклоняет неизвестные поля → `ContractError: unknown spec fields: unexpected`

---

## 2. path traversal rejection

**Test:** `test_rejects_path_traversal`

**RED:** `ModuleNotFoundError` (контракт отсутствует)

**GREEN:** `ContractError: path escapes root: ../../../escape/v1/rhythm.wav`

---

## 3. timeline gap/order/frame mismatch

**Tests:** `test_rejects_scene_frame_gap`, `test_rejects_non_integral_sample_mapping`

**RED:** `ModuleNotFoundError`

**GREEN:**
- gap: `ContractError: scene order/frame gap: expected start 30, got 35 in scene-voice`
- non-integral: `ContractError: non-integral sample mapping: 10 frames @ 23 fps -> 20869.565...`

---

## 4. source-audio/class invariants

**Tests:** `test_silent_scene_forbids_source_audio`, `test_voice_scene_requires_source_audio`

**RED:** `ModuleNotFoundError`

**GREEN:**
- silent+source: `forbids source_audio`
- voice без source: `requires source_audio`

---

## 5. versioned/unique output paths

**Tests:** `test_outputs_require_revision_token_and_uniqueness`, `test_outputs_missing_revision_token`

**RED:** `ModuleNotFoundError`

**GREEN:**
- duplicate paths: `output paths must be unique`
- missing `vN`: `output rhythm_wav must include revision token v1`

---

## 6. deterministic exact-frame stems and previews

**Test:** `test_render_produces_exact_frame_stems_and_previews`

**RED:** `ModuleNotFoundError` / отсутствие `render_story_score.py`

**GREEN:** rhythm/melody/full_score = 144000 PCM frames (90f @ 30fps), M4A previews созданы, повторный render бит-в-бит идентичен.

---

## 7. climax mapping to declared scene

**Test:** `test_climax_energy_peaks_at_declared_scene`

**RED:** нет `climax_time_seconds` / `render_stems` с привязкой к `climax_scene_id`

**GREEN:** climax @ 1.5s (`scene-voice`), RMS rhythm в окне кульминации > off-climax окна.

---

## 8. exact source mix routing and no truncation

**Test:** `test_source_mix_routing_and_no_truncation`

**RED:** `ModuleNotFoundError: mix_story_audio`

**GREEN:** mixed WAV = 144000 frames; voice rhythm>0 melody≈0; silent melody>0; source_music stems≈0.

---

## 9. new revision after feedback

**Test:** `test_feedback_creates_new_revision_and_resets_state`

**RED:** нет `apply_feedback_revision`

**GREEN:** revision 2, state `PLANNED`, paths содержат `v2`, rhythm_gain voice = 0.55.

---

## 10. approval exact-hash binding

**Test:** `test_approval_binds_exact_audio_hash`

**RED:** нет `approve_story_soundtrack.py`

**GREEN:** approval JSON sha256 совпадает с M4A на диске.

---

## 11. changed audio invalidates approval/handoff

**Test:** `test_changed_audio_invalidates_handoff_verification`

**RED:** verify не проверял `source_mixed_wav_sha256` → изменение WAV не ломало handoff (`ok: true`).

**GREEN:** после правки WAV → `approval source_mixed_wav hash mismatch`.

---

## 12. approved handoff locks processing

**Test:** `test_handoff_locks_processing_for_shorts`

**RED:** нет handoff JSON

**GREEN:** `audio_processing_locked: true`, allowed mux ops, `loudnorm` в forbidden.

---

## Demo CLI slice

**Test:** `test_demo_pipeline_cli`

Demo assets live under `assets/demo/`; pipeline runs in `TemporaryDirectory` (see `CLISmokeTests`).

```bash
.venv/bin/python -m unittest media.story-soundtrack.scripts.tests.test_story_soundtrack.CLISmokeTests.test_demo_pipeline_cli -v
```

**GREEN:** exit 0, `{"ok": true, "errors": []}`

---

## Final suite

```bash
.venv/bin/python -m py_compile media/story-soundtrack/scripts/*.py
.venv/bin/python -m unittest discover -s media/story-soundtrack/scripts/tests -v
```

**Result:** 17 tests OK (~33s, FFmpeg integration included)

---

## Hardening blockers (10)

Строгий RED→GREEN для усиления контрактов и QA. Команды из корня репозитория, `.venv/bin/python`.

### H1. valid SKILL frontmatter

**Test:** `test_skill_frontmatter_valid`

**GREEN:** SKILL.md начинается с `---`, содержит `name: story-soundtrack`, `description:`, `version:`.

### H2. source path confinement / canonical aliases

**Test:** `test_rejects_source_path_escape_and_output_input_alias`

**GREEN:**
- `../../../etc/passwd` → `path escapes root`
- output path = input source path → `output cannot alias input`

### H3. exact vN token (boundary)

**Test:** `test_revision_token_boundary_v1_not_v10`

**GREEN:** `v1` match для revision 1; `v10` не match для revision 1; `v1` не match для revision 10.

### H4. immutable approval (no overwrite)

**Test:** `test_approval_refuses_overwrite`

**GREEN:** повторный `approve_soundtrack` → `refusing to overwrite existing approval/handoff artifacts`; CLI без `--overwrite`.

### H5. WAV/M4A/MP4 decode + no-audio failure

**Test:** `test_decode_media_formats_and_no_audio_failure`

**GREEN:** decode WAV/M4A/MP4 OK; MP4 без аудио → `source media has no audio stream`.

### H6. final AAC probe / full-decode / LUFS / TP / duration QA

**Test:** `test_mix_qa_reports_encoded_master`

**RED:** `measure_loudness` с `-v error` не захватывал JSON loudnorm filter.

**GREEN:** encode с `loudnorm`, QA probe/decode/LUFS/TP/duration в aggregate report `phases.source_mix.qa`.

### H7. theme energy affects output + instrumentation strictness

**Test:** `test_theme_energy_affects_output_and_unsupported_instrumentation_rejected`

**GREEN:** `synth_lead` отклонён; post-normalize scene theme envelope → high energy RMS > low energy RMS.

### H8. aggregate stem+mix report + state prerequisites

**Test:** `test_aggregate_report_and_state_prerequisites`

**GREEN:** render только из `PLANNED`; mix требует STEMS report; aggregate `kind=story_soundtrack_aggregate` с phase_hashes.

### H9. strict full approval/handoff verification

**Test:** `test_strict_approval_handoff_verification`

**GREEN:** verify отклоняет tampered `forbidden_operations`; exact allowed/forbidden sets; M4A QA re-check.

### H10. strict feedback payload + versioned writer

**Test:** `test_strict_feedback_and_versioned_writer`

**GREEN:** unknown feedback fields rejected; `write_feedback_revision` пишет `spec-v2.json` + `.feedback.json`, refuse overwrite.

---

## Final suite (post-hardening)

```bash
.venv/bin/python -m py_compile media/story-soundtrack/scripts/*.py
.venv/bin/python -m unittest discover -s media/story-soundtrack/scripts/tests -v
```

**Result:** 27 tests OK (~89s, FFmpeg integration included) — *исторический промежуточный результат (post-hardening); не финальный authoritative count.*

## Clean demo (immutable approval)

```bash
.venv/bin/python <<'PY'
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
root = Path("media/story-soundtrack")
scripts = root / "scripts"
with tempfile.TemporaryDirectory() as td:
    work = Path(td)
    shutil.copytree(root / "assets/demo", work / "demo")
    subprocess.run([sys.executable, str(scripts / "make_demo_sources.py"), "--root", str(work)], check=True)
    spec = str(work / "demo/spec-v1.json")
    for s in ("render_story_score.py", "mix_story_audio.py"):
        subprocess.run([sys.executable, str(scripts / s), "--root", str(work), "--spec", spec, "--overwrite"], check=True)
    subprocess.run([sys.executable, str(scripts / "approve_story_soundtrack.py"), "--root", str(work), "--spec", spec, "--approval-note", "clean demo"], check=True)
    r = subprocess.run([sys.executable, str(scripts / "verify_story_soundtrack.py"), "--root", str(work), "--spec", spec, "--require-approved-handoff"], capture_output=True, text=True, check=True)
    assert json.loads(r.stdout)["ok"]
print("GREEN")
PY
```

**GREEN:** `{"ok": true, "errors": []}` in TemporaryDirectory (no committed demo/out)

---

## Grok review blockers (20)

### G1. spec immutable PLANNED input
**Test:** `test_spec_must_remain_planned_immutable_input`
**RED:** `state: STEMS_RENDERED` accepted
**GREEN:** `ContractError: versioned spec must remain PLANNED`

### G2. tonal_center / pitch_collection strict
**Test:** `test_rejects_unsupported_tonal_center_and_pitch_collection`
**RED:** `C` / wrong pitch accepted
**GREEN:** reject unsupported values

### G3. instrumentation dizi + rhythm required
**Test:** `test_instrumentation_requires_dizi_and_rhythm_instrument`
**GREEN:** reject missing dizi or rhythm subset

### G4. exact revision token replacement
**Tests:** `test_replace_revision_token_only_exact_vn`, `test_feedback_revision_replaces_only_exact_revision_token`
**GREEN:** `v1/archive-v10` → `v2/archive-v10`

### G5. source_mix feedback scene_id + no-op
**Test:** `test_source_mix_feedback_requires_scene_id_and_rejects_noop`
**GREEN:** require scene_id; reject identical source_gain

### G6. write_feedback_revision root confinement + symlink
**Tests:** `test_write_feedback_revision_confined_under_root`, `test_write_feedback_revision_rejects_symlink_escape`
**GREEN:** `output spec escapes root`

### G7. render/mix refuse after approval
**Test:** `test_render_mix_refuse_overwrite_after_approval`
**GREEN:** `refusing overwrite: approval_json or handoff_json exists; create a new revision`

### G8. mandatory stem hashes
**Test:** `test_missing_stem_hash_fails_mix`
**GREEN:** `missing required sha256 in stems report for rhythm_wav`

### G9. mix reloads timeline
**Test:** `test_mix_reloads_timeline_before_mixing`
**GREEN:** timeline frames mismatch → SystemExit

### G10–G12. source duration policy
**Tests:** `test_source_shorter_than_scene_pads_tail_and_reports`, `test_source_longer_than_scene_fails_beyond_codec_padding`, `test_source_codec_padding_trim_reported`, `test_mix_reports_source_padding_per_scene`
**GREEN:** pad/trim/report per scene; fail if >1024 excess

### G13. instrumentation layer PCM difference
**Test:** `test_instrumentation_controls_layers_pcm_difference`
**GREEN:** drums-only rhythm RMS ≠ full instrumentation

### G14. multi-bar climax fixture
**Test:** `test_climax_peak_moves_with_declared_scene_multibar`
**GREEN:** peak @ scene-c (7.5s) > early window

### G15–G16. encoded QA tolerances in spec
**Tests:** `test_qa_encoded_tolerance_fields_required`, `test_mix_uses_spec_qa_tolerances_not_hidden_codec`
**GREEN:** `encoded_lufs_tolerance_db` / `encoded_true_peak_tolerance_db`; no hidden codec_tolerance

### G17. numpy sum mixing semantics
**Test:** `test_mix_semantic_numpy_sum_not_amix`
**GREEN:** `combine_method: numpy_sum`, `automatic_normalization: false`

### G18–G22. final hardening gaps
**Tests:**
- `test_source_mp4_shorter_than_scene_pads_tail_and_reports` — MP4 tail padding + RMS
- `test_missing_stem_hash_fails_approve` — approve rejects missing stems sha256
- `test_missing_stem_hash_fails_verify` — verify rejects missing stems sha256
- `test_render_refuses_when_handoff_json_exists` — handoff alone blocks render
- `test_verify_rejects_incomplete_source_padding_report` — per-scene padding fields mandatory
- `test_apply_feedback_cli_requires_root` — CLI `--root` required

**GREEN:** all gates enforced; verify checks aggregate file hashes and source_padding fields.

---

## Final suite (immutable handoff)

```bash
.venv/bin/python -m py_compile media/story-soundtrack/scripts/*.py
.venv/bin/python -m unittest discover -s media/story-soundtrack/scripts/tests -v
```

**Result:** 53 tests OK (~160s, FFmpeg integration included) — *исторический промежуточный результат (immutable handoff); см. финальный authoritative count ниже.*

---

## Final review fixes (decode QA, first mix, layer gates)

**Tests added/updated:**
- `test_truncated_approval_aac_rejected_by_raw_decode_qa` — short AAC within ffprobe tolerance, raw decode rejects
- `test_guzheng_pluck_layer_gates_pcm_and_report` — `guzheng_pluck` gates synthesis
- `test_first_mix_without_overwrite_consumes_stems_report` — STEMS → aggregate без `--overwrite`
- `test_existing_mix_artifacts_require_overwrite` — `source_mixed_*` требует `--overwrite`
- `test_verify_without_handoff_checks_aggregate_phase_hashes` — verify без handoff проверяет phase hashes + source_padding
- `test_handoff_locks_processing_for_shorts` — exact allowed/forbidden sets
- `test_climax_peak_moves_with_declared_scene_multibar` — два climax_scene_id, peak/bar moves
- CLI smoke: render + mix без `--overwrite`

```bash
.venv/bin/python -m py_compile media/story-soundtrack/scripts/*.py
.venv/bin/python -m unittest discover -s media/story-soundtrack/scripts/tests -v
```

**Result (authoritative):** 58 tests OK (~259s, FFmpeg integration included)
