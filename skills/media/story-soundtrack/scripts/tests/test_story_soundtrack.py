#!/usr/bin/env python3
"""Focused tests for story-soundtrack skill (strict TDD slices)."""
from __future__ import annotations

import copy
import inspect
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent.parent
SKILL_ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from story_soundtrack_contract import (  # noqa: E402
    ContractError,
    apply_feedback_revision,
    default_routing_for_class,
    exact_pcm_frames,
    load_and_validate_spec,
    replace_revision_token,
    revision_token_matches,
    resolve_layer_mapping,
    validate_spec_dict,
    write_feedback_revision,
)
from render_story_score import climax_time_seconds, render_score, render_stems  # noqa: E402
from mix_story_audio import (  # noqa: E402
    CODEC_PADDING_MAX_SAMPLES,
    decode_media_to_pcm,
    decode_source_for_scene,
    mix_audio,
    read_pcm16_stereo,
    validate_approval_aac_raw_decode,
    _qa_check_encoded_master,
    _load_stems_report,
    write_pcm16,
)
import approve_story_soundtrack as approve_module  # noqa: E402
import mix_story_audio as mix_module  # noqa: E402
import render_story_score as render_module  # noqa: E402
from approve_story_soundtrack import approve_soundtrack  # noqa: E402
from verify_story_soundtrack import (  # noqa: E402
    EXACT_ALLOWED_OPS,
    EXACT_FORBIDDEN_OPS,
    verify,
    _verify_aggregate_report,
)

DEMO_FIXTURE = SKILL_ROOT / "assets" / "demo"
DEMO_SPEC = DEMO_FIXTURE / "spec-v1.json"
PYTHON = sys.executable
FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None


class RevisionLockTests(unittest.TestCase):
    def test_render_mix_and_approval_share_one_revision_lock(self):
        for function in (
            render_module.render_score,
            mix_module.mix_audio,
            approve_module.approve_soundtrack,
        ):
            with self.subTest(function=function.__name__):
                self.assertIn("with revision_lock(validated)", inspect.getsource(function))


def base_spec() -> dict:
    return json.loads(DEMO_SPEC.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def wav_frames(path: Path) -> int:
    with wave.open(str(path), "rb") as inp:
        return inp.getnframes()


class StorySoundtrackTests(unittest.TestCase):
  def setUp(self) -> None:
    self.tmp = tempfile.TemporaryDirectory()
    self.work = Path(self.tmp.name)
    shutil.copytree(DEMO_FIXTURE, self.work / "demo")
    subprocess.run(
      [PYTHON, str(SCRIPTS / "make_demo_sources.py"), "--root", str(self.work)],
      check=True,
    )

  def tearDown(self) -> None:
    self.tmp.cleanup()

  def _spec_path(self, name: str = "spec.json") -> Path:
    return self.work / "demo" / name

  def _write_spec(self, spec: dict | None = None, name: str = "spec.json") -> Path:
    data = copy.deepcopy(spec or base_spec())
    path = self._spec_path(name)
    write_json(path, data)
    return path

  # 1 strict unknown-field rejection
  def test_rejects_unknown_top_level_field(self) -> None:
    spec = base_spec()
    spec["unexpected"] = True
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("unknown spec fields", str(ctx.exception))

  # 2 path traversal rejection
  def test_rejects_path_traversal(self) -> None:
    spec = base_spec()
    spec["outputs"]["rhythm_wav"] = "../../../escape/v1/rhythm.wav"
    with self.assertRaises(ContractError) as ctx:
      load_and_validate_spec(self.work, self._write_spec(spec))
    self.assertIn("escapes root", str(ctx.exception))

  # 3 timeline gap/order/frame mismatch rejection
  def test_rejects_scene_frame_gap(self) -> None:
    spec = base_spec()
    spec["scenes"][1]["frames"] = [35, 60]
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("gap", str(ctx.exception).lower())

  def test_rejects_non_integral_sample_mapping(self) -> None:
    with self.assertRaises(ContractError):
      exact_pcm_frames(10, 23, 48000)

  # 4 source-audio/class invariants
  def test_silent_scene_forbids_source_audio(self) -> None:
    spec = base_spec()
    spec["scenes"][0]["source_audio"] = "demo/source/voice_scene.wav"
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("forbids source_audio", str(ctx.exception))

  def test_voice_scene_requires_source_audio(self) -> None:
    spec = base_spec()
    spec["scenes"][1]["source_audio"] = None
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("requires source_audio", str(ctx.exception))

  # 5 versioned/unique output paths
  def test_outputs_require_revision_token_and_uniqueness(self) -> None:
    spec = base_spec()
    spec["outputs"]["melody_wav"] = spec["outputs"]["rhythm_wav"]
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("unique", str(ctx.exception))

  def test_outputs_missing_revision_token(self) -> None:
    spec = base_spec()
    spec["outputs"]["rhythm_wav"] = "demo/out/rhythm.wav"
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("revision token", str(ctx.exception))

  # 6 deterministic exact-frame stems and separate rhythm/full previews
  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_render_produces_exact_frame_stems_and_previews(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    report = render_score(validated, overwrite=True)
    expected = validated["timeline"]["exact_pcm_frames"]
    paths = validated["resolved_paths"]
    self.assertEqual(wav_frames(paths["rhythm_wav"]), expected)
    self.assertEqual(wav_frames(paths["melody_wav"]), expected)
    self.assertEqual(wav_frames(paths["full_score_wav"]), expected)
    self.assertTrue(paths["rhythm_preview_m4a"].is_file())
    self.assertTrue(paths["full_preview_m4a"].is_file())
    rhythm_a, _ = read_pcm16_stereo(paths["rhythm_wav"])
  # rerun determinism
    render_score(validated, overwrite=True)
    rhythm_b, _ = read_pcm16_stereo(paths["rhythm_wav"])
    np.testing.assert_array_equal(rhythm_a, rhythm_b)
    self.assertEqual(report["state"], "STEMS_RENDERED")

  # 7 climax mapping to declared scene
  def test_climax_energy_peaks_at_declared_scene(self) -> None:
    spec = base_spec()
    validated = validate_spec_dict(spec)
    fps = validated["timeline"]["fps"]
    climax_sec = climax_time_seconds(validated, fps)
    self.assertAlmostEqual(climax_sec, 1.5, places=3)
    sr = 48000
    duration = validated["timeline"]["exact_duration_seconds"]
    theme_energies = {t["id"]: t["energy"] for t in validated["themes"]}
    rhythm, melody, meta = render_stems(
      duration, sr, validated["style"]["bpm"], validated["style"]["seed"],
      climax_sec, theme_energies, validated["scenes"], fps,
    )
    climax_sample = int(round(climax_sec * sr))
    window = slice(max(0, climax_sample - sr // 4), climax_sample + sr // 4)
    off_sample = int(round(0.25 * sr))
    off_window = slice(off_sample, off_sample + sr // 2)
    climax_rms = float(np.sqrt(np.mean(np.square(rhythm[window]))))
    off_rms = float(np.sqrt(np.mean(np.square(rhythm[off_window]))))
    self.assertGreater(climax_rms, off_rms)
    self.assertEqual(meta["climax_bar"], int(climax_sec // (60.0 / validated["style"]["bpm"] * 4.0)))

  # 8 exact source mix routing and no truncation
  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_source_mix_routing_and_no_truncation(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    report = mix_audio(validated, overwrite=True)
    expected = validated["timeline"]["exact_pcm_frames"]
    mixed_path = validated["resolved_paths"]["source_mixed_wav"]
    self.assertEqual(wav_frames(mixed_path), expected)
    self.assertEqual(report["kind"], "story_soundtrack_aggregate")
    routing = report["phases"]["source_mix"]["routing_windows"]
    voice = next(r for r in routing if r["scene_id"] == "scene-voice")
    silent = next(r for r in routing if r["scene_id"] == "scene-silent")
    music = next(r for r in routing if r["scene_id"] == "scene-music")
    self.assertGreater(voice["midpoint_rhythm_rms"], 0.0)
    self.assertLess(voice["midpoint_melody_rms"], 1e-4)
    self.assertGreater(silent["midpoint_melody_rms"], 0.0)
    self.assertLess(music["midpoint_rhythm_rms"], 1e-4)
    self.assertLess(music["midpoint_melody_rms"], 1e-4)

  # 9 new revision required after feedback/change
  def test_feedback_creates_new_revision_and_resets_state(self) -> None:
    spec = base_spec()
    feedback = {
      "schema_version": 1,
      "story_id": spec["story_id"],
      "from_revision": 1,
      "requested_revision": 2,
      "user_feedback": "Add more rhythm under voice.",
      "requested_changes": [
        {"target": "routing", "change": {"scene_id": "scene-voice", "rhythm_gain": 0.55}}
      ],
    }
    new_spec = apply_feedback_revision(spec, feedback)
    self.assertEqual(new_spec["revision"], 2)
    self.assertEqual(new_spec["state"], "PLANNED")
    self.assertIn("v2", new_spec["outputs"]["rhythm_wav"])
    voice = next(s for s in new_spec["scenes"] if s["id"] == "scene-voice")
    self.assertAlmostEqual(voice["routing"]["rhythm_gain"], 0.55)

  # 10 approval exact-hash binding
  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_approval_binds_exact_audio_hash(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    mix_audio(validated, overwrite=True)
    result = approve_soundtrack(validated, "approved for shorts")
    m4a = validated["resolved_paths"]["source_mixed_approval_m4a"]
    approval = json.loads(validated["resolved_paths"]["approval_json"].read_text(encoding="utf-8"))
    self.assertEqual(approval["approved_audio"]["sha256"], result["approval"]["approved_audio"]["sha256"])
    self.assertTrue(m4a.is_file())

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_approval_rejects_aggregate_identity_and_phase_hash_drift(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    mix_audio(validated, overwrite=True)
    report_path = validated["resolved_paths"]["report_json"]
    aggregate = json.loads(report_path.read_text(encoding="utf-8"))
    aggregate["story_id"] = "wrong-story"
    aggregate["phases"]["stems"]["state"] = "tampered"
    report_path.write_text(json.dumps(aggregate), encoding="utf-8")
    with self.assertRaises(SystemExit) as ctx:
      approve_soundtrack(validated, "must fail")
    message = str(ctx.exception)
    self.assertIn("story_id mismatch", message)
    self.assertIn("stems phase hash mismatch", message)
    self.assertFalse(validated["resolved_paths"]["approval_json"].exists())
    self.assertFalse(validated["resolved_paths"]["handoff_json"].exists())

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_partial_approval_transaction_recovers_on_retry(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    mix_audio(validated, overwrite=True)
    original_replace = approve_module._replace_transaction_file
    calls = 0

    def fail_after_first_replace(source: Path, destination: Path) -> None:
      nonlocal calls
      calls += 1
      if calls == 2:
        raise OSError("injected handoff commit failure")
      original_replace(source, destination)

    approve_module._replace_transaction_file = fail_after_first_replace
    try:
      with self.assertRaisesRegex(OSError, "injected"):
        approve_soundtrack(validated, "recoverable")
    finally:
      approve_module._replace_transaction_file = original_replace

    approval_path = validated["resolved_paths"]["approval_json"]
    handoff_path = validated["resolved_paths"]["handoff_json"]
    self.assertTrue(approval_path.is_file())
    self.assertFalse(handoff_path.exists())
    recovered = approve_soundtrack(validated, "recoverable")
    self.assertEqual(recovered["handoff"]["state"], "HANDED_OFF_TO_SHORTS")
    self.assertTrue(verify(validated, require_approved_handoff=True)["ok"])

  # 11 changed audio invalidates approval/handoff
  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_changed_audio_invalidates_handoff_verification(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    mix_audio(validated, overwrite=True)
    approve_soundtrack(validated, "ok")
    ok = verify(validated, require_approved_handoff=True)
    self.assertTrue(ok["ok"], ok["errors"])
    mixed = validated["resolved_paths"]["source_mixed_wav"]
    data, sr = read_pcm16_stereo(mixed)
    data[1000] += 0.01
    write_pcm16(mixed, data, sr)
    bad = verify(validated, require_approved_handoff=True)
    self.assertFalse(bad["ok"])
    self.assertTrue(any("hash mismatch" in e for e in bad["errors"]))

  # 12 approved handoff locks processing and allows only shorts mux operations
  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_handoff_locks_processing_for_shorts(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    mix_audio(validated, overwrite=True)
    approve_soundtrack(validated, "final")
    handoff = json.loads(validated["resolved_paths"]["handoff_json"].read_text(encoding="utf-8"))
    self.assertTrue(handoff["audio_processing_locked"])
    self.assertEqual(set(handoff["allowed_short_assembly_operations"]), EXACT_ALLOWED_OPS)
    self.assertEqual(set(handoff["forbidden_operations"]), EXACT_FORBIDDEN_OPS)

  def test_default_routing_matches_contract(self) -> None:
    voice = default_routing_for_class("voice")
    self.assertAlmostEqual(voice["rhythm_gain"], 0.456)
    self.assertEqual(voice["melody_gain"], 0.0)

  # --- hardening blockers ---

  def test_skill_frontmatter_valid(self) -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    self.assertTrue(text.startswith("---\n"), "SKILL.md must start with YAML frontmatter")
    end = text.index("\n---\n", 4)
    frontmatter = text[4:end]
    for key in ("name:", "description:", "version:"):
      self.assertIn(key, frontmatter, f"SKILL frontmatter missing {key}")
    self.assertIn("name: story-soundtrack", frontmatter)

  def test_rejects_source_path_escape_and_output_input_alias(self) -> None:
    spec = base_spec()
    spec["scenes"][1]["source_audio"] = "../../../etc/passwd"
    with self.assertRaises(ContractError) as ctx:
      load_and_validate_spec(self.work, self._write_spec(spec))
    self.assertIn("escapes root", str(ctx.exception))

    spec = base_spec()
    alias = "demo/source/v1_voice_scene.wav"
    spec["scenes"][1]["source_audio"] = alias
    spec["outputs"]["rhythm_wav"] = alias
    with self.assertRaises(ContractError) as ctx:
      load_and_validate_spec(self.work, self._write_spec(spec))
    self.assertIn("alias input", str(ctx.exception))

  def test_revision_token_boundary_v1_not_v10(self) -> None:
    self.assertTrue(revision_token_matches("demo/out/v1/rhythm.wav", 1))
    self.assertFalse(revision_token_matches("demo/out/v10/rhythm.wav", 1))
    self.assertFalse(revision_token_matches("demo/out/v1/rhythm.wav", 10))

    spec = base_spec()
    spec["outputs"]["rhythm_wav"] = "demo/out/v10/rhythm.wav"
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("revision token v1", str(ctx.exception))

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_approval_refuses_overwrite(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    mix_audio(validated, overwrite=True)
    approve_soundtrack(validated, "first approval")
    with self.assertRaises(SystemExit) as ctx:
      approve_soundtrack(validated, "second approval")
    self.assertIn("refusing to overwrite", str(ctx.exception))

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_decode_media_formats_and_no_audio_failure(self) -> None:
    length = 4800
    sr = 48000
    wav_path = self.work / "demo" / "source" / "test_tone.wav"
    tone = 0.1 * np.sin(2 * np.pi * 440 * np.arange(length) / sr)
    stereo = np.column_stack([tone, tone])
    write_pcm16(wav_path, stereo, sr)

    decoded_wav = decode_media_to_pcm(wav_path, length, sr)
    self.assertEqual(len(decoded_wav), length)

    m4a_path = self.work / "demo" / "source" / "test_tone.m4a"
    subprocess.run(
      ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
       "-i", str(wav_path), "-c:a", "aac", str(m4a_path)],
      check=True, capture_output=True,
    )
    decoded_m4a = decode_media_to_pcm(m4a_path, length, sr)
    self.assertEqual(len(decoded_m4a), length)

    mp4_path = self.work / "demo" / "source" / "test_tone.mp4"
    subprocess.run(
      ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
       "-i", str(wav_path), "-c:a", "aac", "-c:v", "libx264",
       "-pix_fmt", "yuv420p", "-shortest", str(mp4_path)],
      check=True, capture_output=True,
    )
    decoded_mp4 = decode_media_to_pcm(mp4_path, length, sr)
    self.assertEqual(len(decoded_mp4), length)

    silent_mp4 = self.work / "demo" / "source" / "silent.mp4"
    subprocess.run(
      ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
       "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.1",
       "-an", str(silent_mp4)],
      check=True, capture_output=True,
    )
    with self.assertRaises(ValueError) as ctx:
      decode_media_to_pcm(silent_mp4, length, sr)
    self.assertIn("no audio stream", str(ctx.exception))

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_mix_qa_reports_encoded_master(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    report = mix_audio(validated, overwrite=True)
    qa = report["phases"]["source_mix"]["qa"]
    self.assertEqual(qa["codec"], "aac")
    self.assertEqual(qa["channels"], 2)
    self.assertEqual(qa["sample_rate_hz"], 48000)
    self.assertEqual(qa["decoded_frames"], validated["timeline"]["exact_pcm_frames"])
    expected = validated["timeline"]["exact_pcm_frames"]
    self.assertGreaterEqual(qa["raw_decoded_frames"], expected)
    self.assertEqual(qa["codec_tail_padding_frames"], qa["raw_decoded_frames"] - expected)
    self.assertLessEqual(qa["codec_tail_padding_frames"], CODEC_PADDING_MAX_SAMPLES)
    self.assertIn("encoded_lufs", qa)
    self.assertIn("encoded_true_peak_dbfs", qa)
    self.assertLessEqual(
      abs(qa["probe_duration_seconds"] - qa["expected_duration_seconds"]),
      validated["qa"]["duration_tolerance_seconds"],
    )

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_rejects_aac_codec_tail_padding_over_limit(self) -> None:
    sr = 48000
    expected = sr
    excessive = expected + CODEC_PADDING_MAX_SAMPLES + 4096
    wav_path = self.work / "demo" / "source" / "excessive-tail.wav"
    m4a_path = self.work / "demo" / "source" / "excessive-tail.m4a"
    write_pcm16(wav_path, np.zeros((excessive, 2), dtype=np.float32), sr)
    subprocess.run(
      ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
       "-i", str(wav_path), "-c:a", "aac", str(m4a_path)],
      check=True, capture_output=True,
    )
    with self.assertRaises(RuntimeError) as ctx:
      validate_approval_aac_raw_decode(m4a_path, expected, sr)
    self.assertIn("codec tail padding", str(ctx.exception))

  def test_theme_energy_affects_output_and_unsupported_instrumentation_rejected(self) -> None:
    spec = base_spec()
    spec["style"]["instrumentation"] = ["guzheng", "synth_lead"]
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("unsupported instrumentation", str(ctx.exception))

    validated = validate_spec_dict(base_spec())
    sr = 48000
    duration = validated["timeline"]["exact_duration_seconds"]
    fps = validated["timeline"]["fps"]
    climax_sec = climax_time_seconds(validated, fps)
    low_energy = {t["id"]: 0.2 for t in validated["themes"]}
    high_energy = {t["id"]: 0.95 for t in validated["themes"]}
    rhythm_low, melody_low, _ = render_stems(
      duration, sr, validated["style"]["bpm"], validated["style"]["seed"],
      climax_sec, low_energy, validated["scenes"], fps,
    )
    rhythm_high, melody_high, _ = render_stems(
      duration, sr, validated["style"]["bpm"], validated["style"]["seed"],
      climax_sec, high_energy, validated["scenes"], fps,
    )
    low_rms = float(np.sqrt(np.mean(np.square(melody_low))))
    high_rms = float(np.sqrt(np.mean(np.square(melody_high))))
    self.assertGreater(high_rms, low_rms)

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_aggregate_report_and_state_prerequisites(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    validated_bad = dict(validated)
    validated_bad["state"] = "SCORE_REVIEW"
    with self.assertRaises(SystemExit) as ctx:
      render_score(validated_bad, overwrite=True)
    self.assertIn("PLANNED", str(ctx.exception))

    with self.assertRaises(SystemExit) as ctx:
      mix_audio(validated, overwrite=True)
    self.assertIn("STEMS_RENDERED report", str(ctx.exception))

    render_score(validated, overwrite=True)
    report = mix_audio(validated, overwrite=True)
    self.assertEqual(report["kind"], "story_soundtrack_aggregate")
    self.assertIn("stems", report["phases"])
    self.assertIn("source_mix", report["phases"])
    self.assertIn("phase_hashes", report)
    self.assertEqual(report["phases"]["stems"]["kind"], "story_soundtrack_stems")
    self.assertEqual(report["phases"]["source_mix"]["kind"], "story_soundtrack_source_mix")

    report["phases"]["stems"]["story_id"] = "wrong-story"
    report["phases"]["stems"]["state"] = "SOURCE_MIX_REVIEW"
    report["phase_hashes"]["stems_sha256"] = __import__("hashlib").sha256(
      json.dumps(report["phases"]["stems"], sort_keys=True).encode("utf-8")
    ).hexdigest()
    errors = _verify_aggregate_report(validated, report)
    self.assertTrue(any("stems phase story_id mismatch" in error for error in errors))
    self.assertTrue(any("stems phase state" in error for error in errors))
    report["phases"]["stems"]["state"] = "STEMS_RENDERED"
    write_json(validated["resolved_paths"]["report_json"], report)
    with self.assertRaisesRegex(SystemExit, "stems phase story_id mismatch"):
      _load_stems_report(validated)

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_strict_approval_handoff_verification(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    mix_audio(validated, overwrite=True)
    approve_soundtrack(validated, "strict verify")
    handoff_path = validated["resolved_paths"]["handoff_json"]
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    handoff["forbidden_operations"] = list(handoff["forbidden_operations"]) + ["extra_op"]
    handoff_path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    bad = verify(validated, require_approved_handoff=True)
    self.assertFalse(bad["ok"])
    self.assertTrue(any("forbidden_operations" in e for e in bad["errors"]))

  def test_strict_feedback_and_versioned_writer(self) -> None:
    spec = base_spec()
    feedback = {
      "schema_version": 1,
      "story_id": spec["story_id"],
      "from_revision": 1,
      "requested_revision": 2,
      "user_feedback": "Louder rhythm.",
      "requested_changes": [
        {"target": "routing", "change": {"scene_id": "scene-voice", "rhythm_gain": 0.55, "bogus": True}}
      ],
    }
    with self.assertRaises(ContractError) as ctx:
      apply_feedback_revision(spec, feedback)
    self.assertIn("unknown fields for feedback target routing", str(ctx.exception))

    feedback["requested_changes"][0]["change"] = {"scene_id": "scene-voice", "rhythm_gain": 0.55}
    out_spec = self.work / "demo" / "spec-v2.json"
    validated = load_and_validate_spec(self.work, self._write_spec())
    new_spec = write_feedback_revision(validated, feedback, out_spec, root=self.work)
    self.assertTrue(out_spec.is_file())
    self.assertTrue(out_spec.with_suffix(".feedback.json").is_file())
    self.assertEqual(new_spec["revision"], 2)
    with self.assertRaises(ContractError):
      write_feedback_revision(validated, feedback, out_spec, root=self.work)

  # --- Grok review blockers (strict TDD) ---

  def test_spec_must_remain_planned_immutable_input(self) -> None:
    spec = base_spec()
    spec["state"] = "STEMS_RENDERED"
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("PLANNED", str(ctx.exception))

  def test_rejects_unsupported_tonal_center_and_pitch_collection(self) -> None:
    spec = base_spec()
    spec["style"]["tonal_center"] = "C"
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("tonal_center", str(ctx.exception))

    spec = base_spec()
    spec["style"]["pitch_collection"] = ["D", "E", "G", "A", "B"]
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("pitch_collection", str(ctx.exception))

  def test_instrumentation_requires_dizi_and_rhythm_instrument(self) -> None:
    spec = base_spec()
    spec["style"]["instrumentation"] = ["guzheng", "bass", "drums"]
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("dizi", str(ctx.exception).lower())

    spec = base_spec()
    spec["style"]["instrumentation"] = ["dizi"]
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("rhythm instrument", str(ctx.exception).lower())

  def test_replace_revision_token_only_exact_vn(self) -> None:
    path = "demo/out/v1/archive-v10/rhythm.wav"
    self.assertEqual(replace_revision_token(path, 1, 2), "demo/out/v2/archive-v10/rhythm.wav")
    self.assertEqual(replace_revision_token("demo/out/v10/rhythm.wav", 10, 11), "demo/out/v11/rhythm.wav")

  def test_feedback_revision_replaces_only_exact_revision_token(self) -> None:
    spec = base_spec()
    spec["outputs"]["rhythm_wav"] = "demo/out/v1/archive-v10/rhythm.wav"
    feedback = {
      "schema_version": 1,
      "story_id": spec["story_id"],
      "from_revision": 1,
      "requested_revision": 2,
      "user_feedback": "Bump revision only.",
      "requested_changes": [
        {"target": "routing", "change": {"scene_id": "scene-voice", "rhythm_gain": 0.50}}
      ],
    }
    new_spec = apply_feedback_revision(spec, feedback)
    self.assertEqual(new_spec["outputs"]["rhythm_wav"], "demo/out/v2/archive-v10/rhythm.wav")

  def test_source_mix_feedback_requires_scene_id_and_rejects_noop(self) -> None:
    spec = base_spec()
    feedback = {
      "schema_version": 1,
      "story_id": spec["story_id"],
      "from_revision": 1,
      "requested_revision": 2,
      "user_feedback": "No scene.",
      "requested_changes": [
        {"target": "source_mix", "change": {"source_gain": 0.9}}
      ],
    }
    with self.assertRaises(ContractError) as ctx:
      apply_feedback_revision(spec, feedback)
    self.assertIn("scene_id", str(ctx.exception))

    voice = next(s for s in spec["scenes"] if s["id"] == "scene-voice")
    feedback["requested_changes"][0]["change"] = {
      "scene_id": "scene-voice",
      "source_gain": voice["routing"]["source_gain"],
    }
    with self.assertRaises(ContractError) as ctx:
      apply_feedback_revision(spec, feedback)
    self.assertIn("no-op", str(ctx.exception).lower())

  def test_write_feedback_revision_confined_under_root(self) -> None:
    spec = base_spec()
    feedback = {
      "schema_version": 1,
      "story_id": spec["story_id"],
      "from_revision": 1,
      "requested_revision": 2,
      "user_feedback": "Louder rhythm.",
      "requested_changes": [
        {"target": "routing", "change": {"scene_id": "scene-voice", "rhythm_gain": 0.55}}
      ],
    }
    validated = load_and_validate_spec(self.work, self._write_spec())
    escape_out = Path("/tmp/escape-spec-v2.json")
    with self.assertRaises(ContractError) as ctx:
      write_feedback_revision(validated, feedback, escape_out, root=self.work)
    self.assertIn("escapes root", str(ctx.exception))

  def test_write_feedback_revision_rejects_symlink_escape(self) -> None:
    outside_file = Path(self.tmp.name).parent / "outside_escape_spec.json"
    outside_file.write_text("{}", encoding="utf-8")
    link = self.work / "demo" / "evil-link.json"
    if link.exists() or link.is_symlink():
      link.unlink()
    link.symlink_to(outside_file)
    spec = base_spec()
    feedback = {
      "schema_version": 1,
      "story_id": spec["story_id"],
      "from_revision": 1,
      "requested_revision": 2,
      "user_feedback": "Symlink escape.",
      "requested_changes": [
        {"target": "routing", "change": {"scene_id": "scene-voice", "rhythm_gain": 0.55}}
      ],
    }
    validated = load_and_validate_spec(self.work, self._write_spec())
    with self.assertRaises(ContractError) as ctx:
      write_feedback_revision(validated, feedback, link, root=self.work)
    self.assertIn("escapes root", str(ctx.exception))

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_render_mix_refuse_overwrite_after_approval(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    mix_audio(validated, overwrite=True)
    approve_soundtrack(validated, "locked")
    with self.assertRaises(SystemExit) as ctx:
      render_score(validated, overwrite=True)
    self.assertIn("new revision", str(ctx.exception).lower())
    with self.assertRaises(SystemExit) as ctx:
      mix_audio(validated, overwrite=True)
    self.assertIn("new revision", str(ctx.exception).lower())

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_missing_stem_hash_fails_mix(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    report_path = validated["resolved_paths"]["report_json"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["files"]["rhythm"].pop("sha256", None)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with self.assertRaises(SystemExit) as ctx:
      mix_audio(validated, overwrite=True)
    self.assertIn("missing required sha256", str(ctx.exception).lower())

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_mix_reloads_timeline_before_mixing(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    timeline_path = validated["timeline_path"]
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    timeline["scenes"][1]["frames"] = [30, 55]
    timeline_path.write_text(json.dumps(timeline, indent=2) + "\n", encoding="utf-8")
    with self.assertRaises(SystemExit) as ctx:
      mix_audio(validated, overwrite=True)
    self.assertIn("timeline", str(ctx.exception).lower())

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_source_shorter_than_scene_pads_tail_and_reports(self) -> None:
    sr = 48000
    fps = 30
    scene_frames = 30
    scene_samples = exact_pcm_frames(scene_frames, fps, sr)
    short_path = self.work / "demo" / "source" / "short_voice.wav"
    tone_len = scene_samples // 2
    tone = 0.2 * np.sin(2 * np.pi * 440 * np.arange(tone_len) / sr)
    write_pcm16(short_path, np.column_stack([tone, tone]), sr)
    pcm, meta = decode_source_for_scene(short_path, scene_samples, sr)
    self.assertEqual(len(pcm), scene_samples)
    self.assertEqual(meta["decoded_source_frames"], tone_len)
    self.assertEqual(meta["padded_tail_frames"], scene_samples - tone_len)
    self.assertEqual(meta["trimmed_codec_padding_frames"], 0)
    tail = pcm[tone_len:]
    self.assertLess(float(np.max(np.abs(tail))), 1e-9)
    self.assertGreater(float(np.sqrt(np.mean(np.square(pcm[:tone_len])))), 0.01)

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_source_longer_than_scene_fails_beyond_codec_padding(self) -> None:
    sr = 48000
    fps = 30
    scene_samples = exact_pcm_frames(30, fps, sr)
    long_path = self.work / "demo" / "source" / "long_voice.wav"
    extra = CODEC_PADDING_MAX_SAMPLES + 1
    tone_len = scene_samples + extra
    tone = 0.2 * np.sin(2 * np.pi * 440 * np.arange(tone_len) / sr)
    write_pcm16(long_path, np.column_stack([tone, tone]), sr)
    with self.assertRaises(ValueError) as ctx:
      decode_source_for_scene(long_path, scene_samples, sr)
    self.assertIn("longer than scene", str(ctx.exception).lower())

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_source_codec_padding_trim_reported(self) -> None:
    sr = 48000
    fps = 30
    scene_samples = exact_pcm_frames(30, fps, sr)
    long_path = self.work / "demo" / "source" / "pad_voice.wav"
    trim = min(CODEC_PADDING_MAX_SAMPLES, 512)
    tone_len = scene_samples + trim
    tone = 0.2 * np.sin(2 * np.pi * 440 * np.arange(tone_len) / sr)
    write_pcm16(long_path, np.column_stack([tone, tone]), sr)
    pcm, meta = decode_source_for_scene(long_path, scene_samples, sr)
    self.assertEqual(len(pcm), scene_samples)
    self.assertEqual(meta["trimmed_codec_padding_frames"], trim)
    self.assertEqual(meta["padded_tail_frames"], 0)

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_mix_reports_source_padding_per_scene(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    report = mix_audio(validated, overwrite=True)
    padding = report["phases"]["source_mix"].get("source_padding", [])
    voice = next(p for p in padding if p["scene_id"] == "scene-voice")
    self.assertIn("decoded_source_frames", voice)
    self.assertIn("padded_tail_frames", voice)
    self.assertIn("trimmed_codec_padding_frames", voice)
    self.assertGreater(voice["decoded_source_rms"], 0.0)

  def test_instrumentation_controls_layers_pcm_difference(self) -> None:
    validated = validate_spec_dict(base_spec())
    sr = 48000
    duration = validated["timeline"]["exact_duration_seconds"]
    fps = validated["timeline"]["fps"]
    climax_sec = climax_time_seconds(validated, fps)
    theme_energies = {t["id"]: t["energy"] for t in validated["themes"]}
    drums_only = ["dizi", "drums"]
    full_inst = validated["style"]["instrumentation"]
    rhythm_drums, melody_drums, _ = render_stems(
      duration, sr, validated["style"]["bpm"], validated["style"]["seed"],
      climax_sec, theme_energies, validated["scenes"], fps,
      instrumentation=drums_only,
    )
    rhythm_full, melody_full, _ = render_stems(
      duration, sr, validated["style"]["bpm"], validated["style"]["seed"],
      climax_sec, theme_energies, validated["scenes"], fps,
      instrumentation=full_inst,
    )
    drums_rms = float(np.sqrt(np.mean(np.square(rhythm_drums))))
    full_rms = float(np.sqrt(np.mean(np.square(rhythm_full))))
    self.assertNotAlmostEqual(drums_rms, full_rms, places=3)
    mapping = resolve_layer_mapping(full_inst)
    self.assertTrue(mapping["guzheng_pluck"])
    self.assertTrue(mapping["dizi_melody"])
    self.assertFalse(resolve_layer_mapping(drums_only)["guzheng_pluck"])

  def test_guzheng_pluck_layer_gates_pcm_and_report(self) -> None:
    validated = validate_spec_dict(base_spec())
    sr = 48000
    duration = validated["timeline"]["exact_duration_seconds"]
    fps = validated["timeline"]["fps"]
    climax_sec = climax_time_seconds(validated, fps)
    theme_energies = {t["id"]: t["energy"] for t in validated["themes"]}
    base_layers = resolve_layer_mapping(validated["style"]["instrumentation"])
    pluck_only = {**base_layers, "guzheng_pluck": True, "guzheng_comping": False, "guzheng_pad": False, "bass": False, "low_drum": False, "woodblock": False, "shaker": False}
    pluck_off = {**pluck_only, "guzheng_pluck": False}
    rhythm_pluck, _, meta_pluck = render_stems(
      duration, sr, validated["style"]["bpm"], validated["style"]["seed"],
      climax_sec, theme_energies, validated["scenes"], fps,
      layer_mapping=pluck_only,
    )
    rhythm_off, _, meta_off = render_stems(
      duration, sr, validated["style"]["bpm"], validated["style"]["seed"],
      climax_sec, theme_energies, validated["scenes"], fps,
      layer_mapping=pluck_off,
    )
    pluck_rms = float(np.sqrt(np.mean(np.square(rhythm_pluck))))
    off_rms = float(np.sqrt(np.mean(np.square(rhythm_off))))
    self.assertGreater(pluck_rms, off_rms)
    self.assertTrue(meta_pluck["resolved_layer_mapping"]["guzheng_pluck"])
    self.assertFalse(meta_off["resolved_layer_mapping"]["guzheng_pluck"])

  def test_climax_peak_moves_with_declared_scene_multibar(self) -> None:
    def multibar_spec(climax_scene_id: str) -> dict:
      spec = base_spec()
      spec["timeline"]["total_frames"] = 360
      spec["scenes"] = [
        {"id": "scene-a", "frames": [0, 90], "audio_class": "silent", "source_audio": None,
         "theme_ids": ["theme-main"], "routing": {"source_gain": 0.0, "rhythm_gain": 1.0, "melody_gain": 1.0}},
        {"id": "scene-b", "frames": [90, 180], "audio_class": "silent", "source_audio": None,
         "theme_ids": ["theme-main"], "routing": {"source_gain": 0.0, "rhythm_gain": 1.0, "melody_gain": 1.0}},
        {"id": "scene-c", "frames": [180, 270], "audio_class": "silent", "source_audio": None,
         "theme_ids": ["theme-main"], "routing": {"source_gain": 0.0, "rhythm_gain": 1.0, "melody_gain": 1.0}},
        {"id": "scene-d", "frames": [270, 360], "audio_class": "silent", "source_audio": None,
         "theme_ids": ["theme-main"], "routing": {"source_gain": 0.0, "rhythm_gain": 1.0, "melody_gain": 1.0}},
      ]
      spec["dramaturgy"]["climax_scene_id"] = climax_scene_id
      spec["themes"][0]["scene_ids"] = ["scene-a", "scene-b", "scene-c"]
      return validate_spec_dict(spec)

    def climax_meta_for(validated: dict) -> tuple[int, float]:
      fps = validated["timeline"]["fps"]
      sr = 48000
      duration = validated["timeline"]["exact_duration_seconds"]
      climax_sec = climax_time_seconds(validated, fps)
      theme_energies = {t["id"]: t["energy"] for t in validated["themes"]}
      rhythm, _, meta = render_stems(
        duration, sr, validated["style"]["bpm"], validated["style"]["seed"],
        climax_sec, theme_energies, validated["scenes"], fps,
        instrumentation=validated["style"]["instrumentation"],
      )
      climax_sample = int(round(climax_sec * sr))
      climax_rms = float(np.sqrt(np.mean(np.square(
        rhythm[max(0, climax_sample - sr // 4):climax_sample + sr // 4]
      ))))
      return meta["climax_bar"], climax_rms

    validated_b = multibar_spec("scene-b")
    validated_c = multibar_spec("scene-c")
    bar_b, rms_b = climax_meta_for(validated_b)
    bar_c, rms_c = climax_meta_for(validated_c)
    self.assertNotEqual(bar_b, bar_c)
    self.assertGreater(rms_c, rms_b * 0.85)

  def test_qa_encoded_tolerance_fields_required(self) -> None:
    spec = base_spec()
    spec["qa"].pop("encoded_lufs_tolerance_db")
    with self.assertRaises(ContractError) as ctx:
      validate_spec_dict(spec)
    self.assertIn("encoded_lufs_tolerance_db", str(ctx.exception))

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_mix_uses_spec_qa_tolerances_not_hidden_codec(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    report = mix_audio(validated, overwrite=True)
    qa = report["phases"]["source_mix"]["qa"]
    self.assertEqual(qa["encoded_lufs_tolerance_db"], validated["qa"]["encoded_lufs_tolerance_db"])
    self.assertEqual(qa["encoded_true_peak_tolerance_db"], validated["qa"]["encoded_true_peak_tolerance_db"])
    self.assertNotIn("codec_tolerance", qa)

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_source_mp4_shorter_than_scene_pads_tail_and_reports(self) -> None:
    sr = 48000
    fps = 30
    scene_samples = exact_pcm_frames(30, fps, sr)
    short_wav = self.work / "demo" / "source" / "short_mp4_src.wav"
    tone_len = scene_samples // 2
    tone = 0.2 * np.sin(2 * np.pi * 440 * np.arange(tone_len) / sr)
    write_pcm16(short_wav, np.column_stack([tone, tone]), sr)
    mp4_path = self.work / "demo" / "source" / "short_voice.mp4"
    subprocess.run(
      ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
       "-i", str(short_wav), "-c:a", "aac", "-c:v", "libx264",
       "-pix_fmt", "yuv420p", str(mp4_path)],
      check=True, capture_output=True,
    )
    pcm, meta = decode_source_for_scene(mp4_path, scene_samples, sr)
    self.assertEqual(len(pcm), scene_samples)
    self.assertGreater(meta["decoded_source_frames"], 0)
    self.assertLess(meta["decoded_source_frames"], scene_samples)
    self.assertEqual(meta["padded_tail_frames"], scene_samples - meta["decoded_source_frames"])
    decoded_rms = float(np.sqrt(np.mean(np.square(pcm[: meta["decoded_source_frames"]]))))
    self.assertGreater(decoded_rms, 0.005)

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_missing_stem_hash_fails_approve(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    mix_audio(validated, overwrite=True)
    report_path = validated["resolved_paths"]["report_json"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["phases"]["stems"]["files"]["melody"].pop("sha256", None)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with self.assertRaises(SystemExit) as ctx:
      approve_soundtrack(validated, "should fail")
    self.assertIn("missing required sha256", str(ctx.exception).lower())

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_missing_stem_hash_fails_verify(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    mix_audio(validated, overwrite=True)
    approve_soundtrack(validated, "verify hash gate")
    report_path = validated["resolved_paths"]["report_json"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["phases"]["stems"]["files"]["rhythm"].pop("sha256", None)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bad = verify(validated, require_approved_handoff=True)
    self.assertFalse(bad["ok"])
    self.assertTrue(any("missing required sha256" in e for e in bad["errors"]))

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_render_refuses_when_handoff_json_exists(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    mix_audio(validated, overwrite=True)
    approve_soundtrack(validated, "handoff lock")
    handoff_path = validated["resolved_paths"]["handoff_json"]
    approval_path = validated["resolved_paths"]["approval_json"]
    approval_path.unlink()
    with self.assertRaises(SystemExit) as ctx:
      render_score(validated, overwrite=True)
    self.assertIn("handoff_json", str(ctx.exception).lower())
    self.assertIn("new revision", str(ctx.exception).lower())
    self.assertTrue(handoff_path.is_file())

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_verify_rejects_incomplete_source_padding_report(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    report = mix_audio(validated, overwrite=True)
    padding = report["phases"]["source_mix"]["source_padding"]
    padding[0].pop("padded_tail_frames", None)
    errors = _verify_aggregate_report(validated, report)
    self.assertTrue(any("padded_tail_frames" in e for e in errors))

  def test_apply_feedback_cli_requires_root(self) -> None:
    proc = subprocess.run(
      [PYTHON, str(SCRIPTS / "apply_feedback_revision.py"),
       "--spec", "demo/spec-v1.json",
       "--feedback", "demo/feedback.json",
       "--output-spec", "demo/spec-v2.json"],
      capture_output=True, text=True,
    )
    self.assertNotEqual(proc.returncode, 0)
    self.assertIn("--root", proc.stderr)

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_mix_semantic_numpy_sum_not_amix(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated, overwrite=True)
    report = mix_audio(validated, overwrite=True)
    mixing = report["phases"]["source_mix"]["mixing"]
    self.assertEqual(mixing["combine_method"], "numpy_sum")
    self.assertFalse(mixing["automatic_normalization"])

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_first_mix_without_overwrite_consumes_stems_report(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated)
    report_path = validated["resolved_paths"]["report_json"]
    stems_report = json.loads(report_path.read_text(encoding="utf-8"))
    self.assertEqual(stems_report["kind"], "story_soundtrack_stems")
    self.assertEqual(stems_report["state"], "STEMS_RENDERED")
    aggregate = mix_audio(validated)
    self.assertEqual(aggregate["kind"], "story_soundtrack_aggregate")
    self.assertEqual(aggregate["state"], "SOURCE_MIX_REVIEW")
    with self.assertRaises(SystemExit) as ctx:
      mix_audio(validated)
    self.assertIn("source_mixed", str(ctx.exception).lower())

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_existing_mix_artifacts_require_overwrite(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated)
    mix_audio(validated)
    with self.assertRaises(SystemExit) as ctx:
      mix_audio(validated, overwrite=False)
    self.assertIn("source_mixed", str(ctx.exception).lower())
    mix_audio(validated, overwrite=True)

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_truncated_approval_aac_rejected_by_raw_decode_qa(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated)
    mix_audio(validated)
    paths = validated["resolved_paths"]
    sr = validated["timeline"]["sample_rate_hz"]
    expected_frames = validated["timeline"]["exact_pcm_frames"]
    expected_duration = expected_frames / sr
    tolerance = validated["qa"]["duration_tolerance_seconds"]
    short_duration = expected_duration - tolerance + 0.01
    short_m4a = paths["source_mixed_approval_m4a"].with_suffix(".short.m4a")
    subprocess.run(
      ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
       "-i", str(paths["source_mixed_wav"]),
       "-t", f"{short_duration:.6f}",
       "-c:a", "aac", "-b:a", "192k", str(short_m4a)],
      check=True, capture_output=True,
    )
    paths["source_mixed_approval_m4a"].unlink()
    short_m4a.replace(paths["source_mixed_approval_m4a"])
    with self.assertRaises(RuntimeError) as ctx:
      _qa_check_encoded_master(
        paths["source_mixed_wav"],
        paths["source_mixed_approval_m4a"],
        validated,
        expected_frames,
        sr,
      )
    self.assertIn("raw decode too short", str(ctx.exception).lower())
    bad = verify(validated, require_approved_handoff=False)
    self.assertFalse(bad["ok"])
    self.assertTrue(any("raw decode too short" in e.lower() for e in bad["errors"]))

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_verify_without_handoff_checks_aggregate_phase_hashes(self) -> None:
    spec_path = self._write_spec()
    validated = load_and_validate_spec(self.work, spec_path)
    render_score(validated)
    mix_audio(validated)
    ok = verify(validated, require_approved_handoff=False)
    self.assertTrue(ok["ok"], ok["errors"])
    report_path = validated["resolved_paths"]["report_json"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["phase_hashes"]["stems_sha256"] = "0" * 64
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bad = verify(validated, require_approved_handoff=False)
    self.assertFalse(bad["ok"])
    self.assertTrue(any("stems phase hash mismatch" in e for e in bad["errors"]))
    padding = report["phases"]["source_mix"]["source_padding"]
    padding[0].pop("decoded_source_rms", None)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bad_padding = verify(validated, require_approved_handoff=False)
    self.assertFalse(bad_padding["ok"])
    self.assertTrue(any("decoded_source_rms" in e for e in bad_padding["errors"]))


class CLISmokeTests(unittest.TestCase):
  def setUp(self) -> None:
    self.tmp = tempfile.TemporaryDirectory()
    self.work = Path(self.tmp.name)
    shutil.copytree(DEMO_FIXTURE, self.work / "demo")
    subprocess.run(
      [PYTHON, str(SCRIPTS / "make_demo_sources.py"), "--root", str(self.work)],
      check=True,
    )

  def tearDown(self) -> None:
    self.tmp.cleanup()

  @unittest.skipUnless(FFMPEG_AVAILABLE, "ffmpeg required")
  def test_demo_pipeline_cli(self) -> None:
    spec = str(self.work / "demo" / "spec-v1.json")
    root = str(self.work)
    proc = subprocess.run(
      [PYTHON, str(SCRIPTS / "render_story_score.py"), "--root", root, "--spec", spec],
      capture_output=True, text=True,
    )
    self.assertEqual(proc.returncode, 0, proc.stderr)
    proc = subprocess.run(
      [PYTHON, str(SCRIPTS / "mix_story_audio.py"), "--root", root, "--spec", spec],
      capture_output=True, text=True,
    )
    self.assertEqual(proc.returncode, 0, proc.stderr)
    proc = subprocess.run(
      [PYTHON, str(SCRIPTS / "approve_story_soundtrack.py"), "--root", root, "--spec", spec,
       "--approval-note", "demo approval"],
      capture_output=True, text=True,
    )
    self.assertEqual(proc.returncode, 0, proc.stderr)
    proc = subprocess.run(
      [PYTHON, str(SCRIPTS / "verify_story_soundtrack.py"), "--root", root, "--spec", spec,
       "--require-approved-handoff"],
      capture_output=True, text=True,
    )
    self.assertEqual(proc.returncode, 0, proc.stdout)
    payload = json.loads(proc.stdout.strip())
    self.assertTrue(payload["ok"])


if __name__ == "__main__":
  unittest.main()
