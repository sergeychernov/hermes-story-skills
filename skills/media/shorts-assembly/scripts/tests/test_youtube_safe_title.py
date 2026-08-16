import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "youtube_safe_title.py"
spec = importlib.util.spec_from_file_location("youtube_safe_title", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


class YouTubeSafeTitleTests(unittest.TestCase):
    def test_policy_pins_box_above_current_shorts_bottom_controls(self):
        expr = module.ffmpeg_expressions("lower_fifth")
        self.assertEqual(expr["bottom_free"], 0.28)
        self.assertEqual(expr["y"], "h*0.72-text_h-24")

    def test_policy_reserves_right_twenty_percent(self):
        expr = module.ffmpeg_expressions("lower_fifth")
        self.assertEqual(expr["right_free"], 0.20)
        self.assertIn("w*0.80", expr["x"])

    def test_1080x1920_safe_rectangle(self):
        self.assertEqual(module.safe_rect(1080, 1920), {
            "x": 86,
            "y": 0,
            "width": 778,
            "height": 1382,
        })

    def test_bottom_position_is_rejected(self):
        with self.assertRaises(ValueError):
            module.ffmpeg_expressions("bottom")


if __name__ == "__main__":
    unittest.main()
