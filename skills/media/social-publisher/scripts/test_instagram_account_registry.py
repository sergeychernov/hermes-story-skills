#!/usr/bin/env python3
import os
import multiprocessing
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from instagram_account_registry import (
    credentials_for_account,
    instagram_home,
    load_registry,
    read_credentials_file,
    remove_account,
    upsert_account,
)


def concurrent_upsert(start, registry: str, credentials: str, index: int) -> None:
    start.wait()
    upsert_account(
        f"account-{index}", f"Account {index}", str(10000 + index),
        f"user_{index}", Path(credentials), Path(registry),
    )


class InstagramAccountRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.registry = self.root / "accounts.json"
        self.credentials = self.root / "credentials.env"
        self.credentials.write_text(
            "INSTAGRAM_ACCESS_TOKEN=token\nINSTAGRAM_USER_ID=12345\nINSTAGRAM_API_VERSION=v24.0\n",
            encoding="utf-8",
        )
        self.credentials.chmod(0o600)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_registry_is_target_specific_and_mode_600(self):
        upsert_account("travel", "Travel", "12345", "travel_frog", self.credentials, self.registry)
        account, credentials = credentials_for_account("travel", self.registry)
        self.assertEqual(account["user_id"], "12345")
        self.assertEqual(account["username"], "travel_frog")
        self.assertEqual(credentials["INSTAGRAM_ACCESS_TOKEN"], "token")
        self.assertEqual(stat.S_IMODE(self.registry.stat().st_mode), 0o600)
        self.assertTrue(remove_account("travel", self.registry))

    def test_rejects_insecure_credentials_file(self):
        upsert_account("travel", "Travel", "12345", "travel_frog", self.credentials, self.registry)
        self.credentials.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "group/others"):
            credentials_for_account("travel", self.registry)

    def test_concurrent_upserts_do_not_lose_successful_updates(self):
        context = multiprocessing.get_context("fork")
        start = context.Event()
        processes = [
            context.Process(
                target=concurrent_upsert,
                args=(start, str(self.registry), str(self.credentials), index),
            )
            for index in range(16)
        ]
        for process in processes:
            process.start()
        start.set()
        for process in processes:
            process.join(timeout=10)
            self.assertEqual(process.exitcode, 0)
        self.assertEqual(len(load_registry(self.registry)["accounts"]), 16)

    def test_rejects_duplicate_user_ids(self):
        upsert_account("one", "One", "12345", "one_user", self.credentials, self.registry)
        with self.assertRaisesRegex(ValueError, "Duplicate Instagram user ID"):
            upsert_account("two", "Two", "12345", "two_user", self.credentials, self.registry)

    def test_manager_list_never_prints_token_or_path(self):
        upsert_account("travel", "Travel", "12345", "travel_frog", self.credentials, self.registry)
        script = Path(__file__).resolve().parent / "manage_instagram_accounts.py"
        env = os.environ.copy()
        env["INSTAGRAM_HOME"] = str(self.root)
        result = subprocess.run(
            [sys.executable, str(script), "list"],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("token", result.stdout.lower())
        self.assertNotIn(str(self.credentials), result.stdout)
        self.assertNotIn("credentials_file", result.stdout)

    def test_manager_help(self):
        script = Path(__file__).resolve().parent / "manage_instagram_accounts.py"
        result = subprocess.run([sys.executable, str(script), "--help"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Instagram publication accounts", result.stdout)

    def test_hermes_home_is_used_without_double_nesting(self):
        previous_home = os.environ.get("HERMES_HOME")
        previous_instagram = os.environ.pop("INSTAGRAM_HOME", None)
        os.environ["HERMES_HOME"] = "/srv/hermes"
        try:
            self.assertEqual(instagram_home(), Path("/srv/hermes/instagram"))
        finally:
            if previous_home is None:
                os.environ.pop("HERMES_HOME", None)
            else:
                os.environ["HERMES_HOME"] = previous_home
            if previous_instagram is not None:
                os.environ["INSTAGRAM_HOME"] = previous_instagram

    def test_read_credentials_requires_user_id_and_token(self):
        bad = self.root / "bad.env"
        bad.write_text("INSTAGRAM_ACCESS_TOKEN=only\n", encoding="utf-8")
        bad.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "Missing Instagram credentials"):
            read_credentials_file(bad)

    def test_add_verifies_identity_before_registering(self):
        import manage_instagram_accounts as manager

        original = manager.fetch_instagram_identity
        manager.fetch_instagram_identity = lambda token, version, opener=None: {
            "id": "99999",
            "username": "wrong",
        }
        try:
            with self.assertRaisesRegex(ValueError, "does not match"):
                manager.command_add(mock.Mock(
                    key="travel",
                    label=None,
                    credentials_file=self.credentials,
                ))
        finally:
            manager.fetch_instagram_identity = original
        self.assertEqual(load_registry(self.registry)["accounts"], [])


if __name__ == "__main__":
    unittest.main()
