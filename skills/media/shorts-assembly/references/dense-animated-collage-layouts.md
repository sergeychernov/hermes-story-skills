# Dense animated collage layouts

Use this reference for 4–6 photos in a vertical Story when the user wants a collage rather than separate still scenes.

## Space-utilization rule

A 9:16 collage should be filled by real photographs edge to edge. Do not reserve a decorative header/footer or leave a dark background band merely to host the title. The standard lower-fifth title may overlay a real panel when that panel contains no face or key action. If every candidate panel contains important content, change the panel assignment/crop rather than moving the title to a bespoke top header.

Priorities:

1. preserve faces, hands, and the story object;
2. fill the frame with actual source photos;
3. keep the standard lower-fifth title style;
4. use small borders/gutters only as separators, not as empty layout regions.

## Reliable layouts

### Four photos

A dense 1080×1920 arrangement:

- wide hero: `1080×720` at `y=0`;
- two middle panels: `540×650` each at `y=720`;
- wide bottom panel: `1080×550` at `y=1370`.

Place a low-detail/no-face image in the bottom panel and allow the lower-fifth title to overlay it. This avoids the wasteful caption-only footer.

### Five photos

A dense `2 + 1 + 2` arrangement:

- top: `720×650` plus `360×650`;
- middle: `1080×500`;
- bottom: two `540×770` panels.

Put key people in the top/middle. Use low-detail or distant-subject photos in the bottom row under the title.

### Six photos

Use an equal `2 × 3` grid when all six images deserve comparable weight:

- every panel: `540×640`;
- top row: `y=0`;
- middle row: `y=640`;
- bottom row: `y=1280`.

Assign prominent faces and close human action to the top and middle rows. Reserve the bottom row for water, gardens, architecture, or other title-safe scenery so the shared lower-fifth title can span both columns without covering a person. For landscape sources in portrait-shaped cells, choose crop offsets per image rather than centering mechanically—for example, use `x=iw-ow` when an ornate column or other story detail sits at the right edge. If a nominally scenic bottom panel contains distant people, crop toward the architecture and verify that the title does not cover any still-recognizable face.

These are starting points, not fixed templates. Swap panel roles based on subject location and source orientation.

## Animation implementation

Render from preserved originals through a reusable project or skill script—not an inline one-off command. The script should:

1. preprocess each source once into its final panel size using aspect-fill crop and a small border;
2. compose all panels in one FFmpeg filter graph;
3. animate panel coordinates during `t=0…2` with staggered arrivals from distinct sides;
4. pin every coordinate for `t=2…5` with no fade-out;
5. apply the shared lower-fifth title (`white`, `black@0.58`, `boxborderw=24`);
6. decode-check the MP4 and emit a JSON report with dimensions, duration, hash, renderer, and source list.

Preprocessing cards before the animated overlay pass avoids repeatedly scaling full-resolution JPEGs for every output frame.

When constructing a Python `filter_complex` string, escape the comma inside the lower-fifth expression:

```text
y=min(h*0.80-text_h/2\,h-text_h-h*0.1875)
```

## Visual QA

Inspect at least:

- `1.0s`: mid-entrance; partial offscreen panels are expected, but no broken overlays;
- `2.1s`: all panels arrived and title placement is final;
- `4.8s`: late hold is identical in geometry to the arrived frame.

Reject and redesign if:

- a final-state region shows only background rather than a photo;
- the title covers a face, hands, food being lifted, or other key action;
- a top title/header appears without explicit user request;
- a panel is technically filled but the crop removes its subject;
- motion continues during the requested static hold.
