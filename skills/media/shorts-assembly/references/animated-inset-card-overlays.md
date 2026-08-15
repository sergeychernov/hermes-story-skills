# Animated inset/card overlays

Use this when a photo or cropped detail enters as a smaller card over a full-frame photo.

## Geometry contract

Track these values explicitly:

- canvas: `W × H`
- card: `cw × ch`
- final position: `(xf, yf)`
- entrance interval: `[t0, t1]`
- motion direction: left→right or right→left
- subject facing: head/front on left or right side of the card

For a linear left entrance:

```text
x = if(t<t0, -cw,
       if(t<t1, -cw + (xf+cw)*(t-t0)/(t1-t0),
          xf))
```

For a linear right entrance:

```text
x = if(t<t0, W,
       if(t<t1, W - (W-xf)*(t-t0)/(t1-t0),
          xf))
```

Escape expression commas as `\,` inside FFmpeg filter graphs.

## Facing rule

- left→right: head/front belongs on the **right** side of the card;
- right→left: head/front belongs on the **left** side of the card.

Inspect the source itself before adding `hflip`. A mistaken flip can make the card move tail-first even when the x-expression is correct.

## Size revisions

When asked to make the inset larger:

1. Increase width and height proportionally by about 20–30% as a first revision.
2. Recompute the final `x/y` so the card remains within safe margins.
3. Reinspect the base image: the card must not hide the main comparison object, faces, or title.
4. Preserve the previously approved entrance timing unless the user asks for a timing change.

## Required visual QA

Inspect four moments:

1. before entry — base composition and title;
2. mid-entry — entrance edge, direction, and head/front leading;
3. just after arrival — card crop, size, and occlusion;
4. late hold — stable composition, safe zones, no residual motion.

Do not claim “head-first” from the filter expression alone. Confirm the head/front position in the mid-entry pixels.

## Report fields

Record:

```json
{
  "card_size": "650x458",
  "entrance_edge": "left",
  "motion_direction": "left-to-right",
  "subject_facing": "right",
  "arrival_interval_seconds": [0.8, 2.0],
  "final_position": [390, 190],
  "visual_qa": "mid-entry and late-hold frames passed"
}
```
