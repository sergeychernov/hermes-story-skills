---
name: social-publisher
description: Publish an already verified media package to YouTube, Telegram Stories, or Instagram through official APIs after explicit publication and audience gates. Use for OAuth setup, platform adapters, upload verification, and publish records; never for story composition.
version: 1.4.0
author: Sergey Chernov / Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [publishing, youtube, telegram, instagram, oauth, approval, verification]
---

# Social Publisher

## Boundary

Consume an exact, verified media package and perform external platform writes. This skill owns platform adapters, credentials setup, audience mapping, duplicate-risk handling, upload read-back, and minimal publish records.

It must not choose a narrative, reorder scenes, animate photos, rewrite approved text, or treat preparation as permission to publish.

## Hard gates

Before every publication network write require all of the following:

1. The current platform-specific verification reports are eligible and their hashes match the current files.
2. The package has not changed since preview/approval.
3. The exact media, title, description, tags/caption, cover, and targets were shown.
4. The user explicitly said **«публикуй»** or an equally unambiguous command naming the target.
5. For YouTube or Telegram, the user explicitly chose one current audience: **для своих контактов**, **для всех**, or **по ссылке**.
6. A target-specific missing-information preflight is complete: unknown decisions were asked, explicit omissions were recorded where supported, and the exact final publication manifest was shown.

Never infer approval from “собери”, “подготовь”, “покажи”, media uploads, or an old package.

## Missing-information preflight

Before requesting publication approval, inventory every target-specific field and classify it as:

- verified from the exact approved package;
- safe visible default shown in the final summary;
- explicit user decision for this publication revision;
- explicitly omitted when the platform and policy permit omission; or
- unresolved blocker.

Ask the user only about unresolved or policy-sensitive values. Never guess dates, coordinates, target/account, audience, made-for-kids, synthetic-media disclosure, privacy, or other legal/visibility decisions. A sourced candidate is not a confirmed value. Do not silently reuse answers from another package or a stale revision. Any change to media, cover, visible metadata, target, audience, or disclosure invalidates the previous publication approval.

The final summary must show the exact target, audience/privacy, visible text, media and cover, optional date/location decisions, disclosures, subscriber-notification choice when supported, platform settings, and explicit omissions. Do not invoke a publisher until the user gives an unambiguous publication command after seeing that summary.

## Audience mapping

| User choice | YouTube | Telegram Story |
|---|---|---|
| Для своих контактов | `private` | contacts |
| Для всех | `public` | everyone |
| По ссылке | `unlisted` | deliberately skip; link-only Stories do not exist |

Approval and audience are separate gates.

## YouTube

Require a verified video, reviewed non-empty tag file, exact metadata, an approved platform-fit API cover, and a hash-bound metadata preflight. Read `references/youtube-metadata-preflight.md`. All publication parameters live in `story.publication.targets.youtube` and are validated by `templates/youtube-publication.schema.json`; do not create a second decisions file and do not infer required fields in prose.

First list the locally registered channels. If `story.json` already contains a selected channel key, verify that it still exists in the current registry; otherwise ask for a channel choice and save it. For the selected channel, use the read-only playlist command to verify the OAuth identity and fetch `playlists.list(mine=true)`. If the saved exact playlist title still exists in that live result, preserve it; otherwise ask for a playlist choice and save it. Do not repeatedly ask for valid saved values. After resolver/assess succeeds, show one complete summary of all saved publication information and ask one combined question: whether the information is still current and the exact package should be published. A positive answer is the final publication approval. Ask separate field questions only for missing, invalid, ambiguous, or explicitly changed values. No YouTube write endpoint may be called before that combined approval.

```bash
python3 <skill-dir>/scripts/manage_youtube_channels.py list
python3 <skill-dir>/scripts/list_youtube_playlists.py --channel <selected-key>
python3 <skill-dir>/scripts/youtube_metadata_preflight.py resolve \
  --story <package-dir>/story.json \
  --schema <skill-dir>/templates/youtube-publication.schema.json \
  --write
python3 <skill-dir>/scripts/youtube_metadata_preflight.py assess \
  --story <package-dir>/story.json \
  --schema <skill-dir>/templates/youtube-publication.schema.json \
  --locale ru
```

The resolver executes only `x-auto-resolve` rules from the schema. It writes only unique eligible technical paths. Never choose by mtime: `ambiguities` require an explicit package decision, while `blockers` require a missing approval/artifact to be fixed. Ask only entries returned in `questions`; technical path failures are not user questionnaires.

Repeat `resolve` and `assess` after recording answers or approvals. When and only when `ready: true`, show the complete normalized summary and request final publication approval. After that approval, create the immutable manifest exactly as documented in `references/youtube-metadata-preflight.md`, then publish:

For recording date, ask for the date only, never exact shooting time. Accept `YYYY-MM-DD`, `сегодня`, `вчера`, `позавчера`, or a Russian weekday such as `в среду`. Resolve relative wording against the current local date in the event location/timezone with `scripts/normalize_recording_date.py`; a bare weekday means the most recent occurrence, never a future date. Show the resulting `YYYY-MM-DD` in the final manifest.

```bash
python3 <skill-dir>/scripts/publish_youtube.py \
  --story <package-dir>/story.json \
  --schema <skill-dir>/templates/youtube-publication.schema.json \
  --metadata-preflight <package-dir>/youtube-publication-preflight.json \
  --approved
```

Before every agent-driven YouTube publication, list the registered channels and verify the saved `channel_key` against the current registry. Preserve a valid saved key and include the current channel list plus selected channel in the single final summary; ask for a new selection only when the key is missing, invalid, or the user says it changed. Each key maps to its own mode-600 OAuth credentials file; the publisher verifies `channels.list(mine=true)` matches the selected registered channel before upload. For compatibility only, `channel_key=legacy-env` keeps using the three existing `YOUTUBE_*` environment variables; migrate them with the command in `references/youtube-oauth-setup.md`. Read `references/youtube-oauth-setup.md`, `references/youtube-publish-verification.md`, `references/youtube-short-thumbnails.md`, and `references/youtube-metadata-preflight.md`. API acceptance is not final verification: poll processing, read metadata/tags/category/language/status/recording date back, upload the verified cover through `thumbnails.set`, and check the intended public surface when applicable. Deprecated YouTube geo coordinates are never sent; confirmed public location text must occur exactly in the approved description. The Shorts-grid frame is a separate manual surface; the Data API cannot verify it.

**Telegram preview gate after YouTube publication:** when the active delivery channel is Telegram, do not include a clickable YouTube URL in the first success response. Telegram can crawl and cache the exact URL before the user finishes choosing the Shorts cover, and Bot API provides no reliable global URL-cache purge. Report the video ID in non-link form, verify the conventional YouTube CDN/OG thumbnail, let the user finish any owner-facing Shorts cover selection, and release the URL only after an explicit request. If a controlled Telegram share is needed, send the approved cover as a photo and put the URL in its caption rather than relying on an automatic link card; alternatively send text with link preview explicitly disabled. Never claim that deleting a message or adding a query parameter clears Telegram's global cache.

## Telegram Stories

Use a personal user session, not the ordinary Hermes bot connection. Run:

```bash
python3 <skill-dir>/scripts/setup_telegram_user.py
python3 <skill-dir>/scripts/manage_telegram_channels.py list
python3 <skill-dir>/scripts/publish_telegram_story.py <package-dir> \
  --channel <selected-key> \
  --audience {contacts,everyone,link} \
  --approved
```

Before every agent-driven Telegram publication, run `manage_telegram_channels.py list`, present its currently available registered targets as a selectable choice, and pass the selected key. Never silently reuse a previous target. `self` means the authorized personal account; other keys are explicitly registered channels/supergroups. Add eligible channels with `manage_telegram_channels.py add <key> <id-or-@username> --label <label>` and remove them with `manage_telegram_channels.py remove <key>`. The live Telegram `stories.getChatsToSend` result and `stories.canSendStory` check remain authoritative. For compatibility only, legacy callers may omit `--channel`; this maps to `self` and retains `telegram-story-publish.json` alongside the new target-specific record.

Channel Stories require `--audience everyone`; personal-account Stories retain `contacts`, `everyone`, and the safe `link` no-op. The publisher verifies the exact Story MP4 hash and format before upload and writes one target-specific publish record. Read `references/telegram-stories.md` and `references/telegram-user-api-kubernetes.md`.

## Instagram

Use the official Instagram Login container workflow through `graph.instagram.com`. Meta must fetch media from a user-approved reachable public HTTPS URL; do not upload it to an arbitrary host. Preparation stops locally when no safe hosting destination exists. Instagram has no contacts/link audience mapping — Reels publish as public platform content once approved.

Before every agent-driven Instagram publication, run `manage_instagram_accounts.py list`, present the registered accounts as a selectable choice, and pass the selected key. Never silently reuse a previous account. Each key maps to its own mode-600 credential env file; the publisher verifies the live Instagram identity matches the selected registered user ID before any write. For compatibility only, legacy callers may omit `--account` and keep using `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`, and optional `INSTAGRAM_API_VERSION` from the environment; migrate them with the command in `references/instagram-setup.md`.

The publisher downloads the remote asset first (DNS hostname only, pinned public DNS per connection hop, no environment proxies, validating redirects, content type, size, and hash) and requires its SHA-256 to equal the green local verification report. It creates a REELS container, polls processing, publishes exactly once, writes a provisional publish record when `media_id` returns, and read-backs exact id, username, VIDEO/REELS type, HTTPS permalink, caption, and timestamp before finalizing the record. Duplicate detection scans every `instagram-publish*.json` in the package directory before Instagram writes; an optional `--record` must stay in that directory and match `instagram-publish[-key].json`, so it remains discoverable on later runs. After an ambiguous timeout or any failure after container creation or `media_publish`, inspect the safe JSON (`container_id`, `media_id`, `published`, `ambiguous`) and query platform state before retrying — do not blindly republish.

```bash
python3 <skill-dir>/scripts/manage_instagram_accounts.py list
python3 <skill-dir>/scripts/publish_instagram.py \
  --account <selected-key> \
  --video <package-dir>/reel-short.mp4 \
  --video-url <approved-https-url> \
  --verification <package-dir>/verification.json \
  --caption-file <package-dir>/instagram-caption.txt \
  --approved
```

Read `references/instagram-setup.md` for Meta app setup, permission names (`instagram_business_basic`, `instagram_business_content_publish`), long-lived token handling, identity verification, approved public HTTPS hosting, API version configuration, and token rotation. After `media_publish`, a provisional publish record blocks blind retry; read-back must match media ID, VIDEO/REELS, HTTPS permalink, timestamp, username, and caption before the record is finalized. Graph API calls reject redirects. Preparation and OAuth do not authorize publishing.

## Credentials

Credentials come only from environment variables, mode-600 credential files, or an external secret store. Never put tokens, passwords, cookies, client secrets, full API responses, or user-session files into a story manifest, skill text, Git, chat, or publish record. Read `references/oauth-account-setup.md` before handling credential-bearing attachments.

## Result and failure handling

- Record only platform, selected target key/ID, timestamp, returned ID/URL, exact media SHA-256, and visibility.
- Report success per platform; multi-platform publication is not atomic.
- After an ambiguous timeout, query platform state before retrying to avoid duplicates.
- Never delete a previous publication until a replacement upload is processed and verified.
- Missing optional SDKs must fail with an actionable error and no network write.

## Tests

```bash
python3 -m unittest discover \
  -s <skill-dir>/scripts \
  -p 'test_*.py' -v
```

Unit tests do not perform network writes. Real publication remains gated and must return verifiable platform IDs/URLs.
