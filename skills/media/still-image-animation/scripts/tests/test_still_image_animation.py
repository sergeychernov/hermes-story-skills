import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import still_image_animation as sia
from still_image_animation import (
    normalize_spec,
    visual_filter,
    resolve_font,
    _pan_crop_x_expr,
    _pan_progress_value,
    _zoompan_filter,
)


class SpecTests(unittest.TestCase):
    def test_normalizes_focus_and_defaults(self):
        spec = normalize_spec({
            "schema_version": 1,
            "source": "input.ppm",
            "output": "scene.mp4",
            "focus_x": 1.4,
            "focus_y": -0.2,
        })
        self.assertEqual(spec["focus_x"], 1.0)
        self.assertEqual(spec["focus_y"], 0.0)
        self.assertEqual(spec["motion"], "none")
        self.assertEqual(spec["fit_mode"], "crop")
        self.assertTrue(spec["fade_in"])
        self.assertTrue(spec["fade_out"])
        self.assertEqual(spec["pan_easing"], "focus_dwell")

    def test_rejects_unknown_pan_easing(self):
        with self.assertRaisesRegex(ValueError, "unsupported pan_easing"):
            normalize_spec({
                "schema_version": 1,
                "source": "input.ppm",
                "output": "scene.mp4",
                "pan_easing": "bounce",
            })

    def test_normalizes_fade_flags_independently(self):
        spec = normalize_spec({
            "schema_version": 1,
            "source": "input.ppm",
            "output": "scene.mp4",
            "fade_in": False,
            "fade_out": True,
        })
        self.assertFalse(spec["fade_in"])
        self.assertTrue(spec["fade_out"])

    def test_visual_filter_applies_fades_independently(self):
        both = visual_filter(0, 3.0, fit_mode="crop", motion="none")
        self.assertIn("fade=t=in:st=0:d=0.20", both)
        self.assertIn("fade=t=out:st=2.800:d=0.20", both)

        in_only = visual_filter(0, 3.0, fit_mode="crop", motion="none", fade_in=True, fade_out=False)
        self.assertIn("fade=t=in:st=0:d=0.20", in_only)
        self.assertNotIn("fade=t=out", in_only)

        out_only = visual_filter(0, 3.0, fit_mode="crop", motion="none", fade_in=False, fade_out=True)
        self.assertNotIn("fade=t=in", out_only)
        self.assertIn("fade=t=out:st=2.800:d=0.20", out_only)

        none = visual_filter(0, 3.0, fit_mode="crop", motion="none", fade_in=False, fade_out=False)
        self.assertNotIn("fade=t=", none)

    def test_rejects_unknown_motion(self):
        with self.assertRaisesRegex(ValueError, "unsupported motion"):
            normalize_spec({
                "schema_version": 1,
                "source": "input.ppm",
                "output": "scene.mp4",
                "motion": "orbit",
            })

    def test_rejects_path_escape(self):
        with self.assertRaisesRegex(ValueError, "path escapes root"):
            normalize_spec({
                "schema_version": 1,
                "source": "../input.ppm",
                "output": "scene.mp4",
            })

    def test_contain_rejects_pan_that_cannot_preserve_full_image(self):
        with self.assertRaisesRegex(ValueError, "contain.*pan"):
            normalize_spec({
                "schema_version": 1,
                "source": "input.ppm",
                "output": "scene.mp4",
                "fit_mode": "contain",
                "motion": "pan_right",
            })

    def test_pan_crop_x_expr_for_each_motion(self):
        self.assertIn("sin(2*PI*", _pan_crop_x_expr("pan_left", 0.6, 4.0))
        self.assertIn("clip(", _pan_crop_x_expr("pan_left", 0.6, 4.0))
        self.assertIn("clip(", _pan_crop_x_expr("pan_right", 0.5, 3.0))
        self.assertNotIn("0.360*", _pan_crop_x_expr("pan_right", 0.5, 3.0))
        self.assertEqual(_pan_crop_x_expr("none", 0.42, 3.0), "(iw-ow)*0.420")
        linear = _pan_crop_x_expr("pan_left", 0.6, 4.0, "linear")
        self.assertIn("t/4.000", linear)
        self.assertNotIn("sin(2*PI", linear)

    def test_focus_dwell_passes_through_focus_without_stopping(self):
        focus = 0.5
        self.assertAlmostEqual(_pan_progress_value(0.0, "focus_dwell", focus), 0.0, places=6)
        self.assertAlmostEqual(_pan_progress_value(1.0, "focus_dwell", focus), 1.0, places=6)
        self.assertAlmostEqual(_pan_progress_value(focus, "focus_dwell", focus), focus, places=6)
        progress_deriv = (
            _pan_progress_value(focus + 1e-4, "focus_dwell", focus)
            - _pan_progress_value(focus - 1e-4, "focus_dwell", focus)
        ) / 2e-4
        # Slower than linear (1.0), but never stopped (0.0).
        self.assertGreater(progress_deriv, 0.35)
        self.assertLess(progress_deriv, 0.55)
        values = [_pan_progress_value(i / 100, "focus_dwell", focus) for i in range(101)]
        self.assertTrue(all(values[i] <= values[i + 1] + 1e-9 for i in range(100)))
        edge_speed = (
            _pan_progress_value(0.02, "focus_dwell", focus)
            - _pan_progress_value(0.0, "focus_dwell", focus)
        ) / 0.02
        self.assertGreater(edge_speed, progress_deriv)

    def test_pan_uses_full_horizontal_range(self):
        expr = _pan_crop_x_expr("pan_right", 0.5, 3.0, "linear")
        self.assertIn("clip(t/3.000", expr)
        dwell = _pan_crop_x_expr("pan_right", 0.5, 3.0, "focus_dwell")
        self.assertIn("clip(", dwell)
        self.assertNotIn("0.360*", dwell)

    def test_zoompan_filter_only_for_zoom_motions(self):
        zoom_in = _zoompan_filter("zoom_in", 0.3, 0.48, 3.0, 30, 1080, 1920)
        self.assertIn("zoompan", zoom_in)
        self.assertIn("iw*0.300", zoom_in)
        self.assertIn("ih*0.480", zoom_in)
        self.assertEqual(_zoompan_filter("pan_right", 0.5, 0.5, 3.0, 30, 1080, 1920), "")

    def test_resolve_font_prefers_first_existing_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing.ttf"
            found = Path(td) / "found.ttf"
            found.write_bytes(b"font")
            with patch.object(sia, "FONT_CANDIDATES", (missing, found)):
                self.assertEqual(resolve_font(), found)

    def test_resolve_font_searches_configured_roots(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            font = root / "Arial Bold.ttf"
            font.write_bytes(b"font")
            with patch.object(sia, "FONT_CANDIDATES", ()), patch.object(
                sia, "FONT_SEARCH_ROOTS", (root,)
            ), patch.object(sia, "FONT_RELATIVE_NAMES", ("Arial Bold.ttf",)):
                self.assertEqual(resolve_font(), font)

    def test_title_renders_when_font_available(self):
        if not sia._ffmpeg_supports_drawtext():
            self.skipTest("ffmpeg drawtext filter unavailable")
        font = resolve_font()
        if font is None:
            self.skipTest("no system font available in this environment")
        with tempfile.TemporaryDirectory() as td:
            title = Path(td) / "title.txt"
            title.write_text("TITLE\n", encoding="utf-8")
            chain = visual_filter(0, 1.0, title, [], fit_mode="crop", motion="none")
            self.assertIn("drawtext", chain)
            self.assertIn("fontfile=", chain)

    def test_contain_filter_uses_full_foreground_over_background(self):
        chain = visual_filter(0, 1.0, fit_mode="contain", motion="none", width=270, height=480, fps=10)
        self.assertIn("force_original_aspect_ratio=decrease", chain)
        self.assertIn("overlay=(W-w)/2:(H-h)/2", chain)


class CliIntegrationTests(unittest.TestCase):
    def test_real_ffmpeg_render_reports_verified_moving_scene(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "input.ppm"
            width, height = 640, 480
            pixels = bytearray()
            for _y in range(height):
                for x in range(width):
                    pixels.extend((230, 20, 20) if x < width // 2 else (20, 20, 230))
            source.write_bytes(f"P6\n{width} {height}\n255\n".encode() + pixels)
            spec = {
                "schema_version": 1,
                "source": "input.ppm",
                "output": "scene.mp4",
                "width": 270,
                "height": 480,
                "fps": 10,
                "duration": 1.0,
                "fit_mode": "crop",
                "motion": "pan_right",
                "focus_x": 0.5,
                "focus_y": 0.5,
            }
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            cli = SCRIPTS / "animate_still.py"
            completed = subprocess.run(
                [sys.executable, str(cli), "--root", str(root), "--spec", str(spec_path)],
                check=True,
                text=True,
                capture_output=True,
            )
            report = json.loads(completed.stdout)
            output = root / "scene.mp4"
            self.assertTrue(output.is_file())
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["width"], 270)
            self.assertEqual(report["height"], 480)
            self.assertEqual(report["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertTrue(report["verification"]["decodable"])
            self.assertTrue(report["verification"]["motion_detected"])
            self.assertGreater(report["verification"]["sampled_frame_difference"], 1.0)

    def test_title_temp_file_does_not_follow_or_delete_predictable_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "root"
            root.mkdir()
            source = root / "input.ppm"
            source.write_bytes(b"P6\n2 2\n255\n" + bytes([255, 0, 0] * 4))
            outside = base / "outside.txt"
            outside.write_text("ORIGINAL\n", encoding="utf-8")
            trap = root / ".scene.title.txt"
            trap.symlink_to(outside)
            spec = {
                "schema_version": 1,
                "source": "input.ppm",
                "output": "scene.mp4",
                "width": 270,
                "height": 480,
                "fps": 10,
                "duration": 0.5,
                "fit_mode": "crop",
                "motion": "none",
                "title": "SHOULD NOT ESCAPE",
            }
            spec_path = root / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "animate_still.py"), "--root", str(root), "--spec", str(spec_path)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(outside.read_text(encoding="utf-8"), "ORIGINAL\n")
            self.assertTrue(trap.is_symlink())


if __name__ == "__main__":
    unittest.main()
