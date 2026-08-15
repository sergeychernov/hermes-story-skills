# Animated collage renderer contract

Use this contract when a story scene combines several still photos into one 9:16 animated collage.

## Renderer boundary

Prefer an existing skill/project renderer. If none fits, create one reusable script rather than typing an inline FFmpeg graph. The script must accept or declare:

- ordered original image paths;
- per-panel crop/focus offsets;
- output path, dimensions, fps and duration;
- selected multi-line title;
- panel entrance intervals and final coordinates.

A revision must rebuild from preserved originals, not from an earlier rendered collage.

## Required visual behavior

- Panels fill their cards edge-to-edge; no empty cells or blurred duplicate cards unless explicitly requested.
- Animate panel positions independently. For the common five-second scene, stagger arrivals during `0–2s`, then hold all coordinates fixed during `2–5s`.
- Use the shared lower-fifth title style: white text, `black@0.58` box, `boxborderw=24`, proportional bottom safe margin.
- Never introduce a bespoke top header unless the user explicitly requests it. Design panel geometry around the lower title zone so important faces/action remain unobscured.
- Make overlap decisions from the inspected sources. If no face, person, sign, or key action occupies the lower fifth, the title may overlay a real photo; this is preferable to reserving a large empty or decorative title band.
- Evaluate canvas utilization on the settled frame. For four landscape sources, a useful dense candidate is a wide hero panel, two middle panels, and a wide bottom panel beneath the title. Treat unexplained background-only regions as a layout defect, not as automatic safe space.

## FFmpeg scripting details

- Put multi-line titles in a UTF-8 text file and use `drawtext=textfile=...`.
- In a scripted `filter_complex`, escape commas inside expressions, e.g. `y=min(a\,b)`. An unescaped comma can produce a misleading parse error near a later option such as `box=1`.
- Use an explicit `-t`, frame rate, H.264/yuv420p output and `+faststart`.
- For static source cards, preprocessing each crop once before the 30-fps overlay pass avoids repeatedly scaling full-resolution originals.

## Verification report

The script should emit or save:

- exact output path and SHA-256;
- codec, width, height, fps and duration;
- whether audio is present;
- decode result;
- title position/style;
- three QA frame paths: mid-entrance, just after final arrival, and late hold.

Visually inspect all three frames. Confirm that cards are still entering in the first, all are settled in the second, and the second/third match geometrically during the hold. Check title clipping, lower-fifth placement, safe zones, card fill, and important-subject visibility before delivery.
