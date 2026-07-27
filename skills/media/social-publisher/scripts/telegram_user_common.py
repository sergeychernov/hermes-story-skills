#!/usr/bin/env python3
"""Shared safe configuration for Telegram's MTProto user clients."""
from __future__ import annotations
import os
from urllib.parse import unquote, urlparse


def telethon_proxy():
    raw = (os.environ.get('TELEGRAM_PROXY') or os.environ.get('ALL_PROXY') or '').strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme.lower() not in {'socks5', 'socks5h'}:
        raise SystemExit('Telegram user client requires a SOCKS5 proxy URL')
    if not parsed.hostname or not parsed.port:
        raise SystemExit('Invalid SOCKS5 proxy URL: host and port are required')
    username = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password else None
    return ('socks5', parsed.hostname, parsed.port, True, username, password)


def story_slots(response) -> int | None:
    value = getattr(response, 'count_remains', None)
    return int(value) if value is not None else None


def proxy_label() -> str:
    proxy = telethon_proxy()
    return 'direct' if proxy is None else f'socks5://{proxy[1]}:{proxy[2]}'
