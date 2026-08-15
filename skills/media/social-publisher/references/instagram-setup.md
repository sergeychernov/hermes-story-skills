# Instagram setup for Reels publishing

Use this when Instagram Login is configured but a desired publication account has no registered credential profile. For credential quarantine, host-versus-pod path discovery, stdin transfer, UID/GID repair, and secret-handling invariants, also follow `oauth-account-setup.md`.

## Prerequisites

- An Instagram **professional** account (Business or Creator) connected to the Meta app.
- App permissions **`instagram_business_basic`** (read identity) and **`instagram_business_content_publish`** (publish Reels).
- A **public HTTPS URL** where Meta can fetch the exact verified MP4. The publisher rejects localhost, private/reserved IPs, embedded credentials, URL fragments, and unsafe redirect targets. Preparation/auth do **not** authorize publishing.

## Interaction style

Guide the user **one visible screen at a time**. When they send a screenshot, name exactly one control to click next, describe its location, and wait for the following screenshot.

Never ask the user to paste an access token, authorization code, or app secret into chat. Token exchange and storage must happen outside the conversation.

## Meta developer setup (screen-by-screen)

1. **developers.facebook.com → My Apps → Create App.** Choose a use case that supports Instagram API with Instagram Login (Business type).
2. **Add product → Instagram → API setup with Instagram login.** Connect the target professional Instagram account when prompted.
3. **App roles / testers:** while the app is in development, add the Instagram account owner as a tester and accept the invite in the Instagram app if required.
4. **Permissions:** request **`instagram_business_basic`** and **`instagram_business_content_publish`**. Submit for review before production traffic if the app is not in dev/test mode.
5. **Generate a long-lived token** through the documented Instagram Login / token exchange flow for the target account. Store it only in a protected mode-600 env file — never in chat, Git, manifests, or publish records.
6. **Record the Instagram user ID** returned by the identity endpoint alongside the token. The registry add command verifies they match.

## Credential file layout

Create one mode-600 env file per account under a mode-700 directory:

```bash
INSTAGRAM_DIR="${INSTAGRAM_HOME:-${HERMES_HOME:-$HOME/.hermes}/instagram}"
mkdir -p "$INSTAGRAM_DIR/accounts/travel"
chmod 700 "$INSTAGRAM_DIR" "$INSTAGRAM_DIR/accounts" "$INSTAGRAM_DIR/accounts/travel"
cat > "$INSTAGRAM_DIR/accounts/travel/credentials.env" <<'EOF'
INSTAGRAM_ACCESS_TOKEN=...
INSTAGRAM_USER_ID=...
INSTAGRAM_API_VERSION=v24.0
EOF
chmod 600 "$INSTAGRAM_DIR/accounts/travel/credentials.env"
```

`INSTAGRAM_API_VERSION` is optional; when omitted the publisher defaults to `v24.0`. Use the form `vNN.N` only.

## Register and verify the account

The add command performs a **read-only** identity call and verifies the returned account ID matches `INSTAGRAM_USER_ID` before writing the registry:

```bash
python3 <skill-dir>/scripts/manage_instagram_accounts.py add travel \
  --label "Travel frog" \
  --credentials-file "$INSTAGRAM_DIR/accounts/travel/credentials.env"
python3 <skill-dir>/scripts/manage_instagram_accounts.py list
```

`list` prints only key, label, user ID, and username — never tokens or credential paths.

### Migrating legacy environment credentials

When `--account` is omitted, `publish_instagram.py` still reads `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`, and optional `INSTAGRAM_API_VERSION` from the environment. Register the same profile without reauthorizing:

```bash
LEGACY_ENV="${HERMES_HOME:-$HOME/.hermes}/.env"
python3 <skill-dir>/scripts/manage_instagram_accounts.py add current \
  --label "Current account" --credentials-file "$LEGACY_ENV"
```

New agent-driven publication must list accounts and pass `--account <key>` explicitly.

## Identity test (read-only)

Before any real publication:

1. Confirm only the **presence** — not values — of token and user ID env vars or credential files.
2. Run `manage_instagram_accounts.py add` or `list` to verify the intended username and user ID.
3. Do **not** publish media merely to test OAuth. Preparation and auth do not satisfy the separate **«публикуй»** gate.

Example manual identity check (do not paste tokens into chat):

```bash
curl -s "https://graph.instagram.com/v24.0/me?fields=id,username&access_token=${INSTAGRAM_ACCESS_TOKEN}"
```

Compare the returned `id` to `INSTAGRAM_USER_ID`.

## Approved public HTTPS hosting

Instagram fetches the video from `--video-url`. Requirements:

- Public **HTTPS** only; no credentials in the URL; no `#fragment`.
- Use a DNS hostname, not a literal IP address. Every DNS answer must be public; private, loopback, link-local, multicast, and reserved addresses are rejected again at connect time.
- Each connection and redirect hop re-resolves DNS, validates public A/AAAA, and connects to a pinned public IP while preserving TLS SNI and the HTTP `Host` header. Environment proxies are disabled for this untrusted fetch.
- Redirects are followed; each hop must pass the same checks.
- Remote body must match the verified local MP4 SHA-256 (max 300 MiB; `Content-Type: video/mp4` when present).

Upload the verified file to an approved CDN or object store the user controls. Do not host on arbitrary or unreviewed endpoints.

## Token rotation and revocation

- Rotate tokens in the provider console when exposure is suspected; update the mode-600 credential file atomically.
- Revoke old tokens at Meta after the replacement identity check succeeds.
- Re-run `manage_instagram_accounts.py add` after rotation if the user ID changed (it should not for the same account).
- Never log, echo, or store tokens in publish records, skill text, or chat.

## Publication verification and ambiguous retries

After `--approved` publication:

1. After `media_publish` returns a media ID, the publisher writes a mode-600 provisional target-specific record (`instagram-publish-<key>.json` or legacy `instagram-publish.json`) with `media_id` and null `permalink`/`timestamp`.
2. Exact read-back requires the returned `id` to equal the published `media_id`, `media_type` `VIDEO`, `media_product_type` `REELS`, a non-empty HTTPS `permalink`, non-empty `timestamp`, and exact `username` and `caption`.
3. On success the provisional record is atomically replaced with verified `permalink` and `timestamp` from read-back. Record fields stay limited to platform, target key/id/username, timestamp, media_id/permalink, media SHA-256, caption SHA-256, and visibility.
4. Before any Instagram write, duplicate detection inspects the canonical target-specific record and every `instagram-publish*.json` in the video package directory. Malformed candidate records fail closed. An optional `--record` write destination must remain in that same directory and its name must match `instagram-publish[-key].json`, so later runs always discover it. A provisional record from a prior ambiguous run blocks blind retry.
5. Token-bearing Graph API GET/POST calls use a no-redirect opener; HTTP 301/302/307/308 fail without forwarding query, body, or `access_token`.
6. On timeout or ambiguous failure after container creation or `media_publish`, read the safe JSON exit payload (`container_id`, `media_id`, `published`, `ambiguous`) and query Instagram state before retrying.

## Important pitfalls

- A personal (non-professional) Instagram account cannot publish through this API.
- Instagram has no contacts/link visibility mapping like YouTube or Telegram Stories.
- API acceptance of a container is not final verification; the publisher polls status, read-backs caption and media product type, and treats any failure after `media_publish` as ambiguous.
- If the Meta UI differs from this reference, map the same concepts from the user's screenshot instead of insisting on stale labels.
