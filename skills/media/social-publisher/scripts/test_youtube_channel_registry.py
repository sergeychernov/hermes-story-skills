#!/usr/bin/env python3
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from youtube_channel_registry import (
    credentials_for_channel,
    load_registry,
    remove_channel,
    upsert_channel,
)


class YouTubeChannelRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.registry = self.root / "channels.json"
        self.credentials = self.root / "credentials.env"
        self.credentials.write_text(
            "YOUTUBE_CLIENT_ID=id\nYOUTUBE_CLIENT_SECRET=secret\nYOUTUBE_REFRESH_TOKEN=refresh\n",
            encoding="utf-8",
        )
        self.credentials.chmod(0o600)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_registry_is_target_specific_and_mode_600(self):
        upsert_channel("travel", "Travel", "UC123", "Travel title", self.credentials, self.registry)
        channel, credentials = credentials_for_channel("travel", self.registry)
        self.assertEqual(channel["channel_id"], "UC123")
        self.assertEqual(credentials["YOUTUBE_REFRESH_TOKEN"], "refresh")
        self.assertEqual(stat.S_IMODE(self.registry.stat().st_mode), 0o600)
        self.assertTrue(remove_channel("travel", self.registry))

    def test_rejects_insecure_credentials_file(self):
        upsert_channel("travel", "Travel", "UC123", "Travel title", self.credentials, self.registry)
        self.credentials.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "group/others"):
            credentials_for_channel("travel", self.registry)

    def test_manager_help(self):
        script = Path(__file__).resolve().parent / "manage_youtube_channels.py"
        result = subprocess.run([sys.executable, str(script), "--help"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("YouTube publication channels", result.stdout)

    def test_hermes_home_is_used_without_double_nesting(self):
        from youtube_channel_registry import youtube_home

        previous_home = os.environ.get("HERMES_HOME")
        previous_youtube = os.environ.pop("YOUTUBE_HOME", None)
        os.environ["HERMES_HOME"] = "/srv/hermes"
        try:
            self.assertEqual(youtube_home(), Path("/srv/hermes/youtube"))
        finally:
            if previous_home is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous_home
            if previous_youtube is not None:
                os.environ["YOUTUBE_HOME"] = previous_youtube

    def test_legacy_environment_credentials_remain_supported(self):
        from publish_youtube import legacy_environment_credentials

        env = {
            "YOUTUBE_CLIENT_ID": "id",
            "YOUTUBE_CLIENT_SECRET": "secret",
            "YOUTUBE_REFRESH_TOKEN": "refresh",
        }
        self.assertEqual(legacy_environment_credentials(env), env)


if __name__ == "__main__":
    unittest.main()
