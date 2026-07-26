#!/usr/bin/env python3
"""Verify a prepared travel package and write verification.json."""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path

def sha256(p: Path) -> str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def probe(p: Path) -> dict:
    r=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)],capture_output=True,text=True,check=True)
    return json.loads(r.stdout)

def decode_check(path: Path, label: str, errors: list[str]) -> None:
    try: subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],check=True,capture_output=True)
    except subprocess.CalledProcessError as e: errors.append(label+' decode failed: '+e.stderr.decode('utf-8','ignore')[-500:])

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument('episode_dir',type=Path); a=ap.parse_args()
    d=a.episode_dir.expanduser().resolve(); errors=[]
    video=d/'reel-short.mp4'; story=d/'telegram-story.mp4'; cover=d/'cover.jpg'; carousel=sorted((d/'carousel').glob('*.jpg')) if (d/'carousel').is_dir() else []
    for p in [video,story,cover,d/'instagram-caption.txt',d/'youtube-title.txt',d/'youtube-description.txt']:
        if not p.is_file() or p.stat().st_size==0: errors.append(f'missing or empty: {p.name}')
    video_meta={}; story_meta={}
    if video.is_file():
        video_meta=probe(video); streams=video_meta.get('streams',[]); vv=next((x for x in streams if x.get('codec_type')=='video'),{}); va=next((x for x in streams if x.get('codec_type')=='audio'),{})
        if (vv.get('width'),vv.get('height'))!=(1080,1920): errors.append(f"video dimensions are {vv.get('width')}x{vv.get('height')}")
        if vv.get('codec_name')!='h264': errors.append(f"video codec is {vv.get('codec_name')}")
        if va.get('codec_name')!='aac': errors.append(f"audio codec is {va.get('codec_name')}")
        decode_check(video,'video',errors)
    if story.is_file():
        story_meta=probe(story); streams=story_meta.get('streams',[]); sv=next((x for x in streams if x.get('codec_type')=='video'),{}); sa=next((x for x in streams if x.get('codec_type')=='audio'),{})
        duration=float(story_meta.get('format',{}).get('duration') or 0)
        if (sv.get('width'),sv.get('height'))!=(720,1280): errors.append(f"Telegram Story dimensions are {sv.get('width')}x{sv.get('height')}")
        if sv.get('codec_name')!='h264': errors.append(f"Telegram Story video codec is {sv.get('codec_name')}")
        if sa.get('codec_name')!='aac': errors.append(f"Telegram Story audio codec is {sa.get('codec_name')}")
        if duration<=0 or duration>60: errors.append(f'Telegram Story duration is {duration:.3f}s')
        if story.stat().st_size>30*1024*1024: errors.append(f'Telegram Story exceeds 30 MiB: {story.stat().st_size} bytes')
        decode_check(story,'Telegram Story',errors)
    if not carousel: errors.append('carousel is empty')
    out={'ok':not errors,'errors':errors,'video':{'path':str(video),'sha256':sha256(video) if video.is_file() else None,'bytes':video.stat().st_size if video.is_file() else 0,'duration':video_meta.get('format',{}).get('duration')},'telegram_story':{'path':str(story),'sha256':sha256(story) if story.is_file() else None,'bytes':story.stat().st_size if story.is_file() else 0,'duration':story_meta.get('format',{}).get('duration'),'privacy':'explicit-at-publish-time'},'cover':str(cover),'carousel_count':len(carousel)}
    (d/'verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2)); raise SystemExit(0 if out['ok'] else 1)
if __name__=='__main__': main()
