---
name: social-publisher
description: Publish an already verified media package to YouTube, Telegram Stories, or Instagram through official APIs after explicit publication and audience gates. Use for OAuth setup, platform adapters, upload verification, and publish records; never for story composition.
version: 1.3.0
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

Before every network write require all of the following:

1. `verification.json` is green and its hashes match the current files.
2. The package has not changed since preview/approval.
3. The exact media, title, description, tags/caption, cover, and targets were shown.
4. The user explicitly said **«публикуй»** or an equally unambiguous command naming the target.
5. For YouTube or Telegram, the user explicitly chose one current audience: **для своих контактов**, **для всех**, or **по ссылке**.

Never infer approval from “собери”, “подготовь”, “покажи”, media uploads, or an old package.

## Audience mapping

| User choice | YouTube | Telegram Story |
|---|---|---|
| Для своих контактов | `private` | contacts |
| Для всех | `public` | everyone |
| По ссылке | `unlisted` | deliberately skip; link-only Stories do not exist |

Approval and audience are separate gates.

## YouTube

Require a verified video, reviewed non-empty tag file, exact metadata, and an approved platform-fit cover. Run:

```bash
python3 <skill-dir>/scripts/manage_youtube_channels.py list
python3 <skill-dir>/scripts/publish_youtube.py \
  --channel <selected-key> \
  --video <package-dir>/reel-short.mp4 \
  --cover <package-dir>/youtube-cover.jpg \
  --title-file <package-dir>/youtube-title.txt \
  --description-file <package-dir>/youtube-description.txt \
  --tags-file <package-dir>/youtube-tags.txt \
  --verification <package-dir>/verification.json \
  --audience {contacts,everyone,link} \
  --approved
```

Before every agent-driven YouTube publication, list the registered channels, present them as a selectable choice, and pass the selected key. Never silently reuse the previous channel. Each key maps to its own mode-600 OAuth credentials file; the publisher verifies `channels.list(mine=true)` matches the selected registered channel before upload. For compatibility only, legacy callers may omit `--channel` and keep using the three existing `YOUTUBE_*` environment variables; migrate them with the command in `references/youtube-oauth-setup.md`. Read `references/youtube-oauth-setup.md`, `references/youtube-publish-verification.md`, and `references/youtube-short-thumbnails.md`. API acceptance is not final verification: poll processing, read metadata/tags back, upload the verified cover through `thumbnails.set`, and check the intended public surface when applicable. The Shorts-grid frame is a separate manual surface; the Data API cannot verify it.

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
