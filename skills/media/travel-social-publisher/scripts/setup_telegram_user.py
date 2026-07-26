#!/usr/bin/env python3
"""One-time Telegram user authorization for Story publishing.

Run interactively on the trusted host. Secrets are read from the terminal and
stored with mode 0600 outside episode directories.
"""
from __future__ import annotations
import asyncio, getpass, json, os, tempfile
from pathlib import Path
from telethon import TelegramClient, functions, types
from telegram_user_common import proxy_label, story_slots, telethon_proxy

BASE=Path(os.environ.get('TELEGRAM_USER_HOME','~/.hermes/telegram-user')).expanduser().resolve()
CREDS=BASE/'credentials.env'; SESSION=BASE/'user'

def load_credentials() -> tuple[int,str]:
    if CREDS.is_file():
        vals={}
        for line in CREDS.read_text(encoding='utf-8').splitlines():
            if '=' in line:
                k,v=line.split('=',1); vals[k.strip()]=v.strip()
        try: return int(vals['TELEGRAM_API_ID']),vals['TELEGRAM_API_HASH']
        except (KeyError,ValueError): raise SystemExit(f'Invalid credentials file: {CREDS}')
    print('Create an API application first at https://my.telegram.org/apps')
    api_id=int(input('Telegram API ID: ').strip())
    api_hash=getpass.getpass('Telegram API hash (hidden): ').strip()
    if not api_hash: raise SystemExit('API hash is empty')
    BASE.mkdir(parents=True,exist_ok=True); BASE.chmod(0o700)
    fd,tmp=tempfile.mkstemp(prefix='.credentials.',dir=BASE,text=True)
    try:
        os.write(fd,f'TELEGRAM_API_ID={api_id}\nTELEGRAM_API_HASH={api_hash}\n'.encode())
        os.close(fd); os.chmod(tmp,0o600); os.replace(tmp,CREDS)
    except Exception:
        try: os.close(fd)
        except OSError: pass
        Path(tmp).unlink(missing_ok=True); raise
    return api_id,api_hash

async def main() -> None:
    BASE.mkdir(parents=True,exist_ok=True); BASE.chmod(0o700)
    api_id,api_hash=load_credentials()
    print(f'Connection route: {proxy_label()}')
    client=TelegramClient(str(SESSION),api_id,api_hash,proxy=telethon_proxy())
    await client.connect()
    try:
        if not await client.is_user_authorized():
            phone=input('Phone in international format (not stored): ').strip()
            sent=await client.send_code_request(phone)
            code=getpass.getpass('Telegram login code (hidden): ').strip()
            try:
                await client.sign_in(phone=phone,code=code,phone_code_hash=sent.phone_code_hash)
            except Exception as exc:
                from telethon.errors import SessionPasswordNeededError
                if not isinstance(exc,SessionPasswordNeededError): raise
                password=getpass.getpass('Telegram 2FA password (hidden): ')
                await client.sign_in(password=password)
        me=await client.get_me()
        allowed=await client(functions.stories.CanSendStoryRequest(peer=types.InputPeerSelf()))
        count=story_slots(allowed)
        print(json.dumps({'ok':True,'authorized':True,'user_id':me.id,'username':me.username,'can_send_story':bool(allowed),'available_story_slots':count},ensure_ascii=False))
    finally:
        await client.disconnect()
        for p in BASE.glob('user.session*'):
            try: p.chmod(0o600)
            except OSError: pass

if __name__=='__main__': asyncio.run(main())
