# Motion Choice for Still Photo Animation

## Pan vs Zoom — when to use each

### Pan (`pan_left`, `pan_right`) — movement scenes

Use for photos that imply motion: riding, walking, running, sports.

- `pan_left` (camera moves left) — feels like moving **forward into** the scene.
  Start with subject on the left, pan left opens the environment to the right.
  Good for: a child on a bike, someone about to run, a vehicle ready to depart.
- `pan_right` (camera moves right) — reveals the scene from the subject **outward**.
  Good for: establishing shots, showing context around a subject.

Set `focus_x` on the subject (typically 0.3–0.4 if subject is left-of-center)
so `focus_dwell` easing slows near them and keeps them visible longer.

### Zoom (`zoom_in`, `zoom_out`) — static scenes

- `zoom_in` — static, contemplative scenes: portraits, objects, details.
  Slow push toward the focus point. Good for: a quiet portrait, a still life,
  a moment of reflection.
- `zoom_out` — establishing or reveal shots. Start close and open the
  environment. Good for: "where are we?" context after a close-up.

### Common mistake

Using `zoom_in` for a scene that implies movement (e.g., a child sitting on a
bike, ready to ride). The zoom feels static and contemplative — wrong for an
action moment. **Pan conveys the riding impulse.**

## Pan direction cheat sheet

| Subject position | Narrative goal           | Motion     | focus_x |
|------------------|--------------------------|------------|---------|
| Left             | Move forward into scene  | `pan_left` | 0.35    |
| Left             | Reveal environment right | `pan_right`| 0.35    |
| Center           | Move forward             | `pan_left` | 0.50    |
| Right            | Move forward             | `pan_left` | 0.65    |
| Right            | Reveal environment left  | `pan_right`| 0.65    |

## JSON spec example (pan for movement)

```json
{
  "schema_version": 1,
  "source": "clip02-source.jpg",
  "output": "clip02-panleft.mp4",
  "width": 720, "height": 1280, "fps": 30, "duration": 5.0,
  "fit_mode": "crop",
  "motion": "pan_left",
  "focus_x": 0.35,
  "focus_y": 0.50,
  "pan_easing": "focus_dwell",
  "title": "Шлем надет\nПижама осталась\nПоехали.",
  "overwrite": true,
  "fade_in": true,
  "fade_out": true
}
```

## Verification

After rendering, always:
1. Check `motion_detected: true` in the JSON report.
2. Extract start/mid/end frames with ffmpeg and inspect visually.
3. Confirm the subject stays visible throughout the pan (adjust `focus_x` if
   they exit frame too early).
4. Confirm title position with a mid-clip frame (should be 66–71% of height
   for 720×1280).

## Skills repo source

Media skills source repository:
`/opt/data/home/story-skills` (github.com/sergeychernov/hermes-story-skills).

Check for updates before starting a session:
```bash
cd /opt/data/home/story-skills && git fetch origin && git diff HEAD origin/main --stat
```

The `LOWER_FIFTH_Y` fix (absolute `360` → proportional `h*0.1875`) is applied
in the installed skill but needs a PR to the source repo.