# Historical collage research and design rationale

This note records the evidence used to extract `animated-collage` from one-off renderers. It is not a publishing log.

## Sessions reviewed

- @session:default/20260725_080402_dbf3d816 — Istanbul montage work, including the four-photo “lipstick on the microphone” micro-story and later timing/orientation corrections.
- @session:default/20260802_033216_64054c9d — birthday Short, dense table/trampoline collages, title obstruction, direction, empty-space and animation feedback.
- @session:default/20260809_084005_6e439354 — Beijing story and the reproducible elevator, metro, garden, island, park-exit and night collages.

## Project renderer layouts compared

Reusable renderer names describe motion and geometry rather than the project subject:

```text
<direction>-<row>-<row>[-<row>...].py
```

- `u` means a dominant upward reveal;
- `p` means a portrait cell and `l` means a landscape cell;
- every hyphen after the direction separates canvas rows;
- letters inside one row list its cells from left to right.

The historical layouts therefore map to reusable names:

- `u-pp-pp.py`: four staggered portrait cards in two rows.
- `u-lp-l-pp.py`: asymmetric five-panel layout (`720+360`, full-width center, `540+540`).
- `u-pp-l-pp.py`: five-panel `2+1+2`, with a large landscape center row.
- `u-pp-pp-pp.py`: six-panel `2x3` route sequence.
- `u-pp-pp-l.py`: five-panel `2+2+1`, with a face-free full-width landscape title panel.

The historical assembly-only script that removed a collage segment is deliberately excluded: assembling an edited story variant is not a reusable collage renderer.

## Repeated successful engineering pattern

- 1080x1920, 30 fps, five seconds, H.264/yuv420p, `+faststart`.
- Convert each source once to an aspect-fill PNG card, then animate the card. This avoids scaling full-resolution originals on every frame.
- Dense real-photo coverage; a darkened source crop is only a temporary behind-panels canvas during entrance.
- Cubic ease-out entries from alternating sides or below.
- All entrances finish inside the first two seconds, followed by three seconds of stable reading time.
- White title on `black@0.58` in the lower fifth.
- Extract and inspect mid-entry, arrived, final, and contact frames.
- Emit a machine-readable report with dimensions, duration, decode status, source order, layout, animation, hashes, and QA paths.

## User feedback converted into hard rules

| Feedback seen in prior sessions | General rule |
|---|---|
| “Сейчас много пустого места” | No empty cells, wide unused margins, or blurred filler when supplied photos can fill the canvas. |
| Landscape and portrait photos were not equally readable in a uniform grid | Choose cells from source orientation and subject geometry; use a full-width landscape row when it carries the scene. |
| “За надписью не видно детей на батуте” | A title requires explicit face/action-safe bottom panels; fail instead of silently covering people. |
| “Фотки пролетают быстро, я не успеваю…” | Entrances are short, but the completed collage must have a stable hold; Story default is two seconds plus three seconds. |
| “Коллаж анимационный” | A static contact sheet does not satisfy an animated-collage request; verify actual motion. |
| “Только в другую сторону” / movement-direction corrections | Visible vehicles, animals, gaze, or moving cards should enter head-first; use a custom effect when generic panel motion cannot express that. |
| “Почему правый край обрезается?” | Focal points must not become a permanent narrow crop. Check that the chosen crop preserves the required edge or use a separate pan scene. |
| “Титры должны быть в общем стиле” | Keep the established lower-fifth white/black@0.58 title style; do not move titles to the top casually. |
| Music corrections in the birthday workflow | The collage renderer stays silent. Story/music assembly decides whether approved rhythm or melody is added later. |
| Requests for title choice | `story` owns three title options and user selection; this renderer consumes the selected exact title. |

## Why the contract uses semantic annotations

Automatic face detection alone cannot know whether a sign, dish, clock, reflection, mascot, or edge is narratively important. The render spec therefore records:

- `focus_x/focus_y` — crop anchor after visual inspection;
- `title_safe` — lower panel can safely carry the title;
- `hero` — panel is the reveal/payoff;
- `layout: auto` and `animation: auto` — deterministic selection from those annotations.

The renderer reports its final source order because title-safe images may move to the bottom row. Visual QA remains mandatory.
