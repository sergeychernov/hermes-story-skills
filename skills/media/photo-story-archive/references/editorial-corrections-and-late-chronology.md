# Editorial corrections and late chronology

Use these patterns while an archive is still collecting.

## Late-arriving scenes that belong earlier

A media item's stable archive/material ID records ingestion identity; it does not dictate montage order. When the user later supplies an earlier event:

1. Preserve the new original and checksum it normally.
2. Insert its story entry at the corrected narrative location.
3. Keep existing material IDs stable rather than renumbering the whole archive.
4. Update the manifest's explicit ordered source list.
5. Rephrase the story overview and neighboring transitions so the chronology reads naturally.
6. Label capture-time claims honestly. User-provided relations such as “arrival before the morning tower visit” establish relative chronology even when EXIF is absent; they do not establish an exact clock time.

Example arc: arrival at an airport → next morning's tower visit → daytime city walk → evening district. The late upload may receive a larger material ID while still becoming montage frame 1.

## Duplicate resend or “did you forget?”

Treat this as an integrity audit, not as a request to append another copy:

1. SHA-256 the resent upload and candidate archived file.
2. If hashes match, do not duplicate it.
3. Verify that the story entry exists and that the manifest puts it in the promised editorial position.
4. Reply briefly with the evidence: archived, montage position, caption/title, and matching checksum.
5. If hashes differ, preserve the new bytes separately and classify them as alternate crop/export, improved copy, or genuinely distinct shot.

## Corrections that create an editorial relationship

When a user's clarification changes why a scene matters, update both scenes and their transition.

- Award plaques followed by ordinary tea can become setup/payoff: “In the guides — Michelin…” → “…and for us — tea.” Do not claim a Michelin star unless the sign actually says so or another reliable source confirms it.
- A tram detail noticed later, such as riders on the rear step, belongs in the existing scene record and can sharpen the title. Do not append a duplicate scene.
- A personal disappointment such as an underground funicular revealing no views is valuable first-person travel context. Preserve it as the user's observation and use it as a light punchline, not as a universal evaluation of the transport.

## Signage-based captions

Visible signs can anchor concise wordplay and exact names, but separate transcription from inference:

- Record only text that is actually legible.
- A partial brand sign can support a playful caption, while location/building identity remains separately qualified.
- Guide/award plaques prove the displayed guide and year, not necessarily a star, ranking, or award class.
- If exact place identity is unreadable, use the user's label and mark it user-provided rather than upgrading it to visually confirmed.

## Response pattern

For ongoing intake, answer with only the delta:

- archived or updated;
- stable material number and short title;
- corrected montage position or scene relationship;
- one concise title/caption when useful.

Do not repeat paths, metadata tables, or the full archive state unless requested.
