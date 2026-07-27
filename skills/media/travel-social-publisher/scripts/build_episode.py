#!/usr/bin/env python3
"""Render one Instagram Reel / YouTube Short package from an episode manifest."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, textwrap
from pathlib import Path

# Compatibility seam: the episode builder delegates still-scene motion and
# typography to the independently testable still-image-animation skill.
STILL_ANIMATION_SCRIPTS = Path(__file__).resolve().parents[2] / 'still-image-animation' / 'scripts'
if str(STILL_ANIMATION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(STILL_ANIMATION_SCRIPTS))
from still_image_animation import visual_filter

W, H, FPS = 1080, 1920, 30
# Aim the center of every text block at 4/5 of frame height, while reserving
# 360 px for bottom platform chrome. The x expression also reserves the right rail.
LOWER_FIFTH_Y = 'min(h*0.80-text_h/2\\,h-text_h-360)'
TITLE_Y = LOWER_FIFTH_Y
CAPTION_Y = LOWER_FIFTH_Y
CAPTION_WRAP = 22
FONT_CANDIDATES = [
    Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
    Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf'),
]

def run(cmd: list[str]) -> None:
    print('+', ' '.join(str(x) for x in cmd))
    subprocess.run(cmd, check=True)

def probe(path: Path) -> dict:
    p = subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)], check=True, text=True, capture_output=True)
    return json.loads(p.stdout)

def safe_path(root: Path, rel: str) -> Path:
    p = (root / rel).resolve()
    if p != root and root not in p.parents:
        raise SystemExit(f'path escapes archive root: {rel}')
    if not p.is_file():
        raise SystemExit(f'missing input: {p}')
    return p

def still_export(source: Path, out: Path, width: int, height: int, title_file: Path | None = None) -> None:
    vf = (f'split=2[bg][fg];[bg]scale={width}:{height}:force_original_aspect_ratio=increase,'
          f'crop={width}:{height},boxblur=24:12[bg2];[fg]scale={width}:{height}:'
          f'force_original_aspect_ratio=decrease[fg2];[bg2][fg2]overlay=(W-w)/2:(H-h)/2')
    if title_file:
        font = next((p for p in FONT_CANDIDATES if p.exists()), None)
        if font:
            escaped = str(title_file).replace("'", "\\'").replace(':', '\\:')
            fnt = str(font).replace(':', '\\:')
            vf += (f",drawtext=fontfile='{fnt}':textfile='{escaped}':fontcolor=white:fontsize=64:"
                   "line_spacing=12:x=(w-text_w)/2:y=h-420:box=1:boxcolor=black@0.55:boxborderw=28")
    out.parent.mkdir(parents=True, exist_ok=True)
    run(['ffmpeg','-y','-v','error','-i',str(source),'-vf',vf,'-frames:v','1','-q:v','2',str(out)])

def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode='w', encoding='utf-8', dir=path.parent,
        prefix=f'.{path.name}.', suffix='.tmp', delete=False,
    ) as handle:
        handle.write(value.rstrip() + '\n')
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def caption_specs(clip: dict, duration: float) -> list[tuple[str, float, float]]:
    raw = clip.get('captions')
    if raw is None:
        if not clip.get('caption'):
            return []
        raw = [{'text': clip['caption']}]
    specs: list[tuple[str, float, float]] = []
    for item in raw:
        if isinstance(item, str):
            item = {'text': item}
        text = str(item.get('text') or '').strip()
        start = max(0.0, float(item.get('start', 0.0)))
        if 'end' in item and 'duration' in item:
            raise SystemExit(f'caption cannot have both end and duration: {item!r}')
        if 'duration' in item:
            display_duration = float(item['duration'])
            if display_duration <= 0:
                raise SystemExit(f'invalid caption duration: {item!r}')
            end = min(duration, start + display_duration)
        else:
            end = min(duration, float(item.get('end', duration)))
        if not text or end <= start:
            raise SystemExit(f'invalid caption interval: {item!r}')
        specs.append((text, start, end))
    return specs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--archive', required=True, type=Path)
    ap.add_argument('--manifest', required=True, type=Path)
    args = ap.parse_args()
    root = args.archive.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    m = json.loads(manifest_path.read_text(encoding='utf-8'))
    clips = m.get('clips') or []
    if not clips:
        raise SystemExit('manifest has no clips')
    outdir = (root / m['output_dir']).resolve()
    if outdir != root and root not in outdir.parents:
        raise SystemExit('output_dir escapes archive root')
    outdir.mkdir(parents=True, exist_ok=True)
    title_file = outdir / '.title.txt'
    wrapped_title = '\n'.join(textwrap.wrap(m['title'], width=22, break_long_words=False, break_on_hyphens=False))
    write_text(title_file, wrapped_title)

    inputs: list[str] = []
    filters: list[str] = []
    concat_refs: list[str] = []
    selected: list[Path] = []
    total = 0.0
    for i, clip in enumerate(clips):
        source = safe_path(root, clip['path'])
        selected.append(source)
        kind = clip.get('type', 'image')
        if kind == 'video':
            meta = probe(source)
            natural = float(meta.get('format', {}).get('duration') or 0)
            duration = float(clip.get('duration') or natural)
            if duration <= 0:
                raise SystemExit(f'cannot determine duration: {source}')
            inputs += ['-i', str(source)]
            has_audio = any(s.get('codec_type') == 'audio' for s in meta.get('streams', []))
            if has_audio:
                filters.append(f'[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=duration={duration:.3f},apad,atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[a{i}]')
            else:
                filters.append(f'anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[a{i}]')
        elif kind == 'image':
            duration = float(clip.get('duration', 3.0))
            inputs += ['-loop','1','-t',f'{duration:.3f}','-i',str(source)]
            filters.append(f'anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[a{i}]')
        else:
            raise SystemExit(f'unsupported clip type: {kind}')
        caption_overlays: list[tuple[Path, float, float]] = []
        for j, (caption, start, end) in enumerate(caption_specs(clip, duration)):
            caption_file = outdir / f'.caption-{i:02d}-{j:02d}.txt'
            wrapped = '\n'.join(textwrap.wrap(caption, width=CAPTION_WRAP,
                                              break_long_words=False, break_on_hyphens=False))
            write_text(caption_file, wrapped)
            caption_overlays.append((caption_file, start, end))
        fit_mode = clip.get('fit_mode', 'contain')
        if fit_mode not in {'contain', 'crop'}:
            raise SystemExit(f'unsupported fit_mode: {fit_mode}')
        motion = clip.get('motion', 'none') if kind == 'image' else 'none'
        if motion not in {'none', 'pan_left', 'pan_right', 'zoom_in', 'zoom_out'}:
            raise SystemExit(f'unsupported motion: {motion}')
        filters.append(visual_filter(
            i, duration, title_file if i == 0 else None, caption_overlays,
            fit_mode=fit_mode, focus_x=float(clip.get('focus_x', 0.5)),
            focus_y=float(clip.get('focus_y', 0.5)), motion=motion,
            title_y=str(clip.get('title_y', m.get('title_y', TITLE_Y))),
            caption_y=str(clip.get('caption_y', m.get('caption_y', CAPTION_Y))),
        ))
        concat_refs.append(f'[v{i}][a{i}]')
        total += duration

    filters.append(''.join(concat_refs) + f'concat=n={len(clips)}:v=1:a=1[outv][outa]')
    output = outdir / 'reel-short.mp4'
    cmd = ['ffmpeg','-y','-v','error',*inputs,'-filter_complex',';'.join(filters),
           '-map','[outv]','-map','[outa]','-c:v','libx264','-preset','veryfast','-crf','20',
           '-pix_fmt','yuv420p','-r',str(FPS),'-c:a','aac','-b:a','160k','-movflags','+faststart',str(output)]
    run(cmd)

    story_cfg = m.get('telegram_story') or {}
    story_output = outdir / 'telegram-story.mp4'
    if story_cfg.get('enabled', True) is not False:
        run([
            sys.executable,
            str(Path(__file__).with_name('build_telegram_story.py')),
            str(outdir),
        ])
    else:
        # Do not let a derivative from an earlier revision masquerade as current.
        story_output.unlink(missing_ok=True)

    cover_source = safe_path(root, m.get('cover_source') or clips[0]['path'])
    still_export(cover_source, outdir / 'cover.jpg', W, H, title_file)
    carousel = outdir / 'carousel'
    carousel.mkdir(exist_ok=True)
    # Rerenders may contain fewer stills; remove stale numbered exports first.
    for stale in carousel.glob('*.jpg'):
        stale.unlink()
    for n, clip in enumerate([c for c in clips if c.get('type','image') == 'image'], 1):
        still_export(safe_path(root, clip['path']), carousel / f'{n:02d}.jpg', 1080, 1350)

    write_text(outdir / 'instagram-caption.txt', m['instagram_caption'])
    write_text(outdir / 'youtube-title.txt', m['youtube_title'])
    write_text(outdir / 'youtube-description.txt', m['youtube_description'])
    result = {
        'status': 'prepared', 'title': m['title'], 'duration_seconds_expected': round(total, 3),
        'video': str(output), 'cover': str(outdir / 'cover.jpg'),
        'telegram_story': str(story_output) if story_output.is_file() else None,
        'carousel_count': len(list(carousel.glob('*.jpg'))),
        'selected_inputs': [str(p) for p in selected],
    }
    (outdir / 'build-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    title_file.unlink(missing_ok=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
