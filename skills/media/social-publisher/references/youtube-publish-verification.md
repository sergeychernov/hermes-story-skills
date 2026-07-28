# YouTube publication verification

Use this after the user has explicitly approved a YouTube publication. OAuth setup and account binding are covered by `youtube-oauth-setup.md`; credential handling is covered by `oauth-account-setup.md`.

## Preflight before the write

1. Require the user-facing audience choice **для своих контактов / для всех / по ссылке** for this publication. Map it to `private` / `public` / `unlisted`; do not use a default. Clarify that YouTube `private` means explicitly invited Google accounts, not the user's phone or Telegram contacts.
2. Resolve the **exact file path that will be uploaded** before any hash or API work. If the user reviewed a delivery transcode, require it to be a derivative of the same approved canonical master; do not silently upload an older master or a visually different full-resolution file.
3. Recompute that exact upload file's SHA-256 and require it to equal the path and hash in the current green `verification.json`. Ad-hoc decode checks, manifest notes, or a hash recorded only under `full_preview` do not replace package verification.
4. Require `verification.json` to be newer than the manifest, the exact upload file, and all selected-source changes. A mismatch or stale record is a **hard stop**: regenerate verification before calling `videos.insert`, never repair the record after publication.
5. Confirm title and description files are non-empty.
6. Confirm credential presence without printing values.
7. Refresh OAuth and identify the destination channel through a read-only API call. Do not upload merely to test credentials.

## Upload exactly once

List the registered targets, ask the user to choose one, then run `scripts/publish_youtube.py` once with the approved media, metadata, required `--channel <selected-key>`, and required `--audience {contacts,everyone,link}`. Capture the returned channel, video ID, and URL. The script verifies the selected OAuth channel before upload and maps `contacts` → `private`, `everyone` → `public`, and `link` → `unlisted`.

If the request fails after upload initiation or the response is ambiguous, do **not** immediately retry. First query YouTube for the returned/known ID or otherwise rule out an already-created video. A blind retry can create a duplicate.

## Processing is part of completion

A successful `videos.insert` response can arrive while YouTube still reports:

- `status.uploadStatus = uploaded`
- `processingDetails.processingStatus = processing`

Do not report the publication as complete yet. Poll `videos.list` with `part=snippet,status,processingDetails` for the returned video ID until:

- `status.uploadStatus = processed`; and
- `processingDetails.processingStatus = succeeded`.

Use bounded polling. If processing becomes `failed` or `terminated`, or upload status becomes `failed`, `rejected`, or `deleted`, stop and report the provider's safe error fields without retrying the upload.

## Final verification

After processing succeeds, verify through the API:

- returned ID matches the requested video;
- exact title matches the prepared title;
- `privacyStatus` matches the user's explicit choice;
- processing and upload states are successful.

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

Only after successful verification, write `publish-record.json` with:

- platform;
- UTC timestamp;
- video ID and URL;
- uploaded media SHA-256;
- visibility.

Never include OAuth tokens, client secrets, full API responses, or authorization codes.
