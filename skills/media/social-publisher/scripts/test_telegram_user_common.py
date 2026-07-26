#!/usr/bin/env python3
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


class TelegramProxyTests(unittest.TestCase):
    def setUp(self):
        self.old = {k: os.environ.get(k) for k in ('TELEGRAM_PROXY', 'ALL_PROXY')}
        os.environ.pop('TELEGRAM_PROXY', None)
        os.environ.pop('ALL_PROXY', None)

    def tearDown(self):
        for key, value in self.old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_uses_telegram_proxy_for_telethon(self):
        os.environ['TELEGRAM_PROXY'] = 'socks5://xray.xray.svc.cluster.local:10808'
        from telegram_user_common import telethon_proxy

        self.assertEqual(
            telethon_proxy(),
            ('socks5', 'xray.xray.svc.cluster.local', 10808, True, None, None),
        )

    def test_falls_back_to_all_proxy(self):
        os.environ['ALL_PROXY'] = 'socks5h://proxy.internal:1080'
        from telegram_user_common import telethon_proxy

        self.assertEqual(
            telethon_proxy(),
            ('socks5', 'proxy.internal', 1080, True, None, None),
        )

    def test_reads_remaining_story_slots(self):
        from telegram_user_common import story_slots

        class Response:
            count_remains = 7

        self.assertEqual(story_slots(Response()), 7)

    def test_rejects_unsupported_proxy_scheme(self):
        os.environ['TELEGRAM_PROXY'] = 'http://proxy.internal:8080'
        from telegram_user_common import telethon_proxy

        with self.assertRaisesRegex(SystemExit, 'SOCKS5'):
            telethon_proxy()


if __name__ == '__main__':
    unittest.main()
