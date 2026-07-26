# Media intake and visual QA

Use this reference when media arrives incrementally or when a rendered package has text overlays.

## Incremental intake

1. In an active travel/archive thread, treat a media-only message as the next archive item unless more than one active archive is plausible. A short phrase next to media is the user's scene label or observation, not permission to publish.
2. Preserve originals without transcoding or overwriting. Use semantic filenames; record dimensions, orientation, byte size, and SHA-256; verify source and archive hashes match.
3. For photos, record chat receipt time separately from capture time. Never present filesystem timestamps as camera time.
4. For videos, inspect rather than asking the user to describe them:
   - run `ffprobe` for codec, dimensions, duration, fps, audio, channels, and creation time;
   - extract and inspect a contact sheet with sampling adapted to clip length: for clips under 10 seconds prefer about 2 fps or 8–12 evenly spaced frames; a slow interval such as one frame every 2–3 seconds can leave only one or two useful tiles and hide signs or architectural details;
   - preserve original audio unless the user asks to remove it;
   - never invent a transcript when speech-to-text was not actually run;
   - flag low-resolution sources that may look soft after 1080×1920 scaling and recommend a concise excerpt when the full clip slows the edit.
5. Preserve the user's wording verbatim as attributed provenance, then add a separate neutral visual description and suggested narrative role. Identities, plant names, building names, and location claims may come from the user or established sequence, but record that provenance; do not turn contextual inference into visual/biometric certainty.
   - Treat a short phrase accompanying media as the user's scene label, not necessarily a request to prove the exact object name.
   - For landmark identification, prefer visible signage, embedded coordinates, or a strong map/reference-image match. Sequence context can support a neighborhood-level inference but not an exact building name.
   - If reasonable comparison does not establish the exact object, stop the search, archive it under the attributed user label, mark the name unresolved, and avoid converting a plausible candidate into fact.
6. Append the item to the archive journal and classify it as **selected**, **optional**, or **archive-only**.
7. Offer exactly three concise title choices after every new photo or video: one direct/descriptive, one atmospheric/narrative, and one explicitly self-ironic. Keep them genuinely distinct, preserve any user-supplied wording as provenance, and do not finalize a proposed title until the user chooses. A numeric reply selects the corresponding option and updates the existing journal entry plus any draft overlay/caption; it does not create another material. Keep unresolved choice sets attached to their material IDs: a later upload may be archived normally, but it neither selects nor cancels an earlier title. If a bare number is separated from its choices by another upload or could refer to more than one unresolved material, ask for the material number instead of guessing.
8. If selected material arrives after a render, the old package and `verification.json` are stale. Do not silently rerender after every upload while collection is ongoing, but update the manifest and rerender when the user says “собери/обнови”, signals collection is complete, or before any approved publication.
9. Treat late-arriving context as permission to revise the narrative meaning of earlier items. If a follow-up photo turns an earlier sign or façade into a setup, update the earlier item's role and caption rather than appending a contradictory standalone caption. Prefer a concise setup/payoff pair (expectation → personal choice) plus one combined caption for the final edit.
10. Treat a text reply that corrects or enriches the immediately preceding media description as an update to that same archive item, not as a new asset. Preserve the user's exact wording separately from the neutral visual description; use attribution such as “по наблюдению пользователя” when plausible but not independently established. If the correction changes the joke or scene meaning, revise the existing caption and narrative role as well—for example, a note about riders on a tram's rear footboard should update the tram entry and title rather than create a separate scene.
11. When deriving captions from visible badges, plaques, dates, or logos, record what the sign literally proves before interpreting it. Guide inclusion or recognition does not automatically prove a star, rank, prize tier, or endorsement level; keep stronger claims out unless independently verified.
12. Treat phrases such as “пора домой”, “идём ужинать”, or “собираемся на концерт” as **chapter transitions**, not automatic end-of-collection signals. While intake is still open, assign provisional roles such as “transition to the evening chapter” rather than repeatedly calling each latest item the final closer. Only freeze the closing scene when the user explicitly ends collection or asks to assemble the episode.
13. If a later photo contains a clearly legible venue sign, promote the venue identity from hypothesis to visually confirmed fact in the archive and future captions. Keep claim scope narrow: a sign can confirm the venue, but not the performer, date, ticket conditions, or exact event program. Preserve earlier attributed uncertainty where historically useful rather than silently rewriting it as if it had always been known.

A package is publishable only when its verification was produced after the latest manifest and selected-source changes.

## Signs, object identification, and caption prompts

When a travel image contains a sign, plaque, menu, or storefront:

1. Separate **visible text**, **contextual inference**, and **verified identity**. Record each at its actual confidence; never convert an unreadable plaque or route context into a confirmed object name.
2. If text is small, crop the relevant area, enlarge it with a high-quality scaler, and inspect the crop. Quote only genuinely legible fragments; preserve ellipses or uncertainty instead of completing words from expectation.
3. Use route context, maps, and image comparison when the user asks to identify the place or object. Do not let identification research displace a simple creative request.
4. For prompts such as “придумай подпись по вывеске”, lead with **one concise best caption** built from the exact readable fragment. Wordplay is welcome when clearly editorial, for example combining a visible Latin fragment with a Russian word; do not present the joke as a translation or factual name.
5. Preserve the user's terse phrase as an attributed scene note. If an archive is active, save the chosen caption with the media item, but do not publish or rerender while collection continues.

### Coastlines, skylines, and historic fortifications

Travel captions often combine a visible scene with a geographic interpretation that the pixels alone cannot prove. Keep these layers separate:

1. Preserve claims such as “the opposite shore,” “view toward the Bosphorus,” or “a castle by the station” as the traveller's observation until a map, GPS fix, sign, or strong reference-image match confirms them. A dark band on a hazy horizon may be land, cloud, or atmospheric contrast.
2. Distinguish **where the camera stands**, **what direction it faces**, and **what is visible**. Being on the Marmara coast does not by itself prove that a skyline is the Bosphorus or that the far strip is the opposite shore.
3. For ruins, classify the structure before naming it: city wall, sea wall, land wall, gate, tower, fortress, monastery, or later restoration. Alternating stone-and-brick masonry supports a Byzantine attribution but rarely proves a particular gate or numbered tower.
4. Near transit lines, use the exact station and route sequence to narrow candidates, then compare arches, tower shape, masonry bands, and surrounding terrain against references. Report the broad complex confidently when supported, but keep the precise gate/tower qualified unless the view matches.
5. An old **sea wall** may now stand inland because of reclamation, coastal roads, railways, or parks. Verify that historical shoreline shift before turning “the sea is no longer visible” into explanatory copy; do not relabel the wall as a standalone castle merely because water is absent today.
6. Store the user's wording, neutral visual description, identification confidence, and historical explanation as separate journal fields. Titles may use the user's poetic observation, while factual captions retain the confidence qualifier.

### LED transit displays and rolling-shutter captures

Phone photos of LED departure boards often contain incomplete characters because the camera shutter scans while the display refreshes. A plausible-looking row is not necessarily a complete reading.

1. Crop the board tightly and enlarge it with nearest-neighbour scaling so the LED dot pattern is preserved; do not rely only on a smoothed or sharpened crop.
2. When rows use different colours, create separate high-contrast masks for green/red/white pixels. This can separate destinations and countdowns from safety warnings and a fixed clock.
3. Infer a field's meaning from layout and visible units, not digits alone: a fixed corner `HH:MM` may be the current clock, while row-aligned values followed by `DK`/`dk` are countdowns in Turkish (`dakika`).
4. Quote only characters supported by the captured pixels. If rolling shutter removed essential strokes, report the row as unreadable instead of completing a familiar destination or warning from expectation.
5. Do not convert a countdown into an exact departure time unless both the current clock and interval are independently legible. Label the result approximate because the display may update between capture and reading.

### Food-photo identification and sensory notes

Food uploads often combine visible evidence with the traveller's taste, temperature, or texture report. Preserve both without pretending the photograph proves the sensory claim.

1. Store the user's observations—such as warm, oily, too doughy, spicy, or unexpectedly light—as attributed sensory notes. Keep them distinct from the neutral visual description, but use them as valid narrative material and title inspiration.
2. Identify the dish at the narrowest defensible level. Use the user's name as provenance, then inspect shape, scale relative to utensils, folds, garnish, sauce texture, and accompaniments. Do not infer a hidden filling or exact recipe from an intact dumpling, soup, pastry, or sandwich.
3. For sauces, distinguish what the image supports from a culturally common preparation. Glossy orange droplets over yogurt may support melted butter or oil infused with red pepper; a thick red coating is stronger evidence for tomato or pepper paste. Say “likely” when several preparations produce the same appearance.
4. Do not let a canonical recipe override the actual serving. Regional and restaurant variants may be larger, thicker, differently folded, or more dough-forward than a textbook example.
5. In the archive, record four separate fields where useful: user sensory note, visible components, likely culinary interpretation with confidence, and editing role. This prevents a personal reaction from being rewritten as an objective recipe claim.
6. Build the three title options from different axes: dish identity, dining narrative, and a kind self-ironic reaction. A sensory observation such as “more dough than expected” is stronger story material than a generic “delicious local food” caption.

## Contact sheets

Create contact sheets to check narrative order without loading the whole video. Sample:

```bash
ffmpeg -y -v error -i reel-short.mp4 \
  -vf "fps=1/3,scale=270:480,tile=4x2" -frames:v 1 contact-sheet.jpg
```

A final black tile can be unused grid capacity rather than a black frame in the video. Count sampled scenes before reporting a defect.

## Scene captions and vertical reframing

When the user's observations carry the story, do not rely only on the post caption: add a concise `caption` to each relevant clip in the episode manifest. Keep it to one or two short lines and place it in the lower safe zone, above platform controls.

Choose reframing per clip rather than applying one rule to every landscape source:

- use `fit_mode: "crop"` for central or safely isolated subjects; adjust `focus_x` from `0.0` (left) to `1.0` (right);
- use `fit_mode: "contain"` when people or related objects are spread across the width and cropping would destroy the story;
- inspect the actual crop before rendering the whole episode when the subject is small or off-centre;
- after cropping, make the caption match what remains visible. For example, if only one bird survives a useful crop, do not leave a plural caption;
- never infer that a semantic filename guarantees the named subject is prominent in the rendered frame.

For mixed portrait/landscape edits, cropped scenes may fill 9:16 while exceptional wide compositions remain fitted over a blurred background. Consistency of intent matters more than forcing one geometry everywhere.

## Speech-boundary and duration-budget QA

A visual contact sheet cannot prove that dialogue is complete. Treat every clip containing speech as an audio edit, not merely a duration slot.

1. Probe the natural source duration and mark whether the clip contains speech, ambience, or silence.
2. If a manifest `duration` is shorter than the source, remember that the renderer takes the **first N seconds**; it does not find a sentence boundary. Do not use that field as a generic pacing trim on speech.
3. Prefer the full speaking clip. If an excerpt is necessary, create a derived clip and verify its start and end by listening or reliable transcription, leaving a small natural breath/room-tone tail when available.
4. Build the ≤60-second budget around protected speech first. Recover time from still durations, redundant establishing shots, repeated concert angles, or silence.
5. After rendering, listen from at least one second before to one second after every speaking-scene boundary in the master and platform derivative. A successful decode and readable midpoint frame do not satisfy this check.
6. If the user reports truncated speech, restore the complete phrases first, then tighten non-speaking scenes and rerender/reverify the entire package.

## Midpoint contact-sheet QA

A periodic contact sheet can skip short clips or sample a fade. For final scene-by-scene QA, extract one frame at the midpoint of every manifest clip using cumulative durations, then tile those frames in exact narrative order. Check each tile against the manifest for:

- expected subject and crop;
- exact scene caption, spelling, singular/plural agreement, and line wrapping;
- face/object preservation;
- safe-zone placement;
- blank frames or unintended transitions.

If only one clip changes after this check, rerender, technically verify the package again, and extract that clip's midpoint for focused visual confirmation.

## Render-performance pattern

For blurred 9:16 backgrounds, do not blur a full 1080×1920 stream when the background is intentionally soft. Scale the background branch to a small working size (for example 270×480), crop and blur there, then upscale it behind the sharp foreground. This preserves the intended look while greatly reducing CPU cost. Keep the foreground at output resolution. For CPU-bound H.264 renders, `libx264 -preset veryfast -crf 20` is a practical quality/speed baseline; always run the same technical and visual checks after changing encoder or filter settings.

## Text-overlay QA

FFmpeg `drawtext` does not wrap long titles automatically. A title can pass codec/dimension checks while being clipped on both sides.

Before rendering, wrap titles into a UTF-8 text file at a conservative width (about 20–24 Cyrillic characters for 1080px at 58–64px DejaVu Sans Bold). Use `textfile=` rather than escaping non-ASCII text inline.

After rendering, visually inspect both:

- the cover;
- a sampled first frame containing the title.

Completion criteria:

- every line is fully inside the frame with side margins;
- the text box does not cover the main subject's face;
- the title remains inside Reels/Shorts safe areas;
- Cyrillic glyphs render correctly;
- no real blank/black scene appears between selected clips.

Technical verification (`ffprobe`, decode test, dimensions, codecs) and visual verification are separate gates; both must pass before delivering the draft.