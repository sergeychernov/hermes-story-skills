# YouTube publication verification

Use this after the user has explicitly approved a YouTube publication. OAuth setup and account binding are covered by `youtube-oauth-setup.md`; credential handling is covered by `oauth-account-setup.md`.

## Preflight before the write

1. Require the user-facing audience choice **для своих контактов / для всех / по ссылке** for this publication. Map it to `private` / `public` / `unlisted`; do not use a default. Clarify that YouTube `private` means explicitly invited Google accounts, not the user's phone or Telegram contacts.
2. Resolve the **exact file path that will be uploaded** before any hash or API work. If the user reviewed a delivery transcode, require it to be a derivative of the same approved canonical master; do not silently upload an older master or a visually different full-resolution file.
3. Resolve `verification_file` from the exact eligible video report and require its declared video SHA-256 to match the upload bytes. Ad-hoc decode checks or manifest notes do not replace this report.
4. Resolve `cover_verification_file` from the report that marks the selected artifact as a user-approved YouTube `standard_api_thumbnail`; require its declared output SHA-256 to match the cover bytes. Never infer freshness from mtime.
5. Bind both reports, the video, cover, and all metadata files into the immutable approval manifest. Immediately before OAuth, snapshot every artifact once, rehash those exact bytes against the manifest, and consume only those snapshots. Any mismatch is a **hard stop**. The cover must also be a real JPEG or PNG validated by bytes, at most 2 MiB.
6. Confirm title and description files are non-empty.
7. Confirm credential presence without printing values.
8. Refresh OAuth and identify the destination channel through a read-only API call. Do not upload merely to test credentials.

## Upload exactly once

List the registered targets, ask the user to choose one, record all decisions under `story.publication.targets.youtube`, complete `references/youtube-metadata-preflight.md`, and run `scripts/publish_youtube.py` exactly once with required `--story`, required `--metadata-preflight`, and `--approved`. Do not pass media or metadata as independent CLI parameters. The publisher validates the story against `youtube-publication.schema.json`, verifies the schema-bound manifest and selected OAuth channel before upload, and maps `contacts` → `private`, `everyone` → `public`, and `link` → `unlisted`.

Immediately before `videos.insert`, the publisher creates a private immutable `youtube-upload-attempt-<identity>.json`. If session creation, media upload, or response parsing is ambiguous, it returns `do_not_retry=true` and leaves that journal in place. A repeated command for the same approved package is rejected. First resolve the attempt through YouTube API readback; never delete or bypass the journal merely to retry.

## Processing is part of completion

A successful `videos.insert` response can arrive while YouTube still reports:

- `status.uploadStatus = uploaded`
- `processingDetails.processingStatus = processing`

Do not report the publication as complete yet. Poll `videos.list` with `part=snippet,status,processingDetails` for the returned video ID until:

- `status.uploadStatus = processed`; and
- `processingDetails.processingStatus = succeeded`.

Use bounded polling. If processing becomes `failed` or `terminated`, or upload status becomes `failed`, `rejected`, or `deleted`, stop and report the provider's safe error fields without retrying the upload.

## Cover thumbnail via API

After processing/read-back succeeds and **before** playlist insertion or success output, upload the verified cover through `POST https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=...&uploadType=media` with the correct MIME type, bearer token, and content length. Require a `youtube#thumbnailSetResponse` with a non-empty `items` array.

If thumbnail upload fails after the video is already uploaded and read-back verified, do **not** retry the video upload. Report safe JSON with `video_uploaded=true` and `thumbnail_uploaded=false`, plus the known video ID/URL.

The **Shorts-grid frame** is a separate manual surface in YouTube Studio. The Data API cannot set or verify it; treat `thumbnails.set` as verification of the standard watch-page thumbnail only.

## Final verification

After processing succeeds, verify through the API:

- returned ID matches the requested video;
- exact title matches the prepared title;
- `privacyStatus` matches the user's explicit choice;
- processing and upload states are successful;
- the cover thumbnail upload returned `youtube#thumbnailSetResponse` with items.

For `public` publication, also open the returned watch URL and verify that the public page resolves to the expected title. Treat the API as authoritative for processing state; page availability alone is not enough.

## Replacement uploads

When the approved package is explicitly a replacement (for example, its manifest contains `replaces_youtube_id`, the draft was presented as a replacement, and the user then says **«публикуй»**), complete the whole replacement lifecycle rather than silently leaving two public copies:

1. Upload and fully verify the new video first. Never delete the working old publication before the replacement has reached `processed` / `succeeded` and its public page resolves.
2. Re-query the old ID through the API and require its channel ID to match the configured destination channel. Also compare its title or publish record so the deletion target is unambiguous.
3. Unless the user explicitly asked to keep both versions, delete the old ID through the official API only after the new one is verified.
4. Verify through `videos.list` that the old ID is absent and the new ID remains present with the requested visibility.
5. Record the deletion timestamp, old ID, API status, and replacement ID in a separate deletion record; do not rewrite history in the old publish record.

If replacement intent or the old ID is ambiguous, ask before uploading. Do not default to “leave the old one untouched” after an approved, clearly marked replacement; that creates the duplicate the replacement workflow was intended to avoid.

## Publish record

Only after successful verification, write immutable `publish-record-<video_id>.json` with:

- platform;
- UTC timestamp;
- video ID and URL;
- uploaded media SHA-256;
- cover path and SHA-256;
- visibility.

Never include OAuth tokens, client secrets, full API responses, or authorization codes.
