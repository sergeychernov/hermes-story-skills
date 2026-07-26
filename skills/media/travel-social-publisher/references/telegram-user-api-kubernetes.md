# Telegram user API inside Kubernetes

Use this when the media workflow runs inside a pod but the user opens a shell on the Kubernetes host.

## Execution-boundary checklist

1. Identify where the helper was actually created: host filesystem, container image layer, or mounted PVC.
2. Verify the helper **inside that same execution context** before giving the user a command.
3. Confirm namespace, workload, and container from live manifests or cluster state; do not infer them only from a hostname.
4. Keep the helper, credentials, and MTProto session on persistent storage. An image-layer or `emptyDir` path is unsuitable for the session.
5. Run interactive authorization through an attached TTY:

```bash
sudo k3s kubectl -n <namespace> exec -it deploy/<deployment> -c <container> -- \
  <persistent-path>/setup
```

If the host already has a configured `kubectl`, `kubectl ...` may replace `sudo k3s kubectl ...`.

6. Enter `api_id`, `api_hash`, phone, OTP, and 2FA password only in that terminal. Never put them in chat or ordinary command arguments.
7. Return only a redacted authorization result (`authorized`, account ID/username if acceptable, and capability status).

## Important distinction

A host-side `No such file or directory` does **not** prove that a path is absent from the pod. It only proves that the host shell cannot resolve it. Conversely, a file verified inside the pod must not be presented as a directly executable host path.

## Verification

After authorization, run a non-publishing capability check inside the same pod and verify:

- session file exists on the persistent volume;
- file permissions are restrictive;
- `get_me` succeeds without printing the phone number;
- `stories.canSendStory(inputPeerSelf)` succeeds;
- no Story was published during setup.

Actual publication remains behind the separate explicit **«публикуй»** approval gate.