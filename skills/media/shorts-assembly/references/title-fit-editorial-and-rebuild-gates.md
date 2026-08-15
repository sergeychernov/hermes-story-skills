# Title fit, editorial continuity, and rebuild gates

## 1. Exact safe-line invariant

For Sergey's vertical YouTube stories, the bottom edge of the **complete title box**, including `boxborderw`, is pinned to `0.85 * frame_height`. The lower 15% is therefore exactly title-free. Do not add a second centering term such as `min(h*0.70-text_h/2, ...)`; it silently lifts short and multiline titles above the requested line.

The standard title position is mandatory unless the user explicitly approves an exception. Incidental passers-by, crowds, cars, pavement, or other non-story subjects may be covered to preserve a consistent title line. Do not move a title to the middle merely to protect incidental people.

## 2. Fit before render

A title is invalid if any glyph or box edge crosses the canvas or the reserved right-side controls strip. Before assembly:

1. preserve the user's exact approved wording and punctuation;
2. wrap semantically, not at arbitrary character boundaries;
3. measure or deterministically constrain the complete box;
4. shorten/rephrase only with user approval when exact wording cannot fit;
5. inspect start, middle, and end frames of the actual MP4.

## 3. Adjacent-title editorial check

Read titles in editorial order before rendering. Reject adjacent titles that repeat the same lead phrase or fact without adding a new beat. Example: `Современная архитектура Пекина` followed by `Современная архитектура со стилизованными крышами` is repetitive; the second should identify its distinct observation, such as old roof forms within the new city.

## 4. Local correction and final artifact verification

For a correction to one scene:

1. update the scene's renderer/spec and manifest title together;
2. render and visually inspect that scene;
3. rebuild the review film;
4. fully decode the rebuilt film;
5. extract a frame from the corrected scene **from the rebuilt film**, not from the standalone scene;
6. confirm the final film hash or modification state changed before delivery.

A timed-out or interrupted assembly may leave the previous valid final file untouched. Never infer that the new scene reached the film merely because the standalone scene rendered successfully. Inspect the final artifact itself.

## 5. Media fill is independent of title safety

Safe title placement does not justify blank padding. Use aspect-preserving `cover` when the user wants the frame filled. Use `contain` or black/tonal padding only after explicit approval. Never stretch non-uniformly.