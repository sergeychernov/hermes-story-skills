# Telegram Stories

## What the user means

Telegram Stories are full-screen vertical posts shown as avatars at the top of Telegram. They are not `sendVideoNote` circles in a chat.

## Media preparation

For the Bot API `InputStoryContentVideo` compatibility target, render:

- 720×1280 (9:16);
- H.264/AVC video (`avc1`) in streamable MP4; MTProto `stories.sendStory` rejected HEVC/H.265 with `MEDIA_FILE_INVALID` during a verified upload attempt;
- a keyframe every second;
- AAC audio;
- duration 0–60 seconds;
- size no more than 30 MiB.

Use `scripts/build_telegram_story.py <episode-dir>` when the approved master is no longer than 60 seconds. The input is the approved `reel-short.mp4`, so narrative order, captions, reframing, and approved music remain identical. Story privacy is publication metadata, not a render property.

## Long vertical edits as a Story sequence

Telegram does not have a separate Reels object. What looks like a long Reel split into bars is normally a sequence of independent Stories that auto-advance in the viewer.

When the approved vertical master exceeds 60 seconds, explicitly offer two deliverables rather than silently discarding material:

1. **Editorial single Story:** one condensed cut of at most 60 seconds, with weaker stills or redundant beats removed while complete spoken phrases remain intact.
2. **Full multi-part sequence:** split the complete master into several Stories, each at most 60 seconds.

For a multi-part sequence:

- choose split points at canonical scene boundaries, natural pauses, or chapter changes; never cut mechanically at 60.000 seconds—or at an exact 30-second target—when that would break speech, music, a caption, or a narrative unit;
- treat the requested duration as a soft target and semantic coherence as the hard rule. Uneven parts such as 28/25/33 seconds are preferable to equal parts with a weak or misleading boundary;
- group setup/action scenes with the event they semantically introduce, not merely with the preceding chronology. For example, “walking to the venue” and “venue entrance” belong at the start of the concert chapter, alongside the performance, rather than at the end of a sightseeing chapter;
- validate each proposed chapter with a one-line synopsis before rendering. If the synopsis needs “and then, unrelated…” or leaves an event setup in the prior part, move the boundary;
- prefer a slightly shorter first part when a strong scene boundary occurs just before the target or platform limit;
- render scene segments once, then concatenate complete segments into each part so captions, framing, audio, and approved music remain identical to the master;
- route generated melody/rhythm from canonical metadata **before** splitting. A `content_type: music` scene should remain wholly inside one part, with both generated stems muted throughout;
- name and record every part deterministically (`telegram-story-01.mp4`, `telegram-story-02.mp4`, …), including ordered scene indices, duration, size, and SHA-256;
- probe and fully decode every part; each must independently satisfy the Story codec, geometry, keyframe, size, and duration constraints;
- treat each part as a separate Story post with its own Story ID, statistics, reactions, and active slot. API publication therefore requires one `stories.sendStory`/`postStory` call per part;
- call `stories.canSendStory` before the sequence and account for the number of available active Story slots. On a partial or ambiguous failure, query current Stories before retrying so a sequence is not duplicated;
- apply the same explicitly approved audience and active period to every part. One approval covers the named, previewed sequence only; changing part boundaries or content makes that approval stale.

The official client may offer interactive slicing, but API automation must prepare and upload every fragment explicitly. Declare the approved semantic groups in the canonical manifest and use the reusable builder:

```json
{
  "telegram_story": {
    "max_duration_seconds": 60,
    "sequence": {
      "target_duration_seconds": 30,
      "clip_groups": [[1, 2, 3], [4, 5], [6, 7, 8]]
    }
  }
}
```

```bash
python3 scripts/build_telegram_sequence.py <episode-dir>
```

The script requires complete, non-overlapping, canonical-order coverage, concatenates whole rendered scene segments, transcodes each part to Story format, fully decodes it, enforces duration/size limits, and writes `telegram-sequence-build.json` with ordered indices, durations, sizes, and hashes. Deliver all numbered video previews plus a sequence contact sheet or boundary preview so the user can verify continuity before publication.

## Official publication paths

### Personal account with explicit audience

Create an API application at https://my.telegram.org/apps, then authorize once on the trusted host (never paste credentials or login codes into chat):

```bash
BASE="$HOME/.hermes/telegram-user"
mkdir -p "$BASE" && chmod 700 "$BASE"
uv venv "$BASE/.venv"
uv pip install --python "$BASE/.venv/bin/python" 'telethon>=1.40,<2' 'python-socks[asyncio]>=2.7,<3'
"$BASE/.venv/bin/python" <skill-dir>/scripts/setup_telegram_user.py
```

Telethon opens raw MTProto TCP and does **not** automatically honor `ALL_PROXY`. The setup and publisher therefore pass an explicit proxy tuple parsed from `TELEGRAM_PROXY` (preferred) or `ALL_PROXY`. In the k3s homelab use the internal Service route:

```bash
export TELEGRAM_PROXY=socks5://xray.xray.svc.cluster.local:10808
```

Do not use the LAN `hostPort` address from inside the pod when the cluster Service is available.

The setup stores `credentials.env` and `user.session*` under `$HOME/.hermes/telegram-user/` with restricted permissions. **Do not infer that Telegram Stories are unconfigured merely because top-level `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` environment variables are absent**: the publisher intentionally reads `<TELEGRAM_USER_HOME>/credentials.env`. Check the configured base directory (for this host, `/opt/data/.hermes/telegram-user`) and authorized session first. If Hermes runs in Kubernetes, first distinguish the host filesystem from the pod/PVC: a helper created at a pod path is invoked from the host through `kubectl exec -it`, not as a host-local executable. Follow `references/telegram-user-api-kubernetes.md` and derive namespace, workload, and container from manifests or live cluster state before presenting the command.

Then use Telegram's user MTProto API. Publication targets are an explicit registry, not a hard-coded peer:

```bash
# Discover the personal account and every channel/supergroup Telegram currently permits.
"$BASE/.venv/bin/python" <skill-dir>/scripts/manage_telegram_channels.py list --all

# Add an eligible channel to the stable publication choices.
"$BASE/.venv/bin/python" <skill-dir>/scripts/manage_telegram_channels.py \
  add travel @channel_username --label "Travel channel"

# List the choices before every publication, or remove one later.
"$BASE/.venv/bin/python" <skill-dir>/scripts/manage_telegram_channels.py list
"$BASE/.venv/bin/python" <skill-dir>/scripts/manage_telegram_channels.py remove travel
```

The registry is stored at `<TELEGRAM_USER_HOME>/channels.json` with mode 0600. It stores only stable keys, labels, IDs, and usernames—not session material or API credentials. A registered channel is still rejected if it disappears from the live `stories.getChatsToSend` result.

Before publishing, present all available registered targets as a selectable choice. Never infer a target from the previous publication. Then:

1. resolve the selected key: `self` maps to `inputPeerSelf`; a channel key must map to an `inputPeerChannel` returned by `stories.getChatsToSend`;
2. call `stories.canSendStory(selectedPeer)`;
3. upload `telegram-story.mp4` using `upload.saveFilePart` and return a regular `inputFile`, even above 10 MiB;
4. require the explicit publication audience and call `stories.sendStory` with the selected peer: personal `self` supports contacts/everyone; registered channels are public and require everyone;
5. for personal `self` plus **по ссылке**, do not call Telegram at all: Telegram Stories have no link-only/unlisted privacy mode; report the target as deliberately skipped;
6. record only target key/ID, story ID, timestamp, media hash, expiry period, and privacy label.

Official clients force non-big file parts for Story uploads (`forceNoBigParts: true`). Telethon normally switches files above 10 MiB to `inputFileBig`, which Telegram rejects for this Story path with `MEDIA_FILE_INVALID`; do not use the default large-file upload here.

After the explicit **«публикуй»** command, run:

```bash
"$BASE/.venv/bin/python" <skill-dir>/scripts/publish_telegram_story.py \
  <episode-dir> --channel self --audience contacts --approved

# Or, after the user explicitly chooses «для всех»:
"$BASE/.venv/bin/python" <skill-dir>/scripts/publish_telegram_story.py \
  <episode-dir> --channel self --audience everyone --approved

# «По ссылке» is a safe no-op for Telegram and returns a structured skip result:
"$BASE/.venv/bin/python" <skill-dir>/scripts/publish_telegram_story.py \
  <episode-dir> --channel self --audience link --approved

# A registered channel Story is public to that channel's audience:
"$BASE/.venv/bin/python" <skill-dir>/scripts/publish_telegram_story.py \
  <episode-dir> --channel travel --audience everyone --approved
```

The publisher requires a green `verification.json`, recomputes the media hash, validates the Story format, checks available Story slots, and refuses to run without `--approved`.

This is the deterministic route for personal-account Stories with either contacts-only or public visibility. The gateway's normal Telegram bot connection is not a personal user session and cannot call user MTProto methods.

### Managed Telegram Business account

Bot API `postStory` can post on behalf of a connected managed business account when the bot has `can_manage_stories`. It requires `business_connection_id`. Its request does not expose story `privacy_rules`; therefore do not claim contacts-only audience unless the actual account behavior has been tested and verified. Media requirements above come directly from Bot API `InputStoryContentVideo`.

## Approval and safety

- Preparation and preview do not authorize publishing.
- Publish only after explicit **«публикуй»**.
- List and ask for the publication target before every publication. Never reuse an older target silently.
- For `self`, ask **«для своих контактов / для всех / по ссылке?»** unless the user already gave that explicit choice for the current approval. A channel target has only the public/everyone mode.
- Treat **«по ссылке»** as a deliberate Telegram skip; never turn it into a public Story merely to produce a URL.
- Before the first real story for each supported audience, perform an audience-controlled test when possible and verify it from a separate account.
- Never store `api_hash`, confirmation codes, 2FA password, session material, bot token, or business connection payloads in manifests or chat logs.
- Run `stories.canSendStory` immediately before an MTProto publication.
- On ambiguous network failure, query current stories before retrying to avoid duplicates.

## Official sources

- User/channel MTProto Stories: https://core.telegram.org/api/stories
- Bot API `postStory`: https://core.telegram.org/bots/api#poststory
- Bot API story video constraints: https://core.telegram.org/bots/api#inputstorycontentvideo
