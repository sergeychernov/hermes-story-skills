# Natural editorial composite generation brief

Use source media as image references and generate one text-free background for the selected platform aspect ratio.

## Required prompt structure

Describe, in order:

1. story and platform surface;
2. hero subject and placement;
3. supporting subjects and placement;
4. coherent environment, light, depth and palette;
5. calm region reserved for later deterministic title overlay;
6. target UI reservations from the platform contract;
7. forbidden changes.

## Reusable constraints

```text
Create a seamless photorealistic editorial cover background from the supplied reference images. Do not make a grid, contact sheet, card collage, split screen, framed montage or black text panel. Preserve the recognizable real people, clothing, animals, landmarks and story-critical objects from the references. Do not invent extra people or events. Blend subjects with coherent daylight, perspective, depth and color, using natural transitions rather than hard cutout edges. Leave a visually calm region inside the requested platform text-safe rectangle. Keep platform control reservations visually simple. Do not draw text, letters, logos, signs, badges, UI or watermarks. No duplicate subjects, changed identities, malformed anatomy or altered story facts.
```

Add story-specific subject hierarchy and focus placement. Never ask the image model to render final Cyrillic text; the deterministic renderer owns typography.

## QA gate

Reject and regenerate or fall back to deterministic composition if any of these occur:

- child/adult identity drift;
- changed clothing or pose that changes the event;
- extra or missing people;
- malformed hands, faces, animals or objects;
- duplicate subjects;
- fake readable text or logos;
- essential subject outside the safe composition;
- visual result looks like cards, cutouts or a contact sheet.

Record the generator/provider, model when exposed, prompt, source-reference paths/hashes and generated-background SHA-256 in project provenance. Label the result AI-assisted.
