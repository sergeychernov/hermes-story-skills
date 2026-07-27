# Story Skills

Composable Hermes skills for small media stories:

- `story` — domain-neutral editorial orchestration;
- `still-image-animation` — one still image to one verified motion scene;
- `social-publisher` — gated external publication;
- `photo-story-archive` — preserved source material and journal;
- `travel-social-publisher` — compatibility facade for existing archives.

Travel planning remains an external concern handled by the existing `travel-planning`, `maps`, and `live-transit-navigation` skills. Travel can contribute optional context to `story`; it is not a storytelling dependency.

## Prerequisites

### Required for local development and media tests

| Tool | Used by |
|------|---------|
| **Python 3.9+** | all skill scripts (stdlib only for core tests) |
| **`ffmpeg` and `ffprobe` in `PATH`** | `still-image-animation`, `travel-social-publisher`, package verification |

Quick check:

```bash
python3 --version
ffmpeg -version
ffprobe -version
```

### Title overlays on rendered scenes

`still-image-animation` and `travel-social-publisher` can burn in a `title` with FFmpeg `drawtext`. Both must be available:

1. **A system font** — the renderer searches common Linux and macOS paths (DejaVu, Liberation, Noto, Arial, and similar).
2. **FFmpeg built with `drawtext`** — without it, scenes still render but text is skipped silently.

Check:

```bash
ffmpeg -filters 2>&1 | grep drawtext
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path("skills/media/still-image-animation/scripts")))
from still_image_animation import resolve_font
print("font:", resolve_font() or "not found")
PY
```

**macOS note:** the default Homebrew `ffmpeg` formula often lacks `drawtext`. Install a build that includes libfreetype, for example:

```bash
brew uninstall ffmpeg
brew install homebrew-ffmpeg/ffmpeg/ffmpeg
```

Optional font package (user fonts land in `~/Library/Fonts/`):

```bash
brew install font-dejavu
```

**Linux note:** install `ffmpeg` from your distro or ensure `libfreetype` was enabled at build time; DejaVu or Liberation packages are usually enough for fonts.

### Optional — publishing and platform adapters

These are not needed to run the unit tests above, but are required for live publication workflows:

| Skill / workflow | Extra setup |
|------------------|-------------|
| `social-publisher` → Telegram Stories (user account) | `telethon`, `python-socks` — see `skills/media/social-publisher/references/telegram-stories.md` |
| `social-publisher` → YouTube | Google Cloud OAuth — see `skills/media/social-publisher/references/youtube-oauth-setup.md` |

## Test all local scripts

```bash
python3 -m unittest discover -s skills/media/still-image-animation/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/story/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/social-publisher/scripts -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/travel-social-publisher/scripts -p 'test_*.py' -v
```
