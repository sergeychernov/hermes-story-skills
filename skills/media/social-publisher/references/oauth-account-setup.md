# OAuth credential handoff and account binding

Use this cross-platform reference whenever a social publisher is being connected to a user's account. Provider-specific console steps belong in their own references, such as `youtube-oauth-setup.md`.

## Interaction style

When the user is navigating an OAuth console, guide one visible screen at a time: name the exact control to click, give only the fields needed on that screen, then wait for the next screenshot. Account authorization is setup only; it never satisfies the separate **«публикуй»** approval gate.

## Secret-handling invariant

- Never ask the user to paste or upload downloaded OAuth JSON, client secrets, authorization codes, refresh tokens, or access tokens into chat.
- A client ID may be visible, but a downloaded OAuth JSON normally contains credential-bearing fields.
- Preferred handoff: direct SSH/SFTP into a protected directory, Bitwarden Secrets Manager, 1Password, or another external secret store. Store outside the skill, archive, manifest, episode directory, and publish record.
- Derive `$HERMES_HOME`; do not hardcode another profile's paths. A local secret directory should be `0700`, and files should be `0600`.
- Never reproduce a credential from conversation context into a tool argument, command line, log, summary, skill, or memory.

## Discover the execution boundary before handoff

Before giving an `scp` destination, determine the live `$HERMES_HOME`, runtime UID/GID, and whether Hermes runs directly on the SSH host or inside a container/pod. A path visible inside a pod (for example `/opt/data/...`) may not exist from an SSH login to the host. Do not present an unverified container-internal path as an SSH destination.

For Kubernetes, a reliable pattern is:

1. `scp` the credential only to the SSH user's home directory on the host.
2. Stream it into the pod through stdin so secret content never appears in the command line:

   ```bash
   kubectl -n "$NS" exec -i "$POD" -- sh -c \
     'umask 077; mkdir -p /secure/path; cat > /secure/path/client.json' \
     < "$HOME/client.json"
   ```
3. Determine the actual Hermes runtime UID/GID with `id -u` and `id -g`, then set and verify ownership. A file created by `kubectl exec` may become `root:root` with mode `0600`, making it unreadable to an unprivileged Hermes process even though the mode looks secure.
4. Verify only existence, owner, mode, size, and required JSON key presence; never print credential values.

When desktop OAuth runs inside a pod but the user's browser runs on a laptop, the loopback callback may need two hops: pod port-forward to the SSH host, then SSH local forwarding to the laptop's `localhost`. Keep the callback bound to loopback and use a fixed temporary port.

## If a secret attachment arrives anyway

During an explicit account-connection workflow, **do not print or parse the attachment and do not destroy the only copy before resolving the user's storage intent**.

1. Atomically quarantine the attachment to the intended protected path without displaying contents.
2. Set and verify `0700` on the parent and `0600` on the file; report only path, owner, mode, and checksum if needed.
3. Explain that chat transport exposed the credential and recommend provider-side rotation.
4. Preserve the quarantined copy until either the user explicitly chooses to keep it or a replacement is safely installed and verified.
5. If rotation is chosen, securely remove the old copy only after replacement verification.

This balances incident response with the user's operational intent: quarantine first, rotate second, delete last.

## Account-binding verification

Before any upload:

1. Load credentials through protected environment/secret injection.
2. Check only credential presence, never values.
3. Exchange/refresh tokens without printing them.
4. Make a read-only identity call and report the destination account/channel name and ID.
5. Do not upload media merely to test OAuth. If an upload test is genuinely needed, obtain explicit approval and use the least-visible platform state, typically `private`.
6. Keep the independent **«публикуй»** gate for the prepared package.

## Remote loopback OAuth

Desktop OAuth commonly uses a loopback callback. If the helper runs on a remote NUC while the browser is on the user's computer, use an SSH local port forward to the NUC callback port. Do not use deprecated out-of-band copy/paste flows. Bind the helper only to loopback, validate a random `state`, exchange the code server-side, and never print the refresh token.

## Hermes integration

Social OAuth credentials are not model-provider credentials. Supply them through the publisher's expected environment variables or an external secret manager. After installing or rotating credentials, reload the active environment or restart the Hermes gateway as required by the current surface.

## Completion criteria

Connection is complete only when:

- credentials are protected and available to the publisher process;
- a read-only call identifies the intended destination;
- no secret appears in chat, manifests, scripts, logs, skill files, memory, or publish records;
- no publication occurred as a side effect of setup;
- explicit publication approval is still required.
