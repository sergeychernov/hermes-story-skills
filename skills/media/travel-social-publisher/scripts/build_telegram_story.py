#!/usr/bin/env python3
"""Transcode the approved vertical master into Telegram Story format.

Output follows Telegram Stories upload constraints validated against stories.sendStory:
720x1280 H.264/AAC in streamable MP4, keyframes every second, duration <=60s,
size <=30 MiB. HEVC/H.265 is rejected by MTProto with MEDIA_FILE_INVALID.
Publication and privacy are separate approval-gated concerns.
"""
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

MAX_SECONDS=60.0
MAX_BYTES=30*1024*1024

def probe(path: Path) -> dict:
    p=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],check=True,text=True,capture_output=True)
    return json.loads(p.stdout)

def run(cmd: list[str]) -> None:
    print('+',' '.join(map(str,cmd)))
    subprocess.run(cmd,check=True)

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument('episode_dir',type=Path); ap.add_argument('--input',default='reel-short.mp4'); ap.add_argument('--output',default='telegram-story.mp4')
    a=ap.parse_args(); d=a.episode_dir.expanduser().resolve(); src=d/a.input; out=d/a.output
    if not src.is_file(): raise SystemExit(f'missing vertical master: {src}')
    meta=probe(src); duration=float(meta.get('format',{}).get('duration') or 0)
    if duration <= 0 or duration > MAX_SECONDS: raise SystemExit(f'Telegram Story duration must be 0-60s; got {duration:.3f}s')
    run(['ffmpeg','-y','-v','error','-i',str(src),'-vf','scale=720:1280:flags=lanczos,fps=30','-c:v','libx264','-preset','fast','-crf','23','-profile:v','high','-level:v','4.1','-g','30','-keyint_min','30','-sc_threshold','0','-tag:v','avc1','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-ar','48000','-movflags','+faststart',str(out)])
    result=probe(out); streams=result.get('streams',[]); v=next((s for s in streams if s.get('codec_type')=='video'),{}); au=next((s for s in streams if s.get('codec_type')=='audio'),{})
    errors=[]; actual_duration=float(result.get('format',{}).get('duration') or 0); size=out.stat().st_size
    if (v.get('width'),v.get('height')) != (720,1280): errors.append(f"dimensions {v.get('width')}x{v.get('height')}")
    if v.get('codec_name') != 'h264': errors.append(f"video codec {v.get('codec_name')}")
    if au.get('codec_name') != 'aac': errors.append(f"audio codec {au.get('codec_name')}")
    if actual_duration > MAX_SECONDS: errors.append(f'duration {actual_duration:.3f}s')
    if size > MAX_BYTES: errors.append(f'size {size} bytes exceeds 30 MiB')
    try:
        for start in (0, max(0, actual_duration/2-0.5), max(0, actual_duration-2)):
            subprocess.run(['ffmpeg','-v','error','-ss',f'{start:.3f}','-i',str(out),'-t','1','-f','null','-'],check=True,capture_output=True)
    except subprocess.CalledProcessError as e: errors.append('sample decode failed: '+e.stderr.decode('utf-8','ignore')[-500:])
    report={'ok':not errors,'errors':errors,'video':str(out),'duration':actual_duration,'bytes':size,'width':v.get('width'),'height':v.get('height'),'video_codec':v.get('codec_name'),'audio_codec':au.get('codec_name'),'privacy':'set-at-publish-time'}
    (d/'telegram-story-build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if report['ok'] else 1)
if __name__=='__main__': main()
