# Title-safe composition for one animated still

Use this when the standard lower-fifth title would cover the story object or action in a single photo (for example, lifted food, hands, a toy, or a foreground bowl).

## Decision order

1. **Inspect start/middle/end before acceptance.** A face being clear is not enough; reject the render if the title covers the named object or action.
2. **Try content-aware crop/zoom first.** Slightly enlarge the image and choose a vertical crop offset that moves the action above the lower fifth while retaining the face and hands. Prefer this because it keeps the 9:16 frame filled with the real photo.
3. **Change motion if needed.** For a static food/portrait scene, `zoom_in` or `zoom_out` may preserve the title-safe composition better than a full horizontal pan. Keep full pans for scenes whose narrative actually implies lateral movement.
4. **Only then create a designed canvas.** Place the photo so all anchors remain visible and extend the lower title area with an intentional sampled/tonal treatment. Keep this extension only as tall as necessary for the title and platform safe margin; do not create a large blank footer.
5. Animate the designed canvas through `still-image-animation/animate_still.py`; do not replace the animation script with a static FFmpeg loop.

## QA anchors

For each sampled frame, verify all of the following independently:

- face/eyes;
- hands or tool (palettes, chopsticks, instrument, etc.);
- named story object/action;
- title legibility and safe margin;
- efficient use of the canvas.

A technically valid `motion_detected: true` report does not prove title-safe composition.
