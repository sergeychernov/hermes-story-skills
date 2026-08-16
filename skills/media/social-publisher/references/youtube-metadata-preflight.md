# YouTube metadata preflight

Run this process before any YouTube publication write. After the user explicitly selects a registered channel, a read-only OAuth identity check plus `playlists.list(mine=true)` is allowed solely to present exact playlist choices; it does not authorize publication.

## Authoritative inputs

There is no separate decisions file. The complete publication configuration lives at:

```text
<package-dir>/story.json#/publication/targets/youtube
```

`templates/youtube-publication.schema.json` is authoritative for:

- required and optional fields;
- types, enum values, patterns, and conditional requirements;
- safe defaults;
- user-confirmation fields and localized question text;
- deterministic technical artifact resolution through `x-auto-resolve`.

The LLM must not recreate those rules in prose or guess technical paths.

## Resolve technical paths

```bash
python3 <skill-dir>/scripts/youtube_metadata_preflight.py resolve \
  --story <package-dir>/story.json \
  --schema <skill-dir>/templates/youtube-publication.schema.json \
  --write
```

The resolver:

- selects a video only from a `review-ready` or `verified` report with `video.full_decode=passed`; final publication authorization remains the separate hash-bound approval manifest;
- binds `verification_file` to the report that proved the selected video;
- selects a YouTube API cover only from a user-approved `standard_api_thumbnail` report;
- binds `cover_verification_file` to the report that approved the selected API cover;
- resolves exact canonical title, description, and tags files;
- writes only unique eligible relative paths atomically to `story.json`;
- never selects by mtime or filename version.

Interpret `auto_resolution` as follows:

- `resolved`: unique technical fields that can be used or written automatically;
- `ambiguities`: multiple eligible candidates; do not choose silently—resolve the package provenance or ask the user only when it is genuinely a subjective choice;
- `blockers`: no eligible candidate; fix the missing artifact or approval. Do not turn a technical blocker into a user metadata question.

Running `resolve` without `--write` is a read-only dry run.

## Assess

```bash
python3 <skill-dir>/scripts/youtube_metadata_preflight.py assess \
  --story <package-dir>/story.json \
  --schema <skill-dir>/templates/youtube-publication.schema.json \
  --locale ru
```

The command emits `ready`, `missing_fields`, `confirmation_required`, `questions`, `auto_resolution`, and the complete `normalized` config. Ask only returned `questions`, in the user's language. Record answers under `publication.targets.youtube`, rerun `resolve` and `assess`, and do not create an approval manifest while `ready` is false.

User-owned decisions currently include channel, audience, playlist, made-for-kids, synthetic-media disclosure, subscriber notification, recording date or explicit omission, and location text or explicit omission. Fetch playlist choices only after the channel choice with `scripts/list_youtube_playlists.py --channel <key>`; record the exact returned title selected by the user. Safe defaults remain visible in `normalized`. Deprecated YouTube geo coordinates are never sent; confirmed public location text must occur exactly in the approved description.

Recording date is date-only (`YYYY-MM-DD`). Do not ask for a shooting time. For `сегодня`, `вчера`, `позавчера`, or a weekday, run `scripts/normalize_recording_date.py '<phrase>' --timezone <IANA-zone>`; a bare weekday resolves to its most recent non-future occurrence. Record and preview the normalized date, not the free-form phrase. YouTube may read it back as midnight UTC; compare the calendar date.

## Final summary and approval

Show the exact video, API cover, title, full description, tags, channel, playlist, audience/privacy mapping, category, language, date/omit, location text/omit, made-for-kids, synthetic-media disclosure, subscriber notification choice, embedding, license, and statistics visibility. Then request one explicit publication command naming YouTube.

Only after that command create a new immutable approval manifest:

```bash
python3 <skill-dir>/scripts/youtube_metadata_preflight.py approve \
  --story <package-dir>/story.json \
  --schema <skill-dir>/templates/youtube-publication.schema.json \
  --manifest-schema <skill-dir>/templates/youtube-publication-preflight.schema.json \
  --approved-at <timezone-aware-ISO-8601> \
  --approval-note '<brief exact user command reference>' \
  --output <package-dir>/youtube-publication-preflight.json \
  --approved
```

The output is mode 0600, refuses overwrite, and binds SHA-256 of the normalized configuration, publication schema, video, cover, title, description, tags, video verification report, and cover approval report. Any mutation invalidates approval; ask again and create a new manifest rather than editing an approved one.

Publish only with the story and manifest:

```bash
python3 <skill-dir>/scripts/publish_youtube.py \
  --story <package-dir>/story.json \
  --schema <skill-dir>/templates/youtube-publication.schema.json \
  --manifest-schema <skill-dir>/templates/youtube-publication-preflight.schema.json \
  --metadata-preflight <package-dir>/youtube-publication-preflight.json \
  --approved
```

`publish_youtube.py` revalidates schema, re-resolves paths, snapshots and rehashes every manifest artifact before OAuth, consumes those exact bytes, sends only officially writable fields, and reads extended metadata back after processing.
