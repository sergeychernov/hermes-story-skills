#!/usr/bin/env python3
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from telegram_channel_registry import (
    load_registry,
    registered_channel,
    remove_channel,
    upsert_channel,
)


class TelegramChannelRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "channels.json"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_add_update_remove_and_permissions(self):
        upsert_channel("travel", 123, "Travel", "@travel", self.path)
        self.assertEqual(registered_channel("travel", self.path)["username"], "travel")
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

        upsert_channel("travel", 123, "Travel Stories", "travel", self.path)
        data = load_registry(self.path)
        self.assertEqual(len(data["channels"]), 1)
        self.assertEqual(data["channels"][0]["label"], "Travel Stories")

        self.assertTrue(remove_channel("travel", self.path))
        self.assertFalse(remove_channel("travel", self.path))

    def test_channel_ids_are_unique_and_self_is_reserved(self):
        upsert_channel("first", 123, "First", path=self.path)
        upsert_channel("second", 123, "Second", path=self.path)
        self.assertEqual([item["key"] for item in load_registry(self.path)["channels"]], ["second"])
        with self.assertRaisesRegex(ValueError, "cannot be 'self'"):
            upsert_channel("self", 999, "Bad", path=self.path)

    def test_invalid_registry_is_rejected(self):
        self.path.write_text(json.dumps({"version": 1, "channels": [{"key": "BAD", "channel_id": 1}]}))
        with self.assertRaisesRegex(ValueError, "Invalid channel key"):
            load_registry(self.path)

    def test_manager_help_does_not_require_telethon(self):
        script = Path(__file__).resolve().parent / "manage_telegram_channels.py"
        result = subprocess.run([sys.executable, str(script), "--help"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Telegram Story publication channels", result.stdout)


if __name__ == "__main__":
    unittest.main()
