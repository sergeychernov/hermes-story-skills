# Smooth still-image motion for vertical video

Use this reference when a Reel/Short contains still images that should feel alive without visible stepping or subject drift.

## Failure pattern

A small zoom applied directly on the final 1080×1920 canvas can look like a light twitch rather than continuous motion. At low amplitudes (for example 3–4% over 2.5–3 seconds), crop coordinates may remain on the same integer pixel for several frames and then jump. A technically valid 30 fps export can therefore still look uneven.

## Stable zoom recipe

1. Build the crop/contain composition on a **2160×3840 working canvas**.
2. Use `zoompan` to produce the final 1080×1920 stream.
3. Default to about **9% total travel** for 2.5–3.1 second stills; reduce it only when a face, label, or edge would be cropped.
4. Apply cosine easing so velocity reaches zero at both ends:

   ```text
   ease = (1 - cos(PI * progress)) / 2
   zoom_in  = 1.000 + 0.090 * ease
   zoom_out = 1.090 - 0.090 * ease
   ```

5. Keep a visual anchor fixed near the viewport centre:

   ```text
   x = clamp(iw * focus_x - iw / (2 * zoom), 0, iw - iw / zoom)
   y = clamp(ih * focus_y - ih / (2 * zoom), 0, ih - ih / zoom)
   ```

`focus_x` and `focus_y` are normalized `0.0–1.0` coordinates on the composed vertical canvas.

## Built-in source borders

A mathematically valid cover crop (`zoom >= 1.0`) can still reveal a frame when the source itself is a designed diptych/collage with an outer border. Let ordinary photos reach exact cover scale (`zoom = 1.0`) at the widest point; do not add overscan by default. Use a per-clip overscan only for bordered composites, and only as much as needed to remove their built-in outer frame. Measure the widest rendered frame instead of guessing:

```bash
ffmpeg -v info -loop 1 -i widest-frame.jpg \
  -vf cropdetect=limit=0.08:round=2:reset=0 -t 0.2 -f null - 2>&1 \
  | grep 'crop=' | tail -1
```

The accepted result for a 1080×1920 frame is `crop=1080:1920:0:0`. If cropdetect reports side bars, increase only that clip's minimum overscan and render again. In one bordered diptych, 4% still left 16/14 px side bars; 11% removed them without harming the subjects. Treat the standalone animation's widest non-faded frame as the authoritative geometry check. After assembly, also verify integration in the final master, but sample just inside the scene after fade-in and before fade-out—not at the exact manifest boundary, which may be intentionally black or dimmed and can conceal crop or text defects.

## Face-aware anchoring

- For one face, place the focus at the point between the eyes.
- For a close pair, use the midpoint between their eye/face centres so neither person drifts out of the frame.
- For a landscape source shown with `contain`, convert the source-space face coordinate to the composed-canvas coordinate because the foreground occupies only the middle band of the 9:16 canvas.
- Check both the first and last non-faded frames. Face detection or estimated coordinates are only a starting point; composition wins.

## Memory-safe rendering of many animated stills

Do not place many 2160×3840 `zoompan` branches in one FFmpeg `filter_complex`: FFmpeg may keep them active concurrently and the kernel can kill the render with `SIGKILL` under normal NUC memory limits.

For an episode with several animated stills:

1. render each still scene sequentially to its own normalized 1080×1920, 30 fps, H.264 intermediate;
2. verify start/mid/end composition and adjacent frame hashes for each intermediate;
3. add captions/fades per scene while normalizing audio to AAC stereo 48 kHz;
4. concatenate the normalized scene files;
5. derive Telegram and other lightweight previews from the resulting master;
6. run package verification and final exact-timeline contact-sheet QA.

Never solve memory pressure by changing stills to `motion: "none"` or wide photos to `contain`. Render architecture may change; the approved composition rule may not.

## Verification

Render a short spike before rebuilding the full episode. Then verify that adjacent video frames are not duplicated:

```bash
ffmpeg -v error -i spike.mp4 -map 0:v:0 -an -f framemd5 -
```

Parse only video hashes and count equal adjacent hashes. Always include `-map 0:v:0 -an`: otherwise audio packets are mixed into the output and produce misleading frame counts and false duplicate reports.

For every zoom scene in the final master:

1. inspect start/end frames for subject retention;
2. count adjacent duplicate video hashes in the non-faded middle interval;
3. confirm the stronger motion did not crop text, faces, or designed overlays;
4. generate and inspect the lightweight Telegram preview, not only the full-resolution master.

## Caption placement learned from device review

Safe-zone diagrams are conservative defaults, not a substitute for a real-device preview. If the user shows that platform chrome occupies less space on their phone, expose per-episode `title_y` and `caption_y` overrides. Position the **bottom edge of the whole text box** just above the observed UI boundary; do not reason from the text baseline alone. Keep the right edge clear of the reaction rail independently of the lower boundary.
