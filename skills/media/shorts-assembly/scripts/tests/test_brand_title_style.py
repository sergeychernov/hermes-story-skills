import hashlib
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from brand_title_style import STYLE_VERSION, drawtext_filter, style_manifest


class BrandTitleStyleTests(unittest.TestCase):
    def test_canonical_1080_style(self):
        s = style_manifest(1080)
        self.assertEqual(s["style_version"], STYLE_VERSION)
        self.assertEqual(s["font_weight"], "Bold")
        self.assertTrue(str(s["font_file"]).endswith("-Bold.ttf"))
        self.assertEqual(s["font_size"], 54)
        self.assertEqual(s["line_spacing"], 12)
        self.assertEqual(s["box_color"], "black@0.406")
        self.assertEqual(s["box_border"], 24)
        self.assertEqual(s["safe_box_bottom_ratio"], 0.72)

    def test_scales_at_720(self):
        s = style_manifest(720)
        self.assertEqual(s["font_size"], 36)
        self.assertEqual(s["line_spacing"], 8)
        self.assertEqual(s["box_border"], 16)

    def test_drawtext_uses_canonical_values(self):
        chain, _ = drawtext_filter(Path("/work/title.txt"), 1080)
        self.assertIn("DejaVuSans-Bold.ttf", chain)
        self.assertIn("fontsize=54", chain)
        self.assertIn("line_spacing=12", chain)
        self.assertIn("boxcolor=black@0.406", chain)
        self.assertIn("boxborderw=24", chain)


if __name__ == "__main__":
    unittest.main()
