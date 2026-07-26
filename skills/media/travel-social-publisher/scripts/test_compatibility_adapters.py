import subprocess
import sys
import unittest
from pathlib import Path


class CompatibilityAdapterTests(unittest.TestCase):
    def test_telegram_setup_help_runs_through_async_aware_adapter(self):
        script = Path(__file__).resolve().parent / "setup_telegram_user.py"
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Telegram", result.stdout)


if __name__ == "__main__":
    unittest.main()
