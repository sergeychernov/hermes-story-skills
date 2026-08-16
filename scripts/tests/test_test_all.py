#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/test_all.sh"
SOUNDTRACK = "skills/media/story-soundtrack/scripts/tests"


class AggregateRunnerTests(unittest.TestCase):
    def run_with_fake_python(self, *, soundtrack: bool) -> str:
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "python"
            fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake.chmod(0o755)
            env = os.environ.copy()
            env["PYTHON"] = str(fake)
            if soundtrack:
                env["RUN_STORY_SOUNDTRACK_TESTS"] = "1"
            else:
                env.pop("RUN_STORY_SOUNDTRACK_TESTS", None)
            result = subprocess.run(
                ["bash", str(RUNNER)], cwd=ROOT, env=env,
                text=True, capture_output=True, check=True,
            )
            return result.stdout

    def test_story_soundtrack_is_skipped_by_default(self):
        output = self.run_with_fake_python(soundtrack=False)
        self.assertNotIn(f"=== {SOUNDTRACK} ===", output)
        self.assertIn(f"SKIP {SOUNDTRACK}", output)

    def test_story_soundtrack_can_be_enabled_explicitly(self):
        output = self.run_with_fake_python(soundtrack=True)
        self.assertIn(f"=== {SOUNDTRACK} ===", output)
        self.assertNotIn(f"SKIP {SOUNDTRACK}", output)


if __name__ == "__main__":
    unittest.main()
