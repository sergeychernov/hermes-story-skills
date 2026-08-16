# Stop-frame photo cards

## Contract

A stop-frame scene has three parts:

1. normalized source video on a CFR timeline;
2. a clone of its final decoded video frame for the requested hold;
3. one or more original-photo cards entering over that hold.

The source video remains immutable. The render report records source hash, output hash, video-frame count before the hold, freeze-frame count, card geometry/entrances/final positions, title, and audio handling.

## Reusable photo-frame helper

Do not repeat card-size arithmetic in every renderer. A helper has this contract:

```python
def framed_card_filter(input_label, output_label, *, width, height,
                       border=7, color="white") -> tuple[str, tuple[int, int]]:
    """Return FFmpeg filter fragment and (outer_width, outer_height)."""
```

The required filter sequence is aspect-fill → crop → pad → `setsar=1` → `format=yuv420p`:

```text
[input]scale=INNER_W:INNER_H:force_original_aspect_ratio=increase,
crop=INNER_W:INNER_H,
pad=OUTER_W:OUTER_H:BORDER:BORDER:color=white,
setsar=1,format=yuv420p[output]
```

`OUTER_W = INNER_W + 2 × BORDER`; `OUTER_H = INNER_H + 2 × BORDER`. Use these returned dimensions for off-canvas positions (`x=-outer_w` or `x=canvas_w`) and slide distance.

## Filter-graph outline

```text
[source] fps=30,…,trim=duration=SOURCE_VISUAL,
         setpts=PTS-STARTPTS,
         tpad=stop_mode=clone:stop_duration=HOLD [base]

[base][card_left] overlay=x=left-slide-expression:y=… [one]
[one][card_right] overlay=x=right-slide-expression:y=… [cards]
[cards] drawtext=…:enable='gte(t,SOURCE_VISUAL)' [video]

[source-audio] aresample=48000,apad,
               atrim=duration=TOTAL_VISUAL,asetpts=PTS-STARTPTS [audio]
```

Use `textfile=` for titles; do not put user text in drawtext's inline `text=` option. Obtain the lower-fifth geometry from `youtube_safe_title.py`; do not copy title-safe constants.

## QA

- Fully decode final MP4; `ffprobe` sees 9:16 video and an audio stream whose duration matches visual duration within encoder tolerance.
- Inspect: source-video frame, first frozen frame, a frame while every card enters, a settled frame, and final frame.
- At settle: all cards are inside frame, photo-filled, no black/empty backgrounds, source image remains recognizable, and title is legible and inside the safe zone.
- A title revision always creates a new hash and requires fresh visual inspection; do not claim an earlier preview contains the new title.
