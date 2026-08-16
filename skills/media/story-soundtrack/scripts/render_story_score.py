#!/usr/bin/env python3
"""Render deterministic procedural pentatonic story score stems."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from story_soundtrack_contract import (  # noqa: E402
    ContractError,
    SUPPORTED_INSTRUMENTS,
    load_and_validate_spec,
    load_timeline,
    resolve_layer_mapping,
    validate_timeline_agreement,
)
from story_soundtrack_lock import revision_lock  # noqa: E402

PITCH_COLLECTION = ("D", "E", "F#", "A", "B")
MIDI = {
    "D2": 38, "E2": 40, "F#2": 42, "A2": 45, "B2": 47,
    "D3": 50, "E3": 52, "F#3": 54, "A3": 57, "B3": 59,
    "D4": 62, "E4": 64, "F#4": 66, "A4": 69, "B4": 71,
    "D5": 74, "E5": 76, "F#5": 78, "A5": 81, "B5": 83, "D6": 86,
}
ROOTS = ("D2", "B2", "E2", "A2", "D2", "F#2", "B2", "A2",
         "D2", "E2", "F#2", "A2", "B2", "A2", "D2", "D2")
BASS_WALK = {
    "D2": ("D2", "A2", "D3", "A2"), "E2": ("E2", "B2", "E3", "B2"),
    "F#2": ("F#2", "B2", "F#3", "B2"), "A2": ("A2", "E3", "A3", "E3"),
    "B2": ("B2", "F#3", "B3", "F#3"),
}
CHORD_TONES = {
    "D2": ("D4", "A4", "E5"), "E2": ("E4", "B4", "F#5"),
    "F#2": ("F#4", "B4", "E5"), "A2": ("A3", "E4", "B4"),
    "B2": ("B3", "F#4", "D5"),
}
MOTIFS = (
    (("D5", 0.0, 0.90), ("E5", 1.0, 0.42), ("F#5", 1.5, 0.42), ("A5", 2.0, 0.88),
     ("F#5", 3.0, 0.80), ("E5", 4.0, 0.42), ("D5", 4.5, 1.25), ("B4", 6.0, 1.60)),
    (("A4", 0.0, 0.72), ("B4", 0.8, 0.72), ("D5", 1.6, 1.20), ("F#5", 3.0, 0.72),
     ("E5", 3.8, 0.72), ("D5", 4.6, 0.72), ("B4", 5.4, 0.72), ("D5", 6.2, 1.35)),
    (("D5", 0.0, 0.62), ("F#5", 0.7, 0.62), ("A5", 1.4, 1.05), ("B5", 2.7, 0.55),
     ("A5", 3.3, 0.55), ("F#5", 3.9, 0.90), ("E5", 5.0, 0.62), ("D5", 5.7, 1.50)),
    (("B4", 0.0, 0.70), ("D5", 0.8, 0.70), ("E5", 1.6, 0.70), ("F#5", 2.4, 1.05),
     ("A5", 3.7, 0.55), ("F#5", 4.4, 0.55), ("E5", 5.1, 0.70), ("D5", 5.9, 1.55)),
)


def freq(name: str) -> float:
    return 440.0 * 2.0 ** ((MIDI[name] - 69) / 12.0)


def envelope(n: int, sr: int, attack: float, release: float, decay: float = 0.0) -> np.ndarray:
    env = np.ones(n, dtype=np.float64)
    a = min(n, max(1, int(round(attack * sr))))
    r = min(n - a, max(1, int(round(release * sr))))
    env[:a] = 0.5 - 0.5 * np.cos(np.linspace(0.0, math.pi, a, endpoint=True))
    if decay > 0:
        env *= np.exp(-np.arange(n, dtype=np.float64) / sr * decay)
    if r:
        env[-r:] *= 0.5 + 0.5 * np.cos(np.linspace(0.0, math.pi, r, endpoint=True))
    return env


def pan_mono(x: np.ndarray, pan: float) -> np.ndarray:
    theta = (float(np.clip(pan, -1.0, 1.0)) + 1.0) * math.pi / 4.0
    return np.column_stack((x * math.cos(theta), x * math.sin(theta)))


def add_at(dst: np.ndarray, src: np.ndarray, start_seconds: float, sr: int) -> None:
    start = max(0, int(round(start_seconds * sr)))
    if start >= len(dst):
        return
    end = min(len(dst), start + len(src))
    dst[start:end] += src[: end - start]


def guzheng_pluck(note, duration, sr, rng, brightness=1.0, pan=0.0):
    n = max(2, int(round(duration * sr)))
    t = np.arange(n, dtype=np.float64) / sr
    phase = rng.uniform(0, 2 * math.pi, 9)
    mono = np.zeros(n, dtype=np.float64)
    f = freq(note)
    for h in range(1, 9):
        mono += brightness / (h ** 1.20) * np.sin(2 * math.pi * f * h * t + phase[h]) * np.exp(-t * (2.2 + 0.34 * h))
    pick = np.convolve(rng.normal(0.0, 1.0, n), np.ones(9) / 9.0, mode="same")
    mono += 0.11 * pick * np.exp(-t * 24.0)
    mono *= envelope(n, sr, 0.004, min(0.16, duration * 0.25), decay=0.35) * 0.20
    return pan_mono(mono, pan)


def bass_pluck(note, duration, sr, rng, pan=0.0):
    n = max(2, int(round(duration * sr)))
    t = np.arange(n, dtype=np.float64) / sr
    f = freq(note)
    mono = np.sin(2 * math.pi * f * t + rng.uniform(0, 0.2)) + 0.30 * np.sin(4 * math.pi * f * t) + 0.12 * np.sin(6 * math.pi * f * t)
    mono *= envelope(n, sr, 0.008, min(0.15, duration * 0.30), decay=2.3) * 0.18
    return pan_mono(mono, pan)


def dizi_note(note, duration, sr, rng, pan, ornament=False):
    n = max(2, int(round(duration * sr)))
    t = np.arange(n, dtype=np.float64) / sr
    f = freq(note)
    vib = 0.0042 * np.sin(2 * math.pi * 5.2 * t + rng.uniform(0, 2 * math.pi))
    if ornament:
        vib += 0.010 * np.exp(-t * 18.0) * np.sin(2 * math.pi * 8.0 * t)
    phase = 2 * math.pi * f * np.cumsum(1.0 + vib) / sr
    mono = np.sin(phase) + 0.29 * np.sin(2 * phase + 0.2) + 0.10 * np.sin(3 * phase + 0.45)
    breath = np.convolve(rng.normal(0.0, 1.0, n), np.ones(41) / 41.0, mode="same")
    mono = (0.17 * mono + 0.020 * breath) * envelope(n, sr, 0.055, min(0.18, duration * 0.30), decay=0.08)
    return pan_mono(mono, pan)


def low_drum(duration, sr, rng, pan=0.0):
    n = max(2, int(round(duration * sr)))
    t = np.arange(n, dtype=np.float64) / sr
    phase = 2 * math.pi * (48.0 * t + 28.0 / 16.0 * (1.0 - np.exp(-16.0 * t)))
    mono = np.sin(phase) * np.exp(-t * 9.0) + 0.025 * rng.normal(size=n) * np.exp(-t * 22.0)
    return pan_mono(0.22 * mono * envelope(n, sr, 0.002, 0.035), pan)


def woodblock(duration, sr, rng, pan):
    n = max(2, int(round(duration * sr)))
    t = np.arange(n, dtype=np.float64) / sr
    base = rng.uniform(980.0, 1160.0)
    mono = (np.sin(2 * math.pi * base * t) + 0.54 * np.sin(2 * math.pi * base * 1.62 * t + 0.3))
    return pan_mono(0.105 * mono * np.exp(-t * 31.0) * envelope(n, sr, 0.0015, 0.020), pan)


def shaker(duration, sr, rng, pan):
    n = max(2, int(round(duration * sr)))
    x = rng.normal(size=n)
    high = x - np.convolve(x, np.ones(17) / 17.0, mode="same")
    high *= np.exp(-np.arange(n) / sr * 34.0) * envelope(n, sr, 0.003, 0.025)
    return pan_mono(0.022 * high, pan)


def subtle_pad(note, duration, sr, pan):
    n = max(2, int(round(duration * sr)))
    t = np.arange(n, dtype=np.float64) / sr
    f = freq(note)
    mono = np.sin(2 * math.pi * f * t) + 0.40 * np.sin(4 * math.pi * f * t + 0.4)
    return pan_mono(mono * envelope(n, sr, 0.38, 0.55, decay=0.10) * 0.025, pan)


def short_reverb(x, sr, amount):
    out = x.copy()
    for delay, gain, swap in ((0.083, 0.22, True), (0.147, 0.15, False), (0.231, 0.09, True)):
        n = int(round(delay * sr))
        if n < len(x):
            out[n:] += gain * (x[:-n, ::-1] if swap else x[:-n])
    return out * (1.0 - amount * 0.18)


def fade_edges(x, sr, fade_in, fade_out):
    y = x.copy()
    ni = min(len(y), int(round(fade_in * sr)))
    no = min(len(y), int(round(fade_out * sr)))
    if ni:
        y[:ni] *= np.linspace(0.0, 1.0, ni)[:, None]
    if no:
        y[-no:] *= np.linspace(1.0, 0.0, no)[:, None]
    return y


def peak_normalize(x, target):
    peak = float(np.max(np.abs(x)))
    return x if peak == 0 else x * (target / peak)


def climax_time_seconds(validated: dict, fps: float) -> float:
    climax_id = validated["dramaturgy"]["climax_scene_id"]
    for scene in validated["scenes"]:
        if scene["id"] == climax_id:
            start, end = scene["frames"]
            mid_frame = (start + end) / 2.0
            return mid_frame / fps
    raise ContractError(f"climax scene not found: {climax_id}")


def render_stems(
    duration: float,
    sr: int,
    bpm: float,
    seed: int,
    climax_seconds: float,
    theme_energies: dict[str, float],
    scenes: list[dict],
    fps: float,
    *,
    instrumentation: list[str] | None = None,
    layer_mapping: dict[str, bool] | None = None,
) -> tuple[np.ndarray, np.ndarray, dict]:
    layers = layer_mapping or resolve_layer_mapping(instrumentation or ["guzheng", "dizi", "bass", "drums"])
    frames = int(round(duration * sr))
    rhythm = np.zeros((frames, 2), dtype=np.float64)
    melody = np.zeros_like(rhythm)
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    bar = beat * 4.0
    bars = max(1, int(duration // bar))
    climax_bar = max(0, min(bars - 1, int(climax_seconds // bar)))

    for b in range(bars):
        t0 = b * bar
        root = ROOTS[b % len(ROOTS)]
        dist = abs(b - climax_bar)
        if b < climax_bar:
            energy = 0.58 + 0.24 * (b / max(1, climax_bar))
        elif b == climax_bar:
            energy = 1.0
        else:
            energy = max(0.72, 1.0 - 0.08 * dist)
        if layers["guzheng_pad"]:
            add_at(rhythm, subtle_pad(CHORD_TONES[root][0], bar + 0.4, sr, -0.32), t0, sr)
            add_at(rhythm, subtle_pad(CHORD_TONES[root][1], bar + 0.4, sr, 0.32), t0, sr)
        if layers["bass"]:
            for k, bass_note in enumerate(BASS_WALK[root]):
                add_at(rhythm, energy * bass_pluck(bass_note, beat * 0.82, sr, rng, -0.08), t0 + k * beat, sr)
        if layers["guzheng_pluck"]:
            add_at(
                rhythm,
                energy * guzheng_pluck(CHORD_TONES[root][0], beat * 1.65, sr, rng, 0.92, -0.38),
                t0 + 0.05 * beat,
                sr,
            )
        if layers["guzheng_comping"]:
            for k, tone in enumerate(CHORD_TONES[root]):
                add_at(
                    rhythm,
                    energy * guzheng_pluck(tone, beat * 1.65, sr, rng, 0.88, (-0.38, 0.08, 0.42)[k]),
                    t0 + (0.05 if k == 0 else (1.5 + 0.18 * k) * beat),
                    sr,
                )
        for k in range(4):
            bt = t0 + k * beat
            if layers["low_drum"] and k in (0, 2):
                add_at(rhythm, energy * low_drum(0.36, sr, rng, -0.05), bt, sr)
            if layers["woodblock"] and k in (1, 3):
                add_at(rhythm, energy * woodblock(0.13, sr, rng, 0.28 if k == 1 else -0.28), bt, sr)
            if layers["shaker"] and b >= max(1, climax_bar // 4):
                add_at(rhythm, energy * shaker(0.10, sr, rng, -0.42 if k % 2 == 0 else 0.42), bt + beat * 0.5, sr)

    phrases = max(1, math.ceil(bars / 2))
    climax_phrase = max(0, min(phrases - 1, int((climax_seconds / (2 * bar)))))
    for phrase in range(phrases):
        motif = MOTIFS[phrase % len(MOTIFS)]
        phrase_start = phrase * 2 * bar
        if phrase < climax_phrase:
            level = 0.72 + 0.18 * (phrase / max(1, climax_phrase))
        elif phrase == climax_phrase:
            level = 1.0
        else:
            level = max(0.68, 1.0 - 0.10 * (phrase - climax_phrase))
        register_shift = phrase % 8 in (4, 5) or phrase == climax_phrase
        for idx, (note, beat_offset, beat_duration) in enumerate(motif):
            if not layers["dizi_melody"]:
                continue
            chosen = "D6" if register_shift and note == "D5" else note
            add_at(
                melody,
                level * dizi_note(
                    chosen,
                    beat_duration * beat,
                    sr,
                    rng,
                    -0.14 + 0.28 * ((idx + phrase) % 3) / 2.0,
                    ornament=idx in (0, 3) or phrase == climax_phrase,
                ),
                phrase_start + beat_offset * beat,
                sr,
            )

    rhythm = peak_normalize(fade_edges(short_reverb(rhythm, sr, 0.42), sr, 0.10, 1.20), 0.64)
    melody = peak_normalize(fade_edges(short_reverb(melody, sr, 0.58), sr, 0.12, 1.50), 0.56)
    for scene in scenes:
        s0, s1 = scene["frames"]
        start = int(round(s0 / fps * sr))
        end = min(len(melody), int(round(s1 / fps * sr)))
        if start >= end or not scene["theme_ids"]:
            continue
        scene_energy = max(theme_energies.get(tid, 0.7) for tid in scene["theme_ids"])
        melody[start:end] *= scene_energy
    climax_sample = int(round(climax_seconds * sr))
    meta = {
        "climax_seconds": climax_seconds,
        "climax_bar": climax_bar,
        "climax_phrase": climax_phrase,
        "climax_rhythm_rms": float(np.sqrt(np.mean(np.square(rhythm[max(0, climax_sample - sr // 2):climax_sample + sr // 2])))),
        "climax_melody_rms": float(np.sqrt(np.mean(np.square(melody[max(0, climax_sample - sr // 2):climax_sample + sr // 2])))),
        "resolved_layer_mapping": layers,
    }
    return rhythm, melody, meta


def write_pcm16(path: Path, audio: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.round(audio * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(sr)
        out.writeframes(pcm.tobytes())


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def metrics(x: np.ndarray) -> dict:
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(np.square(x))))
    tail_n = min(len(x), max(1, int(len(x) * 0.04)))
    return {"peak": peak, "rms": rms, "tail_rms": float(np.sqrt(np.mean(np.square(x[-tail_n:]))))}


def ffmpeg_version() -> str:
    try:
        return subprocess.run(
            ["ffmpeg", "-version"], text=True, capture_output=True, check=True
        ).stdout.splitlines()[0]
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unavailable"


def encode_preview_m4a(input_wav: Path, output_m4a: Path, exact_frames: int, sr: int) -> None:
    output_m4a.parent.mkdir(parents=True, exist_ok=True)
    temp = output_m4a.with_name(output_m4a.stem + ".tmp" + output_m4a.suffix)
    if temp.exists():
        temp.unlink()
    duration = exact_frames / sr
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-nostats",
        "-i", str(input_wav),
        "-af", f"alimiter=level=false,aresample={sr},asetpts=PTS-STARTPTS",
        "-ar", str(sr), "-ac", "2", "-c:a", "aac", "-b:a", "192k",
        "-t", f"{duration:.9f}",
        "-movflags", "+faststart",
        str(temp),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("ffmpeg encode failed: " + result.stderr)
    temp.replace(output_m4a)


def _refuse_if_approval_locked(validated: dict) -> None:
    paths = validated["resolved_paths"]
    if paths["approval_json"].exists() or paths["handoff_json"].exists():
        raise SystemExit(
            "refusing overwrite: approval_json or handoff_json exists; create a new revision"
        )


def render_score(validated: dict, overwrite: bool = False) -> dict:
    with revision_lock(validated):
        return _render_score_locked(validated, overwrite)


def _render_score_locked(validated: dict, overwrite: bool = False) -> dict:
    _refuse_if_approval_locked(validated)
    if validated["state"] != "PLANNED":
        raise SystemExit(
            f"render requires state PLANNED, got {validated['state']}"
        )
    root = validated["root"]
    timeline = load_timeline(root, validated["timeline"]["path"])
    try:
        validate_timeline_agreement(validated, timeline)
    except ContractError as exc:
        raise SystemExit(str(exc)) from exc
    sr = validated["timeline"]["sample_rate_hz"]
    fps = validated["timeline"]["fps"]
    frames = validated["timeline"]["exact_pcm_frames"]
    duration = frames / sr
    paths = validated["resolved_paths"]
    stem_keys = ("rhythm_wav", "melody_wav", "full_score_wav", "rhythm_preview_m4a", "full_preview_m4a", "report_json")
    existing = [str(p) for k, p in paths.items() if k in stem_keys and p.exists()]
    if existing and not overwrite:
        raise SystemExit("refusing to overwrite existing outputs: " + ", ".join(existing))

    theme_energies = {t["id"]: t["energy"] for t in validated["themes"]}
    climax_seconds = climax_time_seconds(validated, fps)
    rhythm, melody, climax_meta = render_stems(
        duration,
        sr,
        validated["style"]["bpm"],
        validated["style"]["seed"],
        climax_seconds,
        theme_energies,
        validated["scenes"],
        fps,
        instrumentation=validated["style"]["instrumentation"],
    )
    full = fade_edges(peak_normalize(np.tanh((0.88 * rhythm + 0.92 * melody) * 1.08), 0.78), sr, 0.08, 1.40)
    write_pcm16(paths["rhythm_wav"], rhythm, sr)
    write_pcm16(paths["melody_wav"], melody, sr)
    write_pcm16(paths["full_score_wav"], full, sr)
    encode_preview_m4a(paths["rhythm_wav"], paths["rhythm_preview_m4a"], frames, sr)
    encode_preview_m4a(paths["full_score_wav"], paths["full_preview_m4a"], frames, sr)

    report = {
        "schema_version": 1,
        "kind": "story_soundtrack_stems",
        "state": "STEMS_RENDERED",
        "story_id": validated["story_id"],
        "revision": validated["revision"],
        "preset": validated["style"]["preset"],
        "implementation_sha256": sha256_file(Path(__file__).resolve()),
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "ffmpeg_version": ffmpeg_version(),
        "timeline_path": validated["timeline"]["path"],
        "exact_pcm_frames": frames,
        "exact_pcm_duration_seconds": duration,
        "sample_rate_hz": sr,
        "channels": 2,
        "style": validated["style"],
        "instrumentation": validated["style"]["instrumentation"],
        "resolved_layer_mapping": climax_meta.get("resolved_layer_mapping"),
        "supported_instruments": sorted(SUPPORTED_INSTRUMENTS),
        "dramaturgy": validated["dramaturgy"],
        "climax_mapping": climax_meta,
        "rhythm_provenance": "one continuous global beat/phase timeline from t=0",
        "files": {},
        "routing": validated["scenes"],
    }
    for key, data, path_key in (
        ("rhythm", rhythm, "rhythm_wav"),
        ("melody", melody, "melody_wav"),
        ("full_score", full, "full_score_wav"),
    ):
        path = paths[path_key]
        report["files"][key] = {
            "path": str(path.relative_to(root)),
            "sha256": sha256_file(path),
            **metrics(data),
        }
    for key, path_key in (("rhythm_preview", "rhythm_preview_m4a"), ("full_preview", "full_preview_m4a")):
        path = paths[path_key]
        report["files"][key] = {
            "path": str(path.relative_to(root)),
            "sha256": sha256_file(path),
        }
    paths["report_json"].parent.mkdir(parents=True, exist_ok=True)
    paths["report_json"].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    try:
        validated = load_and_validate_spec(args.root.resolve(), args.spec.resolve())
        report = render_score(validated, overwrite=args.overwrite)
    except ContractError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps({
        "status": "ok",
        "state": report["state"],
        "report": validated["outputs"]["report_json"],
        "exact_pcm_frames": report["exact_pcm_frames"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
