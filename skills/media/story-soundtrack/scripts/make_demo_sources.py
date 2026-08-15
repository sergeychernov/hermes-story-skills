#!/usr/bin/env python3
"""Generate short PCM16 stereo source clips for demo/tests."""
from __future__ import annotations

import argparse
import math
import wave
from pathlib import Path

import numpy as np


def write_tone(path: Path, duration: float, freq_hz: float, sr: int = 48000) -> None:
    n = int(round(duration * sr))
    t = np.arange(n, dtype=np.float64) / sr
    mono = 0.25 * np.sin(2 * math.pi * freq_hz * t)
    fade = min(n, sr // 20)
    env = np.ones(n, dtype=np.float64)
    if fade > 0:
        env[:fade] *= np.linspace(0, 1, fade)
        env[-fade:] *= np.linspace(1, 0, fade)
    mono *= env
    stereo = np.column_stack((mono, mono))
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.round(stereo * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(sr)
        out.writeframes(pcm.tobytes())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    args = ap.parse_args()
    root = args.root.resolve()
    write_tone(root / "demo/source/voice_scene.wav", 1.0, 440.0)
    write_tone(root / "demo/source/music_scene.wav", 1.0, 220.0)
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
