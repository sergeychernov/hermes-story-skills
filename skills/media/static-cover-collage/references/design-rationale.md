# Design rationale

The default vertical layout adapts the established Istanbul concert/travel cover language rather than copying its exact geometry: one dominant visual, contrasting supporting moments, and a large dark typographic field.

## Geometry

- hero: full-width top 52%
- support left/right: next 22%
- text panel: bottom 26%

This preserves hierarchy and phone readability. It deliberately avoids a uniform contact sheet.

## Typography

- yellow accent line: destination/hook
- large white primary line: narrative promise
- small white keywords: visual itinerary
- black outline for legibility

## Crop contract

Every image is uniformly scaled with `max(target_w/source_w, target_h/source_h)` and cropped around normalized focus coordinates. Pixels are never independently stretched along X/Y. Image cells are edge-to-edge; no blurred duplicate or blank filler.

## Reproducibility

The spec fixes source paths, focus coordinates, normalized cell geometry, colors, dimensions, and title text. The report records source hashes, crop geometry, font path, output hash, and visual-review status.
