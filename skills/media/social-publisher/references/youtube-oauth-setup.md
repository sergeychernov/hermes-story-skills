# YouTube OAuth setup for publishing

Use this when YouTube Data API v3 is enabled but a desired publication channel has no registered OAuth credential profile. For credential quarantine, host-versus-pod path discovery, stdin transfer, UID/GID repair, and remote loopback tunneling, also follow `oauth-account-setup.md`.

## Interaction style

Guide the user **one visible screen at a time**. When they send a screenshot, name exactly one control to click next, describe its location, and wait for the following screenshot. Do not dump the entire Google Cloud setup sequence while they are navigating it.

Never ask the user to paste a client secret, authorization code, access token, or refresh token into chat. OAuth consent and any secret transfer must happen outside the conversation.

## Google Auth Platform flow

Google Cloud's current Auth Platform UI may show these left-navigation items: **Overview, Branding, Audience, Clients, Data Access, Verification Center, Settings**.

1. From **OAuth Overview**, if it says “Google Auth Platform not configured yet,” click **Get started**.
2. Configure app identity/branding with a recognizable internal name and support email.
3. Set the audience. For a personal Google account, use **External** and add the account that owns the target YouTube channel as a test user while the app remains in testing. For a Google Workspace-only deployment, use **Internal** only when the channel-owning account belongs to that organization.
4. Under **Data Access**, request `https://www.googleapis.com/auth/youtube.upload`. Also request `https://www.googleapis.com/auth/youtube.readonly` when the workflow must verify and display the connected channel before publication; `youtube.upload` alone cannot call `channels.list(mine=true)`. Request `https://www.googleapis.com/auth/youtube.force-ssl` when the workflow must update title, description, tags, or other metadata on an existing video; upload/read scopes can otherwise return `403 insufficientPermissions` for `videos.update`.
5. Under **Clients**, create an OAuth client suitable for the one-time authorization helper. Prefer a **Desktop app** client when using a loopback redirect flow.
6. Run `scripts/setup_youtube_oauth.py`, complete OAuth in the browser while signed into the intended Google account, and select the intended YouTube channel. Request offline access so the authorization returns a refresh token. For Hermes in k3s behind an SSH host, chain Mac `ssh -L` to host-side `kubectl port-forward` and the helper's loopback callback. The port-forward may exit with connection reset after the helper successfully receives the one callback and closes its listener; this is expected. The helper must ignore empty health-check or tunnel connections and keep waiting for a callback containing `code` or `error`.
7. Store the resulting values outside the skill and manifests as:
   - `YOUTUBE_CLIENT_ID`
   - `YOUTUBE_CLIENT_SECRET`
   - `YOUTUBE_REFRESH_TOKEN`
8. For each channel, use a separate mode-600 env file, then register and verify it:

```bash
python3 <skill-dir>/scripts/setup_youtube_oauth.py \
  --env-file "${HERMES_HOME:-$HOME}/.hermes/youtube/channels/travel/credentials.env"
python3 <skill-dir>/scripts/manage_youtube_channels.py add travel \
  --label "Travel" \
  --credentials-file "${HERMES_HOME:-$HOME}/.hermes/youtube/channels/travel/credentials.env"
python3 <skill-dir>/scripts/manage_youtube_channels.py list
```

Repeat OAuth with a distinct credentials file for every additional channel. The add command exchanges the refresh token without printing it, queries `channels.list(mine=true)`, and records only the stable key, label, channel ID/title, and credential-file path in `${HERMES_HOME:-$HOME}/.hermes/youtube/channels.json` (mode 600).

9. Before every upload, present the current registry list as a selectable choice and pass the chosen key to `publish_youtube.py --channel <key>`. The publisher re-checks that the OAuth identity matches the selected channel before initiating an upload.

## Important pitfalls

- Enabling YouTube Data API v3 alone is insufficient; OAuth consent, an OAuth client, the upload scope, and account authorization are all required.
- A refresh token still determines one Google account/channel. Multi-channel choice works by selecting an explicitly registered, isolated credential profile—not by redirecting one token to another channel.
- An OAuth app left in **External / Testing** can issue refresh tokens with limited lifetime. For durable unattended publishing, review Google's current publishing-status and verification requirements rather than assuming a test token is permanent.
- Do not use API keys for uploads. YouTube uploads require OAuth 2.0 user authorization.
- Keep first test uploads `private`; switch to `unlisted` or `public` only after verifying the returned video belongs to the intended channel.
- `hermes auth` manages supported model-provider credentials; social publishing credentials are supplied to this skill via environment variables or an external secrets manager.
- If the Google UI differs from this reference, inspect the user's screenshot and map the same concepts instead of insisting on stale labels.

## Verification after setup

Before any real publication:

1. Confirm only the presence—not the values—of all three environment variables.
2. Exchange the refresh token for an access token without printing either token.
3. Query the authorized YouTube account/channel with a read-only API request when practical, and show the channel name to the user.
4. Upload a harmless test video as `private` only with explicit user approval.
5. Record only the resulting video ID/URL and media hash; never record tokens.
