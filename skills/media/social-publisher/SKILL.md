---
name: social-publisher
description: Publish an already verified media package to YouTube, Telegram Stories, or Instagram through official APIs after explicit publication and audience gates. Use for OAuth setup, platform adapters, upload verification, and publish records; never for story composition.
version: 1.0.0
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
python3 <skill-dir>/scripts/publish_youtube.py \
  --video <package-dir>/reel-short.mp4 \
  --title-file <package-dir>/youtube-title.txt \
  --description-file <package-dir>/youtube-description.txt \
  --tags-file <package-dir>/youtube-tags.txt \
  --verification <package-dir>/verification.json \
  --audience {contacts,everyone,link} \
  --approved
```

Read `references/youtube-oauth-setup.md`, `references/youtube-publish-verification.md`, and `references/youtube-short-thumbnails.md`. API acceptance is not final verification: poll processing, read metadata/tags back, and check the intended public surface when applicable.

## Telegram Stories

Use a personal user session, not the ordinary Hermes bot connection. Run:

```bash
python3 <skill-dir>/scripts/setup_telegram_user.py
python3 <skill-dir>/scripts/publish_telegram_story.py <package-dir> \
  --audience {contacts,everyone,link} \
  --approved
```

`link` performs no Telegram write. The publisher verifies the exact Story MP4 hash and format before upload. Read `references/telegram-stories.md` and `references/telegram-user-api-kubernetes.md`.

## Instagram

Use the official container workflow through `scripts/publish_instagram.py`. Meta must fetch media from a user-approved reachable HTTPS URL; do not upload it to an arbitrary host. Preparation stops locally when no safe hosting destination exists. The publisher downloads the remote asset first and requires its hash to equal the green local verification report:

```bash
python3 <skill-dir>/scripts/publish_instagram.py \
  --video <package-dir>/reel-short.mp4 \
  --video-url <approved-https-url> \
  --verification <package-dir>/verification.json \
  --caption-file <package-dir>/instagram-caption.txt \
  --approved
```

## Credentials

Credentials come only from environment variables, mode-600 credential files, or an external secret store. Never put tokens, passwords, cookies, client secrets, full API responses, or user-session files into a story manifest, skill text, Git, chat, or publish record. Read `references/oauth-account-setup.md` before handling credential-bearing attachments.

## Result and failure handling

- Record only platform, timestamp, returned ID/URL, exact media SHA-256, and visibility.
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
