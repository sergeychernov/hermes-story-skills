#!/usr/bin/env python3
"""Build a verified multi-part Telegram Story sequence from rendered scene segments.

Manifest shape:
  telegram_story:
    max_duration_seconds: 60
    sequence:
      target_duration_seconds: 30
      clip_groups: [[1,2,3], [4,5], [6,7,8]]

By default the script expects canonical scene files at <episode>/segments-v3/00.mp4,
01.mp4, ... and writes telegram-story-01.mp4, telegram-story-02.mp4, ... .
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def run(cmd):
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('episode_dir', type=Path)
    ap.add_argument('--manifest', type=Path)
    ap.add_argument('--segments-dir', type=Path)
    ap.add_argument('--prefix', default='telegram-story')
    args = ap.parse_args()
    ep = args.episode_dir.resolve()
    manifest_path = args.manifest or ep / 'manifest.json'
    segments_dir = args.segments_dir or ep / 'segments-v3'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    config = manifest.get('telegram_story') or {}
    sequence = config.get('sequence') or {}
    groups = sequence.get('clip_groups') or []
    clips = manifest.get('clips') or []
    limit = float(config.get('max_duration_seconds', 60))
    if not groups:
        raise SystemExit('telegram_story.sequence.clip_groups is required')

    flattened = []
    for number, raw in enumerate(groups, 1):
        indices = [int(i) for i in raw]
        if not indices or len(indices) != len(set(indices)):
            raise SystemExit(f'part {number} is empty or contains duplicates: {indices!r}')
        if any(i < 1 or i > len(clips) for i in indices) or indices != sorted(indices):
            raise SystemExit(f'part {number} has invalid/non-canonical order: {indices!r}')
        flattened.extend(indices)
    expected_coverage = list(range(1, len(clips) + 1))
    if flattened != expected_coverage:
        raise SystemExit(f'sequence must cover every canonical scene exactly once; got {flattened!r}')

    records = []
    for number, raw in enumerate(groups, 1):
        indices = [int(i) for i in raw]
        expected = sum(float(clips[i - 1]['duration']) for i in indices)
        if expected > limit:
            raise SystemExit(f'part {number} is {expected:.3f}s, over {limit:.3f}s')
        segment_paths = [segments_dir / f'{i - 1:02d}.mp4' for i in indices]
        missing = [str(p) for p in segment_paths if not p.is_file()]
        if missing:
            raise SystemExit(f'part {number} missing segments: {missing}')
        concat = ep / f'.{args.prefix}-{number:02d}.concat.txt'
        concat.write_text(''.join(f"file \'{p}\'\n" for p in segment_paths), encoding='utf-8')
        tmp = ep / f'{args.prefix}-{number:02d}.tmp.mp4'
        out = ep / f'{args.prefix}-{number:02d}.mp4'
        tmp.unlink(missing_ok=True)
        run([
            'ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat),
            '-vf', 'scale=720:1280:flags=lanczos,fps=30',
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-maxrate', '3M', '-bufsize', '6M',
            '-profile:v', 'high', '-level:v', '4.1', '-g', '30', '-keyint_min', '30', '-sc_threshold', '0',
            '-tag:v', 'avc1', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-movflags', '+faststart', str(tmp)
        ])
        probe = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration,size', '-of', 'json', str(tmp)
        ], check=True, capture_output=True, text=True)
        fmt = json.loads(probe.stdout)['format']
        actual, size = float(fmt['duration']), int(fmt['size'])
        if actual > limit + 0.05 or size > 30 * 1024 * 1024:
            tmp.unlink(missing_ok=True)
            raise SystemExit(f'part {number} violates Story limits: {actual:.3f}s, {size} bytes')
        run(['ffmpeg', '-v', 'error', '-i', str(tmp), '-f', 'null', '-'])
        tmp.replace(out)
        record = {
            'part': number,
            'output': out.name,
            'clip_indices': indices,
            'expected_duration_seconds': round(expected, 3),
            'actual_duration_seconds': round(actual, 3),
            'bytes': size,
            'sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
        }
        records.append(record)
        concat.unlink(missing_ok=True)
        print(json.dumps(record, ensure_ascii=False), flush=True)

    report = {
        'source': 'canonical rendered scene segments',
        'target_duration_seconds': float(sequence.get('target_duration_seconds', 30)),
        'max_duration_seconds': limit,
        'parts': records,
    }
    (ep / 'telegram-sequence-build.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )


if __name__ == '__main__':
    main()
