#!/usr/bin/env python3
"""One-time YouTube OAuth setup without printing or persisting tokens outside Hermes .env."""
from __future__ import annotations

import argparse
import html
import json
import os
import secrets
import stat
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCOPE = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/youtube.force-ssl"
ENV_KEYS = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")


def oauth_default_paths(home: Path) -> tuple[Path, Path]:
    """Return defaults relative to the Hermes home exactly once."""
    return home / "secrets/youtube-client.json", home / ".env"


def build_parser(home: Path) -> argparse.ArgumentParser:
    default_client, default_env = oauth_default_paths(home)
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-json", type=Path, default=default_client)
    parser.add_argument("--env-file", type=Path, default=default_env)
    parser.add_argument("--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timeout", type=int, default=600)
    return parser


def update_env(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replaced: set[str] = set()
    output: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        matched = next((key for key in values if stripped.startswith(key + "=")), None)
        if matched:
            output.append(f"{matched}={values[matched]}")
            replaced.add(matched)
        else:
            output.append(line)
    if output and output[-1] != "":
        output.append("")
    for key in ENV_KEYS:
        if key not in replaced:
            output.append(f"{key}={values[key]}")
    output.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(output))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    finally:
        temp.unlink(missing_ok=True)


def main() -> None:
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    args = build_parser(home).parse_args()

    installed = json.loads(args.client_json.read_text(encoding="utf-8")).get("installed", {})
    required = ("client_id", "client_secret", "auth_uri", "token_uri")
    missing = [key for key in required if not installed.get(key)]
    if missing:
        raise SystemExit("OAuth client JSON is missing: " + ", ".join(missing))

    redirect_uri = f"http://localhost:{args.port}/"
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": installed["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    auth_url = installed["auth_uri"] + "?" + urllib.parse.urlencode(params)
    result: dict[str, str] = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            actionable = bool(query.get("code") or query.get("error"))
            if not actionable:
                message = "YouTube OAuth listener is ready. Return to the authorization link."
                status = 200
            elif query.get("state", [""])[0] != state:
                result["error"] = "OAuth state mismatch"
                message = "Authorization failed: OAuth state mismatch"
                status = 400
            elif "error" in query:
                result["error"] = query["error"][0]
                message = "Authorization failed: " + result["error"]
                status = 400
            else:
                result["code"] = query["code"][0]
                message = "YouTube authorization received. You can close this tab."
                status = 200
            body = ("<!doctype html><meta charset='utf-8'><title>YouTube OAuth</title>"
                    "<style>body{font:20px system-ui;max-width:760px;margin:15vh auto;padding:24px}</style>"
                    f"<h1>{html.escape(message)}</h1>").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer((args.host, args.port), Callback)
    server.timeout = 1
    print("Open this URL in your browser after establishing the localhost tunnel:", flush=True)
    print(auth_url, flush=True)
    print(f"Waiting up to {args.timeout} seconds for OAuth callback on {redirect_uri}", flush=True)
    deadline = time.monotonic() + args.timeout
    while "code" not in result and "error" not in result and time.monotonic() < deadline:
        server.handle_request()
    server.server_close()

    if "code" not in result:
        raise SystemExit("OAuth authorization failed or timed out: " + result.get("error", "no callback"))

    token_body = urllib.parse.urlencode({
        "code": result["code"],
        "client_id": installed["client_id"],
        "client_secret": installed["client_secret"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode("utf-8")
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                installed["token_uri"],
                data=token_body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            ),
            timeout=60,
        ) as response:
            token = json.load(response)
    except urllib.error.HTTPError as exc:
        safe_error = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"Token exchange failed (HTTP {exc.code}): {safe_error}") from None

    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise SystemExit("Google returned no refresh token; revoke prior consent and rerun with prompt=consent")

    update_env(args.env_file, {
        "YOUTUBE_CLIENT_ID": installed["client_id"],
        "YOUTUBE_CLIENT_SECRET": installed["client_secret"],
        "YOUTUBE_REFRESH_TOKEN": refresh_token,
    })
    print(f"YouTube OAuth configured successfully in {args.env_file} (mode 600).", flush=True)


if __name__ == "__main__":
    main()
