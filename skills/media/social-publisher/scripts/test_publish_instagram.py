import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class InstagramGateTests(unittest.TestCase):
    def test_cli_refuses_without_explicit_approval_before_credentials_or_network(self):
        with tempfile.TemporaryDirectory() as directory:
            caption = Path(directory) / "caption.txt"
            caption.write_text("approved caption", encoding="utf-8")
            video = Path(directory) / "video.mp4"
            video.write_bytes(b"video")
            verification = Path(directory) / "verification.json"
            verification.write_text("{}", encoding="utf-8")
            env = os.environ.copy()
            env.pop("INSTAGRAM_ACCESS_TOKEN", None)
            env.pop("INSTAGRAM_USER_ID", None)
            script = Path(__file__).with_name("publish_instagram.py")
            completed = subprocess.run([
                sys.executable,
                str(script),
                "--video", str(video),
                "--video-url", "https://example.invalid/video.mp4",
                "--verification", str(verification),
                "--caption-file", str(caption),
            ], text=True, capture_output=True, env=env)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("explicit --approved", completed.stderr)


if __name__ == "__main__":
    unittest.main()
