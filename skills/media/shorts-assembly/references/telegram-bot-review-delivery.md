# Telegram Bot review-video delivery

Use this reference when a verified MP4 must be delivered to the user through the Hermes Telegram bot. This is a review transport, not publication.

## Re-check the external contract

The official source is `https://core.telegram.org/bots/api#sendvideo`. At the time this workflow was established (Bot API 10.x), `sendVideo` documented:

- Telegram clients support MPEG4 videos; other formats may be sent as Document.
- Bots can currently send video files up to 50 MB (50,000,000 bytes in the local preflight).
- Success returns a `Message`.

Treat those values as versioned external facts: re-check the official page when the Bot API changes. An integration layer may impose stricter limits.

## Diagnose before recompressing

Read the active Hermes gateway log for the exact artifact path, normally `/opt/data/logs/gateway.log`.

- `Request Entity Too Large` / `file is too big`: size failure. Create a smaller versioned review derivative with headroom.
- `Timed out`: transport failure. Check proxy connectivity, connect timeout, and media upload timeout. Recompressing an already compliant file is not a fix by itself.
- Any other error: preserve it verbatim in the report and investigate before retrying.

`python-telegram-bot` has a media-specific write timeout separate from ordinary `write_timeout`; its default may be shorter than a proxy-backed upload needs. Configure `HTTPXRequest.media_write_timeout` and, where supported, pass an explicit per-call upload `write_timeout`. Restart a gateway that is still running code/config from before the timeout change.

## Canonical workflow

Run the single skill entrypoint:

```bash
python3 <shorts-assembly-skill-dir>/scripts/deliver_telegram_review_video.py \
  --input <canonical-master.mp4> \
  --derivative-output <versioned-telegram-preview.mp4> \
  --chat-id <telegram-chat-id> \
  --width 720 --height 1280 --review-max-mib 18
```

The 18 MiB review budget controls when to create a lightweight preview; it is not presented as Telegram's official cap. The script:

1. preserves the publication master;
2. invokes `make_review_delivery_copy.py` only when the chosen review budget requires it;
3. validates MP4/H.264/yuv420p and optional AAC, exact decoded frame count, streams and full decode;
4. enforces the current official `sendVideo` cap;
5. classifies the latest exact-artifact gateway failure;
6. discovers live gateway credentials/proxy without recording secrets;
7. uses explicit connect/read/media-write timeouts and bounded retry;
8. succeeds only when Telegram returns `message_id`;
9. writes an atomic report with `review_only: true` and `publication_eligible: false`.

Use `--dry-run` for local preflight without credentials or network writes. Before a real send, separately inspect first/middle/last frames. Never replace the canonical `video_mix` or publication package with the Telegram derivative.

## Success evidence

Local encoding, a clean decode, a returned process exit code, or absence of an immediate UI warning does not prove delivery. The delivery report must contain:

- exact artifact path/hash/bytes;
- official contract provenance;
- timeout values;
- gateway diagnosis;
- `status: delivered`;
- Telegram `message_id`.

Do not repeat an ambiguous send blindly. Query or inspect delivery state first to avoid duplicate messages.
