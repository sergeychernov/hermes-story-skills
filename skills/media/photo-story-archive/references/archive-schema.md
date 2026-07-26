# Archive schema

Use this as a compact pattern, adapting fields to the task rather than copying empty placeholders.

```markdown
---
title: "Event or trip title"
date: YYYY-MM-DD
status: draft
platform: instagram
location: "Confirmed broad location"
---

# Story

One short evolving paragraph that joins the day's confirmed events in order.

## Photo N — short title

![[photos/YYYY-MM-DD_HH-MM-short-name.jpg]]

- **Time:** YYYY-MM-DD HH:MM (timezone)
- **Time source:** EXIF capture time / user-provided / chat receipt time / archive time
- **Place:** confirmed place, or `inferred from itinerary: ...`
- **Location confidence:** user-confirmed / itinerary-confirmed / inferred / unknown
- **File:** `photos/...`
- **Dimensions:** width × height
- **Orientation:** landscape / portrait / square
- **Bytes:** integer
- **SHA-256:** `...`
- **Scene:** factual visual description
- **User observation:** preserve the user's own wording or joke when it adds narrative value
- **Identity confidence:** verified / probable / unknown (for species, buildings, logos, etc.)
- **Mood:** brief creative interpretation
- **Carousel role:** opener / detail / transition / contrast / closer

### Draft caption

One or two natural sentences grounded in the image and journey.

### Stories overlay

A short phrase that remains legible on a phone screen.
```

## Naming

- Lowercase ASCII scene slugs are the most portable.
- Keep the source extension when copying an original.
- If two images share a minute and scene, add `-02`, `-03`, etc.

## Location confidence

Use one of these representations:

- `confirmed by user` — explicitly named by the user;
- `confirmed by itinerary` — user was actively navigating to/inside the venue and no later move was reported;
- `inferred from image/context` — plausible but not confirmed;
- `unknown` — do not guess.

## Final assembly

When the user says the sequence is complete:

1. review visual order, duplicates, and weak frames;
2. propose a carousel order and a separate Stories order;
3. write one unified caption rather than concatenating per-image captions;
4. identify any image that benefits from crop/rotation, but do not edit without approval;
5. present the exact assets and text for approval before publishing.
