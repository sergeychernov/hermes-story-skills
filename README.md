# Story Skills

Composable Hermes skills for small media stories:

- `story` — domain-neutral editorial orchestration and approval gates;
- `photo-story-archive` — preserved source material and journal;
- `still-image-animation` — one still image to one verified motion scene;
- `animated-collage` — independently rendered multi-photo scenes;
- `scene-group` — reusable editorial beats built from approved scenes;
- `media-voiceover` — immutable source voiceover plus versioned derivatives;
- `static-cover-collage` — platform-specific natural and collage covers;
- `story-soundtrack` — frame-locked composition, source mix, approval and handoff;
- `shorts-assembly` — final visual assembly and exact approved-audio mux;
- `social-publisher` — gated external publication;
- `travel-social-publisher` — compatibility facade for existing archives.

These packages are the media dependency graph delegated by `story`. They are
kept together so a checkout does not silently fall back to stale globally
installed skill copies.

Travel planning remains an external concern handled by the existing `travel-planning`, `maps`, and `live-transit-navigation` skills. Travel can contribute optional context to `story`; it is not a storytelling dependency.

By default, durable story archives live under the domain-neutral `~/stories/YYYY-MM-DD-topic/` root. Originals, previews, music, renders, and publishing packages stay together in the corresponding story directory; platform names describe exports, not storage roots.

## Prerequisites

### Required for local development and media tests

| Tool | Used by |
|------|---------|
| **Python 3.10+** | all skill scripts; PEP 604 union syntax is used |
| **`ffmpeg` and `ffprobe` in `PATH`** | scene rendering, voiceover, soundtrack, assembly and package verification |
| **NumPy** | `story-soundtrack` and deterministic music helpers |
| **Pillow** | `static-cover-collage` rendering and tests |

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
| `shorts-assembly` → Telegram Bot review delivery | `python-telegram-bot` with proxy extras when a proxy is configured |
| `social-publisher` → YouTube | Google Cloud OAuth — see `skills/media/social-publisher/references/youtube-oauth-setup.md` |

## Test all local scripts

Preferred one-command runner:

```bash
PYTHON=.venv/bin/python scripts/test_all.sh
```

It executes the following suites explicitly:

```bash
python3 -m unittest discover -s skills/media/still-image-animation/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/story/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/animated-collage/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/scene-group/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/media-voiceover/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/static-cover-collage/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/story-soundtrack/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/shorts-assembly/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/social-publisher/scripts -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/travel-social-publisher/scripts -p 'test_*.py' -v
```
