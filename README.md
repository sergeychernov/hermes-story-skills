# Story Skills

Composable Hermes skills for small media stories:

- `story` — domain-neutral editorial orchestration;
- `still-image-animation` — one still image to one verified motion scene;
- `social-publisher` — gated external publication;
- `photo-story-archive` — preserved source material and journal;
- `travel-planning` — constraint-aware composition of `maps` and live transit with optional Story context;
- `travel-social-publisher` — compatibility facade for existing archives.

Travel planning is separate from storytelling and composes the `maps` and `live-transit-navigation` skills. Travel can contribute optional context to `story`; it is not a storytelling dependency.

## Test all local scripts

```bash
python3 -m unittest discover -s skills/media/still-image-animation/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/story/scripts/tests -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/social-publisher/scripts -p 'test_*.py' -v
python3 -m unittest discover -s skills/media/travel-social-publisher/scripts -p 'test_*.py' -v
python3 -m unittest discover -s skills/travel/travel-planning/scripts/tests -p 'test_*.py' -v
```
