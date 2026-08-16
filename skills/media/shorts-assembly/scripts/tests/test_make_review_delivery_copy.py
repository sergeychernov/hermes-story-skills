import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "make_review_delivery_copy.py"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg required")
class ReviewDeliveryCopyTests(unittest.TestCase):
    def test_creates_bounded_review_only_copy_with_locked_audio(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "master.mp4"
            output = root / "review.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=720x1280:rate=30:duration=1",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", str(source),
                ],
                check=True,
            )
            completed = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output),
                    "--width", "360", "--height", "640", "--max-mib", "2",
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            report = json.loads((Path(str(output) + ".report.json")).read_text())
            self.assertIn('"status": "ok"', completed.stdout)
            self.assertTrue(output.is_file())
            self.assertLessEqual(output.stat().st_size, 2 * 1024 * 1024)
            self.assertTrue(report["review_only"])
            self.assertFalse(report["publication_eligible"])
            self.assertEqual(report["video"]["width"], 360)
            self.assertEqual(report["video"]["height"], 640)
            self.assertEqual(report["video"]["frame_count"], report["source"]["frame_count"])
            self.assertTrue(report["audio"]["packet_payload_identity"])
            self.assertEqual(report["audio"]["operation"], "stream-copy")
            self.assertTrue(report["verification"]["full_video_decode"])
            self.assertTrue(report["verification"]["full_audio_decode"])


if __name__ == "__main__":
    unittest.main()
