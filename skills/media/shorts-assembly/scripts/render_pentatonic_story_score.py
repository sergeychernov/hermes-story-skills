#!/usr/bin/env python3
"""Render deterministic pentatonic story score stems from a JSON spec."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import wave
from pathlib import Path

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - exercised by CLI setup gate
    raise SystemExit(
        "NumPy is required. Create a venv with: uv venv --python 3.11 .venv-story-music "
        "&& uv pip install --python .venv-story-music/bin/python numpy"
    ) from exc

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
    n = max(2, int(round(duration * sr))); t = np.arange(n, dtype=np.float64) / sr
    phase = rng.uniform(0, 2 * math.pi, 9); mono = np.zeros(n, dtype=np.float64); f = freq(note)
    for h in range(1, 9):
        mono += brightness / (h ** 1.20) * np.sin(2 * math.pi * f * h * t + phase[h]) * np.exp(-t * (2.2 + 0.34 * h))
    pick = np.convolve(rng.normal(0.0, 1.0, n), np.ones(9) / 9.0, mode="same")
    mono += 0.11 * pick * np.exp(-t * 24.0)
    mono *= envelope(n, sr, 0.004, min(0.16, duration * 0.25), decay=0.35) * 0.20
    return pan_mono(mono, pan)


def bass_pluck(note, duration, sr, rng, pan=0.0):
    n = max(2, int(round(duration * sr))); t = np.arange(n, dtype=np.float64) / sr; f = freq(note)
    mono = np.sin(2 * math.pi * f * t + rng.uniform(0, 0.2)) + 0.30 * np.sin(4 * math.pi * f * t) + 0.12 * np.sin(6 * math.pi * f * t)
    mono *= envelope(n, sr, 0.008, min(0.15, duration * 0.30), decay=2.3) * 0.18
    return pan_mono(mono, pan)


def dizi_note(note, duration, sr, rng, pan, ornament=False):
    n = max(2, int(round(duration * sr))); t = np.arange(n, dtype=np.float64) / sr; f = freq(note)
    vib = 0.0042 * np.sin(2 * math.pi * 5.2 * t + rng.uniform(0, 2 * math.pi))
    if ornament:
        vib += 0.010 * np.exp(-t * 18.0) * np.sin(2 * math.pi * 8.0 * t)
    phase = 2 * math.pi * f * np.cumsum(1.0 + vib) / sr
    mono = np.sin(phase) + 0.29 * np.sin(2 * phase + 0.2) + 0.10 * np.sin(3 * phase + 0.45)
    breath = np.convolve(rng.normal(0.0, 1.0, n), np.ones(41) / 41.0, mode="same")
    mono = (0.17 * mono + 0.020 * breath) * envelope(n, sr, 0.055, min(0.18, duration * 0.30), decay=0.08)
    return pan_mono(mono, pan)


def low_drum(duration, sr, rng, pan=0.0):
    n = max(2, int(round(duration * sr))); t = np.arange(n, dtype=np.float64) / sr
    phase = 2 * math.pi * (48.0 * t + 28.0 / 16.0 * (1.0 - np.exp(-16.0 * t)))
    mono = np.sin(phase) * np.exp(-t * 9.0) + 0.025 * rng.normal(size=n) * np.exp(-t * 22.0)
    return pan_mono(0.22 * mono * envelope(n, sr, 0.002, 0.035), pan)


def woodblock(duration, sr, rng, pan):
    n = max(2, int(round(duration * sr))); t = np.arange(n, dtype=np.float64) / sr; base = rng.uniform(980.0, 1160.0)
    mono = (np.sin(2 * math.pi * base * t) + 0.54 * np.sin(2 * math.pi * base * 1.62 * t + 0.3))
    return pan_mono(0.105 * mono * np.exp(-t * 31.0) * envelope(n, sr, 0.0015, 0.020), pan)


def shaker(duration, sr, rng, pan):
    n = max(2, int(round(duration * sr))); x = rng.normal(size=n)
    high = x - np.convolve(x, np.ones(17) / 17.0, mode="same")
    high *= np.exp(-np.arange(n) / sr * 34.0) * envelope(n, sr, 0.003, 0.025)
    return pan_mono(0.022 * high, pan)


def subtle_pad(note, duration, sr, pan):
    n = max(2, int(round(duration * sr))); t = np.arange(n, dtype=np.float64) / sr; f = freq(note)
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
    y = x.copy(); ni = min(len(y), int(round(fade_in * sr))); no = min(len(y), int(round(fade_out * sr)))
    if ni: y[:ni] *= np.linspace(0.0, 1.0, ni)[:, None]
    if no: y[-no:] *= np.linspace(1.0, 0.0, no)[:, None]
    return y


def peak_normalize(x, target):
    peak = float(np.max(np.abs(x)))
    return x if peak == 0 else x * (target / peak)


def render_stems(duration: float, sr: int, bpm: float, seed: int):
    frames = int(round(duration * sr)); rhythm = np.zeros((frames, 2), dtype=np.float64); melody = np.zeros_like(rhythm)
    rng = np.random.default_rng(seed); beat = 60.0 / bpm; bar = beat * 4.0
    bars = max(1, int(duration // bar)); intro_end = max(1, math.ceil(bars * 0.125)); build_end = max(intro_end + 1, math.ceil(bars * 0.375)); outro_start = max(build_end + 1, math.ceil(bars * 0.8125))
    for b in range(bars):
        t0 = b * bar; root = ROOTS[b % len(ROOTS)]
        energy = 0.58 if b < intro_end else (0.82 if b < build_end else (1.0 if b < outro_start else 0.72))
        add_at(rhythm, subtle_pad(CHORD_TONES[root][0], bar + 0.4, sr, -0.32), t0, sr)
        add_at(rhythm, subtle_pad(CHORD_TONES[root][1], bar + 0.4, sr, 0.32), t0, sr)
        for k, bass_note in enumerate(BASS_WALK[root]):
            add_at(rhythm, energy * bass_pluck(bass_note, beat * 0.82, sr, rng, -0.08), t0 + k * beat, sr)
        for k, tone in enumerate(CHORD_TONES[root]):
            add_at(rhythm, energy * guzheng_pluck(tone, beat * 1.65, sr, rng, 0.88, (-0.38, 0.08, 0.42)[k]), t0 + (0.05 if k == 0 else (1.5 + 0.18 * k) * beat), sr)
        for k in range(4):
            bt = t0 + k * beat
            if k in (0, 2): add_at(rhythm, energy * low_drum(0.36, sr, rng, -0.05), bt, sr)
            if k in (1, 3): add_at(rhythm, energy * woodblock(0.13, sr, rng, 0.28 if k == 1 else -0.28), bt, sr)
            if b >= intro_end: add_at(rhythm, energy * shaker(0.10, sr, rng, -0.42 if k % 2 == 0 else 0.42), bt + beat * 0.5, sr)
    phrases = max(1, math.ceil(bars / 2)); climax_end = max(1, math.ceil(phrases * 0.75))
    for phrase in range(phrases):
        motif = MOTIFS[phrase % len(MOTIFS)]; phrase_start = phrase * 2 * bar
        level = 0.72 if phrase == 0 else (0.90 if phrase < climax_end else 0.68); register_shift = phrase % 8 in (4, 5)
        for idx, (note, beat_offset, beat_duration) in enumerate(motif):
            chosen = "D6" if register_shift and note == "D5" else note
            add_at(melody, level * dizi_note(chosen, beat_duration * beat, sr, rng, -0.14 + 0.28 * ((idx + phrase) % 3) / 2.0, ornament=idx in (0, 3)), phrase_start + beat_offset * beat, sr)
    rhythm = peak_normalize(fade_edges(short_reverb(rhythm, sr, 0.42), sr, 0.10, 1.20), 0.64)
    melody = peak_normalize(fade_edges(short_reverb(melody, sr, 0.58), sr, 0.12, 1.50), 0.56)
    return rhythm, melody


def resolve_under(root: Path, value: str) -> Path:
    candidate = (root / value).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path escapes root: {value}")
    return candidate


def duration_from_spec(root: Path, spec: dict) -> float:
    duration = spec.get("duration")
    if not isinstance(duration, dict) or set(duration) != {"timeline"}:
        raise ValueError("duration must contain exactly one timeline path")
    timeline = json.loads(resolve_under(root, duration["timeline"]).read_text(encoding="utf-8"))
    value = float(timeline["total_seconds"])
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeline total_seconds must be positive and finite")
    return value


def write_pcm16(path: Path, audio, sr: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.round(audio * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2); out.setsampwidth(2); out.setframerate(sr); out.writeframes(pcm.tobytes())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()


def metrics(x):
    peak = float(np.max(np.abs(x))); rms = float(np.sqrt(np.mean(np.square(x)))); tail_n = min(len(x), max(1, int(len(x) * 0.04)))
    return {"peak": peak, "rms": rms, "tail_rms": float(np.sqrt(np.mean(np.square(x[-tail_n:]))))}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--root", required=True, type=Path); ap.add_argument("--spec", required=True, type=Path); ap.add_argument("--overwrite", action="store_true"); args = ap.parse_args()
    root = args.root.resolve(); spec_path = args.spec.resolve()
    if spec_path != root and root not in spec_path.parents: raise SystemExit("spec path escapes root")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    allowed = {"schema_version", "preset", "duration", "seed", "sample_rate_hz", "bpm", "outputs"}
    unknown = set(spec) - allowed
    missing = allowed - set(spec)
    if unknown: raise SystemExit("unknown score spec fields: " + ", ".join(sorted(unknown)))
    if missing: raise SystemExit("missing score spec fields: " + ", ".join(sorted(missing)))
    if spec.get("schema_version") != 1 or spec.get("preset") != "chinese_travel_pentatonic_v1": raise SystemExit("unsupported score spec or preset")
    sr = int(spec["sample_rate_hz"]); bpm = float(spec["bpm"]); seed = int(spec["seed"])
    if not 0 <= seed <= 4294967295: raise SystemExit("seed must be within 0..4294967295")
    if sr != 48000: raise SystemExit("sample_rate_hz must be 48000")
    if not 40.0 <= bpm <= 180.0: raise SystemExit("bpm must be within 40..180")
    try:
        duration = duration_from_spec(root, spec); outputs = spec["outputs"]
        required = ("rhythm_wav", "melody_wav", "full_preview_wav", "report")
        if set(outputs) != set(required): raise ValueError(f"outputs must be exactly {required}")
        if len(set(outputs.values())) != len(required): raise ValueError("output paths must be unique")
        paths = {k: resolve_under(root, outputs[k]) for k in required}
        if any(paths[k].suffix.lower() != ".wav" for k in ("rhythm_wav", "melody_wav", "full_preview_wav")): raise ValueError("audio outputs must use .wav")
        if paths["report"].suffix.lower() != ".json": raise ValueError("report output must use .json")
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    existing = [str(p) for p in paths.values() if p.exists()]
    if existing and not args.overwrite: raise SystemExit("refusing to overwrite existing outputs: " + ", ".join(existing))
    frames = int(round(duration * sr)); exact_duration = frames / sr
    rhythm, melody = render_stems(exact_duration, sr, bpm, seed)
    full = fade_edges(peak_normalize(np.tanh((0.88 * rhythm + 0.92 * melody) * 1.08), 0.78), sr, 0.08, 1.40)
    for key, data in (("rhythm_wav", rhythm), ("melody_wav", melody), ("full_preview_wav", full)): write_pcm16(paths[key], data, sr)
    report = {"schema_version": 1, "kind": "story_music_stems", "approval": "pending", "preset": spec["preset"], "spec": str(spec_path.relative_to(root)), "implementation_sha256": sha256(Path(__file__).resolve()), "python_version": sys.version.split()[0], "numpy_version": np.__version__, "timeline": spec["duration"]["timeline"], "timeline_total_seconds": duration, "exact_pcm_frames": frames, "exact_pcm_duration_seconds": exact_duration, "sample_rate_hz": sr, "channels": 2, "bpm": bpm, "meter": "4/4", "bars": max(1, int(exact_duration // (60.0 / bpm * 4.0))), "seed": seed, "pitch_collection": list(PITCH_COLLECTION), "tonal_center": "D", "original_composition": True, "vocals": False, "rhythm_provenance": "one continuous global beat/phase timeline from t=0", "files": {}, "mixing": {"muxed_to_video": False, "speech_aware_routing_applied": False}}
    for key, data in (("rhythm", rhythm), ("melody", melody), ("preview", full)):
        path = paths[{"rhythm": "rhythm_wav", "melody": "melody_wav", "preview": "full_preview_wav"}[key]]
        report["files"][key] = {"path": str(path.relative_to(root)), "sha256": sha256(path), **metrics(data)}
    paths["report"].parent.mkdir(parents=True, exist_ok=True); paths["report"].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "report": str(paths["report"].relative_to(root)), "exact_pcm_frames": frames}, ensure_ascii=False)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
