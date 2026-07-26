import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from still_image_animation import normalize_spec, visual_filter


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
