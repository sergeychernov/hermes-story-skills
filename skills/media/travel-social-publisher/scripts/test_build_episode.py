import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_episode import caption_specs, visual_filter, write_text


class VisualFilterTests(unittest.TestCase):
    def test_text_output_atomically_replaces_symlink_without_following_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outside = root / "outside.txt"
            outside.write_text("ORIGINAL\n", encoding="utf-8")
            output = root / "caption.txt"
            output.symlink_to(outside)
            write_text(output, "approved caption")
            self.assertEqual(outside.read_text(encoding="utf-8"), "ORIGINAL\n")
            self.assertFalse(output.is_symlink())
            self.assertEqual(output.read_text(encoding="utf-8"), "approved caption\n")

    def test_text_defaults_to_lower_fifth_without_touching_bottom_edge(self):
        with tempfile.TemporaryDirectory() as td:
            title = Path(td) / "title.txt"
            caption = Path(td) / "caption.txt"
            result = visual_filter(
                0, 3.0, title, [(caption, 0.25, 2.75)],
                fit_mode="crop", focus_x=0.5, motion="none",
            )
        # Global default: aim at 4/5, but preserve a bottom UI reserve.
        safe_y = "y=min(h*0.80-text_h/2\\,h-text_h-360)"
        self.assertEqual(result.count(safe_y), 2)
        self.assertIn("820-text_w", result)
        self.assertIn("between(t,0.250,2.750)", result)

    def test_template_does_not_override_global_safe_position(self):
        import json
        template = json.loads((Path(__file__).resolve().parent.parent / "templates" / "episode.json").read_text())
        self.assertNotIn("title_y", template)
        self.assertNotIn("caption_y", template)

    def test_landscape_pan_animates_crop_across_time(self):
        result = visual_filter(
            1, 4.0, None, [], fit_mode="crop", focus_x=0.6,
            motion="pan_left",
        )
        self.assertIn("crop=1080:1920", result)
        self.assertIn("t/4.000", result)
        self.assertIn("clip(0.780-0.360*t/4.000", result)
        self.assertNotIn("zoompan", result)

    def test_portrait_zoom_uses_high_resolution_cosine_easing(self):
        result = visual_filter(
            2, 3.0, None, [], fit_mode="crop", focus_x=0.5,
            motion="zoom_in",
        )
        self.assertIn("scale=2160:3840", result)
        self.assertIn("zoompan", result)
        self.assertIn("0.130", result)
        self.assertIn("cos(PI*", result)
        self.assertIn("s=1080x1920", result)
        self.assertNotIn("0.090", result)
        self.assertNotIn("0.035", result)

    def test_zoom_can_center_on_point_between_eyes(self):
        result = visual_filter(
            3, 3.0, None, [], fit_mode="contain", focus_x=0.3,
            focus_y=0.48, motion="zoom_in",
        )
        self.assertIn("iw*0.300", result)
        self.assertIn("ih*0.480", result)

    def test_caption_y_can_follow_a_real_device_ui_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            caption = Path(td) / "caption.txt"
            result = visual_filter(
                0, 3.0, None, [(caption, 0.0, 3.0)],
                fit_mode="crop", focus_x=0.5, motion="none",
                caption_y="h-520",
            )
        self.assertIn("y=h-520", result)
        self.assertNotIn("y=h-820", result)

    def test_title_y_can_avoid_a_scene_subject(self):
        with tempfile.TemporaryDirectory() as td:
            title = Path(td) / "title.txt"
            result = visual_filter(
                0, 3.0, title, [], fit_mode="contain", focus_x=0.5,
                motion="none", title_y="h-760",
            )
        self.assertIn("y=h-760", result)
        self.assertNotIn("y=h-980", result)

    def test_timed_caption_specs_preserve_punchline_at_end(self):
        specs = caption_specs({
            "captions": [
                {"text": "Куда ведёт эта тропинка?", "start": 0.4, "end": 3.2},
                {"text": "Кто-то нас поджидает…", "start": 5.4},
            ]
        }, 8.2)
        self.assertEqual(specs[0], ("Куда ведёт эта тропинка?", 0.4, 3.2))
        self.assertEqual(specs[1], ("Кто-то нас поджидает…", 5.4, 8.2))

    def test_caption_accepts_start_duration_and_text(self):
        specs = caption_specs({
            "captions": [{"text": "Марина идёт на джаз", "start": 0.35, "duration": 2.8}]
        }, 3.7)
        self.assertEqual(specs, [("Марина идёт на джаз", 0.35, 3.15)])

    def test_caption_rejects_end_and_duration_together(self):
        with self.assertRaises(SystemExit):
            caption_specs({
                "captions": [{"text": "Неоднозначно", "start": 0.0, "end": 2.0, "duration": 2.0}]
            }, 3.0)

    def test_legacy_caption_still_covers_the_clip(self):
        self.assertEqual(caption_specs({"caption": "Гусь"}, 2.5), [("Гусь", 0.0, 2.5)])


if __name__ == "__main__":
    unittest.main()
