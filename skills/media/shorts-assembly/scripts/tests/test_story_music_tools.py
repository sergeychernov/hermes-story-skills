#!/usr/bin/env python3
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
GENERATOR = SCRIPTS / "render_pentatonic_story_score.py"
ENCODER = SCRIPTS / "encode_story_audio_preview.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StoryMusicToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "timeline.json").write_text(
            json.dumps({"total_seconds": 1.25}), encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def score_spec(self, suffix: str) -> Path:
        path = self.root / f"score-{suffix}.json"
        path.write_text(json.dumps({
            "schema_version": 1,
            "preset": "chinese_travel_pentatonic_v1",
            "duration": {"timeline": "timeline.json"},
            "seed": 20260814,
            "sample_rate_hz": 48000,
            "bpm": 80.0,
            "outputs": {
                "rhythm_wav": f"out/rhythm-{suffix}.wav",
                "melody_wav": f"out/melody-{suffix}.wav",
                "full_preview_wav": f"out/full-{suffix}.wav",
                "report": f"out/score-{suffix}.report.json"
            }
        }), encoding="utf-8")
        return path

    def run_tool(self, script: Path, spec: Path, expect_ok: bool = True):
        result = subprocess.run(
            [sys.executable, str(script), "--root", str(self.root), "--spec", str(spec)],
            text=True, capture_output=True
        )
        if expect_ok and result.returncode != 0:
            self.fail(f"tool failed: {result.stdout}\n{result.stderr}")
        return result

    def test_score_is_sample_exact_and_deterministic(self):
        self.run_tool(GENERATOR, self.score_spec("a"))
        self.run_tool(GENERATOR, self.score_spec("b"))
        for stem in ("rhythm", "melody", "full"):
            a = self.root / "out" / f"{stem}-a.wav"
            b = self.root / "out" / f"{stem}-b.wav"
            self.assertEqual(sha256(a), sha256(b), stem)
            with wave.open(str(a), "rb") as inp:
                self.assertEqual(inp.getframerate(), 48000)
                self.assertEqual(inp.getnchannels(), 2)
                self.assertEqual(inp.getnframes(), 60000)
        report = json.loads((self.root / "out/score-a.report.json").read_text())
        self.assertEqual(report["exact_pcm_frames"], 60000)
        self.assertEqual(report["pitch_collection"], ["D", "E", "F#", "A", "B"])
        self.assertEqual(report["mixing"]["muxed_to_video"], False)
        self.assertEqual(report["rhythm_provenance"], "one continuous global beat/phase timeline from t=0")
        self.assertRegex(report["implementation_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(report["python_version"])
        self.assertTrue(report["numpy_version"])

    def test_score_refuses_overwrite_and_path_escape(self):
        spec = self.score_spec("same")
        self.run_tool(GENERATOR, spec)
        duplicate = self.run_tool(GENERATOR, spec, expect_ok=False)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("overwrite", (duplicate.stdout + duplicate.stderr).lower())

        bad = json.loads(spec.read_text())
        bad["outputs"]["rhythm_wav"] = "../escaped.wav"
        bad_path = self.root / "bad.json"
        bad_path.write_text(json.dumps(bad))
        escaped = self.run_tool(GENERATOR, bad_path, expect_ok=False)
        self.assertNotEqual(escaped.returncode, 0)
        self.assertFalse((self.root.parent / "escaped.wav").exists())

    def test_score_spec_rejects_unknown_fields_and_output_aliases(self):
        spec_path = self.score_spec("strict")
        spec = json.loads(spec_path.read_text())
        spec["bpmm"] = 81
        spec_path.write_text(json.dumps(spec))
        unknown = self.run_tool(GENERATOR, spec_path, expect_ok=False)
        self.assertNotEqual(unknown.returncode, 0)
        self.assertIn("unknown", (unknown.stdout + unknown.stderr).lower())

        spec_path = self.score_spec("alias")
        spec = json.loads(spec_path.read_text())
        spec["outputs"]["melody_wav"] = spec["outputs"]["rhythm_wav"]
        spec_path.write_text(json.dumps(spec))
        alias = self.run_tool(GENERATOR, spec_path, expect_ok=False)
        self.assertNotEqual(alias.returncode, 0)
        self.assertIn("unique", (alias.stdout + alias.stderr).lower())

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg required")
    def test_audio_preview_preserves_duration_after_loudnorm(self):
        self.run_tool(GENERATOR, self.score_spec("encode"))
        spec = self.root / "encode.json"
        spec.write_text(json.dumps({
            "schema_version": 1,
            "input_wav": "out/full-encode.wav",
            "duration": {"timeline": "timeline.json"},
            "output_m4a": "out/listening.m4a",
            "report": "out/listening.report.json",
            "sample_rate_hz": 48000,
            "bitrate": "192k",
            "target_lufs": -16.0,
            "target_true_peak_dbfs": -2.5,
            "target_lra_lu": 8.0
        }), encoding="utf-8")
        self.run_tool(ENCODER, spec)
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", str(self.root / "out/listening.m4a")
        ], text=True, capture_output=True, check=True)
        duration = float(probe.stdout.strip())
        self.assertGreater(duration, 1.20)  # catches 192 kHz loudnorm quarter-duration regression
        self.assertLessEqual(abs(duration - 1.25), 1024 / 48000 + 1e-6)
        report = json.loads((self.root / "out/listening.report.json").read_text())
        self.assertEqual(report["input_pcm_frames"], 60000)
        self.assertEqual(report["sample_rate_hz"], 48000)
        self.assertTrue(report["full_decode_verified"])
        self.assertIn("aresample=48000,atrim=end_sample=60000", report["render_filter"])
        self.assertRegex(report["implementation_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(report["ffmpeg_version"])

        strict = json.loads(spec.read_text())
        strict["target_luf"] = -15
        strict_path = self.root / "encode-strict.json"
        strict_path.write_text(json.dumps(strict))
        rejected = self.run_tool(ENCODER, strict_path, expect_ok=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("unknown", (rejected.stdout + rejected.stderr).lower())


if __name__ == "__main__":
    unittest.main()
