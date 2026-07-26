#!/usr/bin/env python3
"""Build deterministic melody/rhythm routing from episode scene metadata.

FFmpeg input convention for the generated filter script:
  0:a = original episode audio, 1:a = generated melody stem,
  2:a = generated rhythm stem. Output label: [outa].
"""
import argparse
import json
from pathlib import Path


def _merge(intervals, eps=1e-6):
    merged = []
    for start, end in intervals:
        start, end = float(start), float(end)
        if end <= start:
            continue
        if merged and start <= merged[-1][1] + eps:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [[round(a, 6), round(b, 6)] for a, b in merged]


def build_routing(manifest):
    clips = manifest.get('clips') or []
    if not clips:
        raise ValueError('manifest clips are required')
    melody, rhythm, muted, modes = [], [], [], []
    cursor = 0.0
    for index, clip in enumerate(clips, 1):
        duration = float(clip.get('duration', 0))
        if duration <= 0:
            raise ValueError(f'clip {index} has invalid duration')
        end = cursor + duration
        kind = clip.get('type')
        content_type = clip.get('content_type')
        if content_type == 'music':
            if kind != 'video':
                raise ValueError(f'clip {index}: content_type=music requires type=video')
            muted.append([cursor, end])
            modes.append('original-only')
        elif content_type == 'nosound':
            if kind != 'video':
                raise ValueError(f'clip {index}: content_type=nosound requires type=video')
            melody.append([cursor, end])
            rhythm.append([cursor, end])
            modes.append('melody+rhythm')
        elif kind == 'image':
            melody.append([cursor, end])
            rhythm.append([cursor, end])
            modes.append('melody+rhythm')
        else:
            rhythm.append([cursor, end])
            modes.append('rhythm')
        cursor = end
    return {
        'duration': round(cursor, 6),
        'melody_intervals': _merge(melody),
        'rhythm_intervals': _merge(rhythm),
        'muted_intervals': _merge(muted),
        'scene_modes': modes,
    }


def _envelope(intervals, fade):
    if not intervals:
        return '0'
    windows = []
    for start, end in intervals:
        width = end - start
        ramp = min(float(fade), width / 2)
        if ramp <= 0:
            continue
        a, b, c, d = start, start + ramp, end - ramp, end
        windows.append(
            f"if(between(t,{a:.6f},{b:.6f}),(t-{a:.6f})/{ramp:.6f},"
            f"if(between(t,{b:.6f},{c:.6f}),1,"
            f"if(between(t,{c:.6f},{d:.6f}),({d:.6f}-t)/{ramp:.6f},0)))"
        )
    return f"min(1,{'+'.join(windows)})" if windows else '0'


def build_filter(routing, gain=0.13, fade=0.08):
    duration = float(routing['duration'])
    melody = _envelope(routing['melody_intervals'], fade)
    rhythm = _envelope(routing['rhythm_intervals'], fade)
    return (
        f"[0:a]asetpts=N/SR/TB,atrim=duration={duration:.6f},asetpts=N/SR/TB[original];\n"
        f"[1:a]asetpts=N/SR/TB,atrim=duration={duration:.6f},asetpts=N/SR/TB,"
        f"volume='{float(gain):.6f}*({melody})':eval=frame[melody];\n"
        f"[2:a]asetpts=N/SR/TB,atrim=duration={duration:.6f},asetpts=N/SR/TB,"
        f"volume='{float(gain):.6f}*({rhythm})':eval=frame[rhythm];\n"
        "[original][melody][rhythm]amix=inputs=3:duration=first:normalize=0,"
        f"alimiter=limit=0.95,atrim=duration={duration:.6f}[outa]\n"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--routing-json', required=True, type=Path)
    parser.add_argument('--filter-script', required=True, type=Path)
    parser.add_argument('--gain', type=float, default=0.13)
    parser.add_argument('--fade', type=float, default=0.08)
    args = parser.parse_args()
    if args.gain < 0:
        raise SystemExit('--gain must be non-negative')
    if args.fade <= 0:
        raise SystemExit('--fade must be positive')
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    routing = build_routing(manifest)
    args.routing_json.parent.mkdir(parents=True, exist_ok=True)
    args.filter_script.parent.mkdir(parents=True, exist_ok=True)
    args.routing_json.write_text(json.dumps(routing, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    args.filter_script.write_text(build_filter(routing, args.gain, args.fade), encoding='utf-8')
    print(json.dumps({'routing': str(args.routing_json), 'filter_script': str(args.filter_script), **routing}, ensure_ascii=False))


if __name__ == '__main__':
    main()
