#!/usr/bin/env python3
"""Publish a verified Telegram Story from the authorized personal account."""
from __future__ import annotations
import argparse, asyncio, hashlib, json, os, random, subprocess
from datetime import datetime, timezone
from pathlib import Path

try:
    from telethon import TelegramClient, functions, types
except ModuleNotFoundError:
    TelegramClient = None
    functions = None

    class DocumentAttributeFilename:
        def __init__(self, file_name: str):
            self.file_name = file_name

    class DocumentAttributeVideo:
        def __init__(self, duration: int, w: int, h: int, supports_streaming: bool):
            self.duration = duration
            self.w = w
            self.h = h
            self.supports_streaming = supports_streaming
            self.video_codec = None

    class InputPrivacyValueAllowContacts:
        pass

    class InputPrivacyValueAllowAll:
        pass

    class _Types:
        DocumentAttributeFilename = DocumentAttributeFilename
        DocumentAttributeVideo = DocumentAttributeVideo
        InputPrivacyValueAllowContacts = InputPrivacyValueAllowContacts
        InputPrivacyValueAllowAll = InputPrivacyValueAllowAll

    types = _Types()

from telegram_user_common import story_slots, telethon_proxy

BASE=Path(os.environ.get('TELEGRAM_USER_HOME','~/.hermes/telegram-user')).expanduser().resolve()

def sha256(p: Path) -> str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def credentials() -> tuple[int,str]:
    p=BASE/'credentials.env'; vals={}
    if not p.is_file(): raise SystemExit(f'Missing credentials: run setup_telegram_user.py first ({p})')
    for line in p.read_text(encoding='utf-8').splitlines():
        if '=' in line:
            k,v=line.split('=',1); vals[k.strip()]=v.strip()
    try: return int(vals['TELEGRAM_API_ID']),vals['TELEGRAM_API_HASH']
    except (KeyError,ValueError): raise SystemExit(f'Invalid credentials file: {p}')

def probe(p: Path) -> tuple[float,int,int,str,str]:
    r=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)],check=True,text=True,capture_output=True)
    m=json.loads(r.stdout); ss=m.get('streams',[]); v=next((x for x in ss if x.get('codec_type')=='video'),{}); a=next((x for x in ss if x.get('codec_type')=='audio'),{})
    return float(m.get('format',{}).get('duration') or 0),int(v.get('width') or 0),int(v.get('height') or 0),str(v.get('codec_name')),str(a.get('codec_name'))

def video_attributes(duration: float, width: int, height: int, filename: str):
    return [
        types.DocumentAttributeFilename(file_name=filename),
        types.DocumentAttributeVideo(
            duration=int(duration),
            w=width,
            h=height,
            supports_streaming=True,
        ),
    ]


async def upload_story_file(client: TelegramClient, path: Path):
    """Upload Story media as InputFile, never InputFileBig (official clients force small parts)."""
    part_size=512*1024
    file_size=path.stat().st_size
    part_count=(file_size+part_size-1)//part_size
    file_id=random.randrange(-(2**63),2**63)
    digest=hashlib.md5()
    with path.open('rb') as source:
        for part_index in range(part_count):
            chunk=source.read(part_size)
            if not chunk:
                raise RuntimeError(f'Unexpected EOF at Story part {part_index}/{part_count}')
            digest.update(chunk)
            saved=await client(functions.upload.SaveFilePartRequest(file_id,part_index,chunk))
            if not saved:
                raise RuntimeError(f'Telegram rejected Story file part {part_index}/{part_count}')
    return types.InputFile(id=file_id,parts=part_count,name=path.name,md5_checksum=digest.hexdigest())


def story_id_from(updates) -> int|None:
    for u in getattr(updates,'updates',[]) or []:
        if isinstance(u,types.UpdateStoryID): return u.id
        if isinstance(u,types.UpdateStory): return getattr(u.story,'id',None)
    return None


def privacy_rules_for_audience(audience: str):
    if audience == 'contacts':
        return [types.InputPrivacyValueAllowContacts()]
    if audience == 'everyone':
        return [types.InputPrivacyValueAllowAll()]
    if audience == 'link':
        return None
    raise ValueError(f'Unsupported audience: {audience}')


async def publish(a) -> None:
    d=a.episode_dir.expanduser().resolve(); media=d/'telegram-story.mp4'; verification=d/'verification.json'
    if not a.approved: raise SystemExit('Refusing publication: --approved is required after explicit user command «публикуй».')
    privacy_rules=privacy_rules_for_audience(a.audience)
    if privacy_rules is None:
        print(json.dumps({'ok':True,'platform':'telegram_story','published':False,'skipped':True,'audience':'link','reason':'Telegram Stories do not support link-only visibility'},ensure_ascii=False))
        return
    if not media.is_file() or not verification.is_file(): raise SystemExit('telegram-story.mp4 or verification.json is missing')
    report=json.loads(verification.read_text(encoding='utf-8')); expected=(report.get('telegram_story') or {}).get('sha256'); actual=sha256(media)
    if not report.get('ok'): raise SystemExit('verification.json is not green')
    if not expected or expected!=actual: raise SystemExit('telegram-story.mp4 hash does not match verification.json')
    duration,w,h,vcodec,acodec=probe(media)
    if (w,h)!=(720,1280) or vcodec!='h264' or acodec!='aac' or not 0<duration<=60 or media.stat().st_size>30*1024*1024:
        raise SystemExit(f'Invalid Story media: {w}x{h} {vcodec}/{acodec}, {duration:.3f}s, {media.stat().st_size} bytes')
    caption=''
    if a.caption_file:
        caption=a.caption_file.expanduser().read_text(encoding='utf-8').strip()
    if TelegramClient is None or functions is None:
        raise SystemExit('Telethon is required for Telegram publication; install the optional dependency first')
    api_id,api_hash=credentials(); client=TelegramClient(str(BASE/'user'),api_id,api_hash,proxy=telethon_proxy())
    await client.connect()
    try:
        if not await client.is_user_authorized(): raise SystemExit('Telegram user session is not authorized; run setup_telegram_user.py')
        me=await client.get_me(); allowed=await client(functions.stories.CanSendStoryRequest(peer=types.InputPeerSelf()))
        slots=story_slots(allowed)
        if slots is not None and slots<=0: raise SystemExit('Telegram reports no available Story slots')
        uploaded=await upload_story_file(client,media)
        input_media=types.InputMediaUploadedDocument(
            file=uploaded,
            mime_type='video/mp4',
            attributes=video_attributes(duration,720,1280,media.name),
            nosound_video=True,
        )
        result=await client(functions.stories.SendStoryRequest(peer=types.InputPeerSelf(),media=input_media,privacy_rules=privacy_rules,caption=caption or None,random_id=random.randrange(-(2**63),2**63),period=a.period,noforwards=a.protect))
        sid=story_id_from(result)
        if sid is None: raise SystemExit('Telegram accepted the request but returned no Story ID; inspect current stories before retrying')
        record={'platform':'telegram_story','timestamp':datetime.now(timezone.utc).isoformat(),'story_id':sid,'user_id':me.id,'username':me.username,'sha256':actual,'audience':a.audience,'privacy':a.audience,'period_seconds':a.period,'protected':a.protect}
        (d/'telegram-story-publish.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'ok':True,**record},ensure_ascii=False))
    finally: await client.disconnect()

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument('episode_dir',type=Path); ap.add_argument('--caption-file',type=Path); ap.add_argument('--audience',choices=['contacts','everyone','link'],required=True,help='contacts=own contacts, everyone=public Story, link=skip Telegram (link-only Stories are unsupported)'); ap.add_argument('--period',type=int,choices=[21600,43200,86400,172800],default=86400); ap.add_argument('--protect',action='store_true'); ap.add_argument('--approved',action='store_true')
    a=ap.parse_args(); asyncio.run(publish(a))
if __name__=='__main__': main()
