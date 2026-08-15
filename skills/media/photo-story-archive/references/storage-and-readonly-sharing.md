# Storage classes and read-only sharing

Use this note when the user asks where story files live, what is temporary, what should be backed up, or what can be exposed through SMB/NFS.

## Classify by lifecycle

| Class | Typical contents | Treatment |
|---|---|---|
| Authoritative | untouched `photos/`, `videos/`, journal/story manifest, selected titles and editorial state | Preserve and back up; never regenerate destructively |
| Derived but durable | `previews/`, `exports/`, episode renders, QA frames, publication manifests | Keep while under review or published; can often be rebuilt, but may encode an approved revision |
| Rebuildable tooling/cache | `.venv*`, downloaded audio tools, package caches, temporary contact frames | Exclude from sharing/backups when practical; do not delete without approval |
| Ephemeral | system `/tmp`, upload/cache paths before verified archival copy | Never treat as archive or publication source |

A directory may contain mixed lifecycle classes. Inspect the real tree before describing it as wholly permanent or temporary.

## Safe network-sharing boundary

When media needs read-only access over Samba/NFS:

1. Prefer the explicit archive root (for example `~/instagram-drafts/`) rather than the runtime data root or the whole home directory.
2. Keep the export read-only and authenticated by default; avoid guest access unless the user explicitly accepts LAN-wide visibility.
3. Disable traversal outside the share (`follow symlinks = no`, `wide links = no` or protocol equivalent).
4. Audit the selected tree for credentials, histories, hidden runtime state, nested repositories, virtual environments, and downloaded toolchains.
5. Exclude rebuildable hidden/tool directories from the share when possible, but do not imply that hiding them is a security boundary: the share root itself must contain no secrets.
6. Verify from a separate client that files can be read but not created, renamed, or deleted.

Read-only does not make secrets safe: it still permits copying them. Never expose a broad runtime root merely because writes are disabled.
