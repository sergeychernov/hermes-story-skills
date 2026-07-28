#!/usr/bin/env python3
"""Discover and manage Telegram channels approved for Story publication."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

try:
    from telethon import TelegramClient, functions, types
except ModuleNotFoundError:
    TelegramClient = functions = types = None

from publish_telegram_story import BASE, credentials
from telegram_channel_registry import load_registry, remove_channel, upsert_channel
from telegram_user_common import story_slots, telethon_proxy


def chat_descriptor(chat) -> dict:
    return {
        "channel_id": int(chat.id),
        "title": str(getattr(chat, "title", "") or ""),
        "username": getattr(chat, "username", None),
    }


def match_chat(chats: list, selector: str):
    normalized = selector.strip().lstrip("@").lower()
    matches = []
    for chat in chats:
        username = (getattr(chat, "username", None) or "").lower()
        title = (getattr(chat, "title", None) or "").lower()
        if normalized in {str(chat.id), username, title}:
            matches.append(chat)
    if not matches:
        raise SystemExit(f"Channel {selector!r} is not available in stories.getChatsToSend")
    if len(matches) > 1:
        raise SystemExit(f"Channel selector {selector!r} is ambiguous; use its numeric ID or @username")
    return matches[0]


async def connected_client():
    if TelegramClient is None or functions is None:
        raise SystemExit("Telethon is required; use the configured social-publisher runtime")
    api_id, api_hash = credentials()
    client = TelegramClient(str(BASE / "user"), api_id, api_hash, proxy=telethon_proxy())
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise SystemExit("Telegram user session is not authorized; run setup_telegram_user.py")
    return client


async def available_chats(client) -> list:
    result = await client(functions.stories.GetChatsToSendRequest())
    return list(getattr(result, "chats", []) or [])


async def command_list(args) -> None:
    registry = load_registry()
    configured = {item["channel_id"]: item for item in registry["channels"]}
    client = await connected_client()
    try:
        me = await client.get_me()
        rows = [{
            "key": "self",
            "label": "Личный аккаунт",
            "target_type": "self",
            "user_id": me.id,
            "username": me.username,
            "available": True,
        }]
        for chat in await available_chats(client):
            info = chat_descriptor(chat)
            saved = configured.get(info["channel_id"])
            if saved or args.all:
                rows.append({
                    "key": saved["key"] if saved else None,
                    "label": saved["label"] if saved else info["title"],
                    "target_type": "channel",
                    **info,
                    "registered": bool(saved),
                    "available": True,
                })
        unavailable_ids = set(configured) - {row.get("channel_id") for row in rows}
        for channel_id in sorted(unavailable_ids):
            saved = configured[channel_id]
            rows.append({**saved, "target_type": "channel", "available": False})
        print(json.dumps({"ok": True, "channels": rows}, ensure_ascii=False, indent=2))
    finally:
        await client.disconnect()


async def command_add(args) -> None:
    client = await connected_client()
    try:
        chat = match_chat(await available_chats(client), args.selector)
        peer = await client.get_input_entity(chat)
        allowed = await client(functions.stories.CanSendStoryRequest(peer=peer))
        info = chat_descriptor(chat)
        entry = upsert_channel(
            key=args.key,
            channel_id=info["channel_id"],
            label=args.label or info["title"],
            username=info["username"],
        )
        print(json.dumps({
            "ok": True,
            "added": entry,
            "available_story_slots": story_slots(allowed),
            "registry": str(BASE / "channels.json"),
        }, ensure_ascii=False, indent=2))
    finally:
        await client.disconnect()


def command_remove(args) -> None:
    removed = remove_channel(args.key)
    print(json.dumps({"ok": True, "removed": removed, "key": args.key}, ensure_ascii=False))


def cli() -> None:
    parser = argparse.ArgumentParser(description="Manage Telegram Story publication channels")
    sub = parser.add_subparsers(dest="command", required=True)
    list_parser = sub.add_parser("list", help="List selectable registered channels")
    list_parser.add_argument("--all", action="store_true", help="Also show eligible channels not yet registered")
    add_parser = sub.add_parser("add", help="Register an eligible channel")
    add_parser.add_argument("key", help="Stable publication key, e.g. travel")
    add_parser.add_argument("selector", help="Numeric channel ID, @username, or exact title")
    add_parser.add_argument("--label", help="Human-friendly choice label")
    remove_parser = sub.add_parser("remove", help="Remove a channel from the publication choices")
    remove_parser.add_argument("key")
    args = parser.parse_args()
    if args.command == "remove":
        command_remove(args)
    elif args.command == "list":
        asyncio.run(command_list(args))
    else:
        asyncio.run(command_add(args))


if __name__ == "__main__":
    cli()
