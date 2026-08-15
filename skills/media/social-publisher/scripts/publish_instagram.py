#!/usr/bin/env python3
"""Publish a verified Reel whose exact MP4 is reachable at an approved HTTPS URL."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from instagram_account_registry import DEFAULT_API_VERSION, credentials_for_account

CAPTION_MAX_LENGTH = 2200
MAX_REMOTE_BYTES = 300 * 1024 * 1024
INSTAGRAM_GRAPH = "https://graph.instagram.com"
API_VERSION_RE = re.compile(r"^v\d+\.\d+$")
LOCAL_HOSTNAMES = frozenset({"localhost", "localhost.localdomain"})
USER_AGENT = "Hermes-Social-Publisher/1.2"


def legacy_environment_credentials(environ=None) -> dict[str, str]:
    environ = os.environ if environ is None else environ
    names = ("INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID")
    missing = [name for name in names if not environ.get(name)]
    if missing:
        raise ValueError("missing environment: " + ", ".join(missing))
    result = {name: str(environ[name]) for name in names}
    if environ.get("INSTAGRAM_API_VERSION"):
        result["INSTAGRAM_API_VERSION"] = str(environ["INSTAGRAM_API_VERSION"])
    return result


def validate_api_version(version: str) -> None:
    if not API_VERSION_RE.fullmatch(version):
        raise ValueError("invalid INSTAGRAM_API_VERSION syntax; expected form vNN.N")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def caption_sha256(caption: str) -> str:
    return hashlib.sha256(caption.encode("utf-8")).hexdigest()


def read_caption(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("caption file must be valid UTF-8") from exc
    if not text:
        raise ValueError("caption must be non-empty")
    if len(text) > CAPTION_MAX_LENGTH:
        raise ValueError(f"caption exceeds the {CAPTION_MAX_LENGTH}-character limit")
    return text


def verify_local_package(video: Path, verification: Path) -> str:
    if not video.is_file():
        raise ValueError(f"video is missing: {video}")
    try:
        report = json.loads(verification.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid verification report: {exc}") from exc
    if report.get("ok") is not True:
        raise ValueError("verification report is not green")
    expected = (report.get("video") or {}).get("sha256")
    actual = file_sha256(video)
    if not expected or expected != actual:
        raise ValueError("video hash does not match verification report")
    return actual


def _hostname_is_literal_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _unsafe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def resolve_host(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"video URL host does not resolve: {host}") from exc
    addresses = sorted({info[4][0] for info in infos})
    if not addresses:
        raise ValueError(f"video URL host does not resolve: {host}")
    return addresses


def validate_public_https_url(url: str, *, resolve: bool = True, resolver=resolve_host) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("video URL must use public HTTPS")
    if parsed.fragment:
        raise ValueError("video URL must not contain a fragment")
    if parsed.username or parsed.password:
        raise ValueError("video URL must not contain embedded credentials")
    host = parsed.hostname
    if not host:
        raise ValueError("video URL must include a hostname")
    host_lower = host.lower().rstrip(".")
    if host_lower in LOCAL_HOSTNAMES:
        raise ValueError("video URL must not target localhost")
    if _hostname_is_literal_ip(host_lower):
        ip = ipaddress.ip_address(host_lower)
        if _unsafe_ip(ip):
            raise ValueError("video URL must not target a private or reserved IP address")
        raise ValueError("video URL must use a DNS hostname, not a literal IP address")
    if resolve:
        for address in resolver(host_lower):
            ip = ipaddress.ip_address(address)
            if _unsafe_ip(ip):
                raise ValueError("video URL resolves to a private or reserved IP address")


def select_public_ip(addresses: list[str]) -> str:
    if not addresses:
        raise ValueError("video URL host does not resolve")
    parsed = [ipaddress.ip_address(address) for address in addresses]
    if any(_unsafe_ip(ip) for ip in parsed):
        raise ValueError("video URL resolves to a private or reserved IP address")
    return str(parsed[0])


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        port: int | None = None,
        *,
        pinned_ip: str,
        server_hostname: str,
        timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
        source_address=None,
        context=None,
    ):
        self._pinned_ip = pinned_ip
        self._server_hostname = server_hostname
        super().__init__(
            host,
            port=port,
            timeout=timeout,
            source_address=source_address,
            context=context,
        )

    def connect(self):
        sock = socket.create_connection(
            (self._pinned_ip, self.port or 443),
            self.timeout,
            self.source_address,
        )
        context = self.context or ssl.create_default_context()
        self.sock = context.wrap_socket(sock, server_hostname=self._server_hostname)


class PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, resolver=resolve_host):
        context = ssl.create_default_context()
        super().__init__(context=context)
        self.resolver = resolver

    def https_open(self, req):
        return self.do_open(self._make_connection, req, context=self._context)

    def _make_connection(self, host, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, **kwargs):
        parsed_host = urllib.parse.urlsplit(host if "://" in host else f"//{host}")
        hostname = parsed_host.hostname
        port = parsed_host.port or 443
        if not hostname:
            raise ValueError("video URL must include a hostname")
        host_lower = hostname.lower().rstrip(".")
        pinned_ip = select_public_ip(self.resolver(host_lower))
        return PinnedHTTPSConnection(
            hostname,
            port=port,
            pinned_ip=pinned_ip,
            server_hostname=hostname,
            context=self._context,
            timeout=timeout,
            source_address=source_address,
        )


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(f"Instagram API request must not be redirected: HTTP {code}")


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, resolver=resolve_host):
        super().__init__()
        self.resolver = resolver

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_https_url(newurl, resolve=True, resolver=self.resolver)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_media_opener(resolver=resolve_host):
    return urllib.request.build_opener(
        SafeRedirectHandler(resolver),
        PinnedHTTPSHandler(resolver),
        urllib.request.ProxyHandler({}),
    )


def build_api_opener():
    # Preserve normal environment proxy support for the fixed Graph host, but
    # replace urllib's redirect handler so credentials cannot be forwarded.
    return urllib.request.build_opener(NoRedirectHandler())


def build_opener(resolver=resolve_host):
    return build_media_opener(resolver)


def http_open(request: urllib.request.Request, opener=None, timeout: float = 120):
    opener = opener or build_api_opener()
    return opener.open(request, timeout=timeout)


def download_remote_media(
    url: str,
    expected_sha256: str,
    *,
    max_bytes: int = MAX_REMOTE_BYTES,
    opener=None,
    resolver=resolve_host,
) -> tuple[bytes, str]:
    validate_public_https_url(url, resolve=True, resolver=resolver)
    opener = opener or build_media_opener(resolver)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        response = opener.open(request, timeout=120)
    except urllib.error.URLError as exc:
        raise ValueError(f"remote media download failed: {exc.reason}") from exc
    final_url = response.geturl()
    validate_public_https_url(final_url, resolve=True, resolver=resolver)
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type and content_type != "video/mp4":
        raise ValueError("remote media Content-Type must be video/mp4 when present")
    data = bytearray()
    while True:
        block = response.read(1024 * 1024)
        if not block:
            break
        data.extend(block)
        if len(data) > max_bytes:
            raise ValueError("remote media exceeds the 300 MiB limit")
    body = bytes(data)
    actual = hashlib.sha256(body).hexdigest()
    if actual != expected_sha256:
        raise ValueError("remote HTTPS media hash does not match the verified local video")
    return body, final_url


def default_record_path(video: Path, account_key: str | None) -> Path:
    if account_key:
        return video.parent / f"instagram-publish-{account_key}.json"
    return video.parent / "instagram-publish.json"


def resolve_record_path(video: Path, override_path: Path | None, account_key: str | None) -> Path:
    selected = override_path.expanduser() if override_path is not None else default_record_path(video, account_key)
    # absolute() normalizes the location without dereferencing a final symlink;
    # os.replace() can therefore replace that symlink instead of its target.
    selected = Path(os.path.abspath(selected))
    if override_path is not None:
        package_dir = Path(os.path.abspath(video.parent))
        if selected.parent != package_dir:
            raise ValueError("publish record override must stay in the video package directory")
        if not re.fullmatch(r"instagram-publish(?:-[a-z0-9][a-z0-9_-]{0,63})?\.json", selected.name):
            raise ValueError("publish record override name must match instagram-publish[-key].json")
    return selected


def publish_record_candidates(
    video: Path,
    account_key: str | None,
    override_path: Path | None,
) -> list[Path]:
    parent = video.parent.resolve()
    candidates = {default_record_path(video, account_key).resolve()}
    if override_path is not None:
        expanded = override_path.expanduser()
        candidates.add(expanded.absolute())
        candidates.add(expanded.resolve())
    for path in parent.glob("instagram-publish*.json"):
        candidates.add(path.resolve())
    return sorted(candidates)


def find_blocking_publish_record(
    candidates: list[Path],
    video_sha256: str,
    account_key: str | None,
    user_id: str,
) -> Path | None:
    for path in candidates:
        if not path.is_file():
            continue
        record = load_publish_record(path)
        if not isinstance(record, dict):
            raise ValueError(f"invalid publish record {path}: expected object")
        if duplicate_record_blocks(record, video_sha256, account_key, user_id):
            return path
    return None


def build_publish_record(
    video_sha256: str,
    caption: str,
    identity: dict[str, str],
    account_key: str | None,
    media_id: str,
    permalink: str | None,
    timestamp: str | None,
) -> dict:
    return {
        "platform": "instagram",
        "target": {
            "key": account_key or "legacy-env",
            "id": identity["id"],
            "username": identity["username"],
        },
        "timestamp": timestamp,
        "media_id": media_id,
        "permalink": permalink,
        "sha256": video_sha256,
        "caption_sha256": caption_sha256(caption),
        "visibility": "public",
    }


def load_publish_record(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid publish record {path}: {exc}") from exc


def duplicate_record_blocks(record: dict | None, video_sha256: str, account_key: str | None, user_id: str) -> bool:
    if record is None:
        return False
    if record.get("platform") != "instagram":
        return False
    if record.get("sha256") != video_sha256:
        return False
    target = record.get("target") or {}
    # Registry keys are local aliases and may change during migration; the
    # platform user ID is the stable publication target identity.
    if str(target.get("id") or "") != str(user_id):
        return False
    return True


def write_publish_record_atomic(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True)
    temp = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
        path.chmod(0o600)
    finally:
        temp.unlink(missing_ok=True)


def instagram_api_base(version: str) -> str:
    return f"{INSTAGRAM_GRAPH}/{version}"


def _read_api_json_object(response) -> dict:
    try:
        result = json.load(response)
    except (json.JSONDecodeError, UnicodeDecodeError, http.client.HTTPException) as exc:
        raise ValueError("Instagram API response body is incomplete or invalid JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("Instagram API response must be a JSON object")
    return result


def api_get(path: str, token: str, params: dict[str, str] | None = None, opener=None) -> dict:
    query = urllib.parse.urlencode({**(params or {}), "access_token": token})
    url = f"{path}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with http_open(request, opener=opener) as response:
            return _read_api_json_object(response)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Instagram API request failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ValueError("Instagram API transport failed") from exc


def api_post(path: str, token: str, fields: dict[str, str], opener=None) -> dict:
    payload = urllib.parse.urlencode({**fields, "access_token": token}).encode()
    request = urllib.request.Request(
        path,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with http_open(request, opener=opener) as response:
            return _read_api_json_object(response)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Instagram API request failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ValueError("Instagram API transport failed") from exc


def fetch_instagram_identity(token: str, version: str, opener=None) -> dict[str, str]:
    validate_api_version(version)
    result = api_get(
        f"{instagram_api_base(version)}/me",
        token,
        params={"fields": "id,username"},
        opener=opener,
    )
    user_id = result.get("id")
    username = result.get("username")
    if not user_id or not username:
        raise ValueError("Instagram identity response is missing id or username")
    return {"id": str(user_id), "username": str(username)}


def verify_registered_identity(
    token: str,
    version: str,
    expected_user_id: str,
    expected_username: str | None = None,
    opener=None,
) -> dict[str, str]:
    identity = fetch_instagram_identity(token, version, opener=opener)
    if str(identity["id"]) != str(expected_user_id):
        raise ValueError("Instagram credentials do not match the selected account")
    if expected_username is not None and identity["username"] != expected_username:
        raise ValueError("Instagram credentials do not match the selected account username")
    return identity


def create_reels_container(
    token: str,
    user_id: str,
    version: str,
    video_url: str,
    caption: str,
    share_to_feed: bool,
    opener=None,
) -> str:
    result = api_post(
        f"{instagram_api_base(version)}/{user_id}/media",
        token,
        {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": str(share_to_feed).lower(),
        },
        opener=opener,
    )
    container_id = result.get("id")
    if not container_id:
        raise ValueError("Instagram returned no container ID")
    return str(container_id)


def poll_container_status(
    token: str,
    container_id: str,
    version: str,
    *,
    timeout: float = 300,
    interval: float = 5,
    sleeper=time.sleep,
    monotonic=time.monotonic,
    opener=None,
) -> dict:
    deadline = monotonic() + max(0, timeout)
    last_status: dict = {}
    while True:
        last_status = api_get(
            f"{instagram_api_base(version)}/{container_id}",
            token,
            params={"fields": "status_code,status"},
            opener=opener,
        )
        code = last_status.get("status_code")
        if code == "FINISHED":
            return last_status
        if code in {"ERROR", "EXPIRED"}:
            raise ValueError("container failed: " + json.dumps({
                key: value for key, value in last_status.items() if key != "access_token"
            }))
        if monotonic() >= deadline:
            raise TimeoutError("container not ready before the status timeout")
        sleeper(max(0, interval))


def publish_container(token: str, user_id: str, version: str, container_id: str, opener=None) -> str:
    result = api_post(
        f"{instagram_api_base(version)}/{user_id}/media_publish",
        token,
        {"creation_id": container_id},
        opener=opener,
    )
    media_id = result.get("id")
    if not media_id:
        raise ValueError("Instagram returned no media ID")
    return str(media_id)


def read_back_published_media(
    token: str,
    media_id: str,
    version: str,
    *,
    expected_username: str,
    expected_caption: str,
    opener=None,
) -> dict[str, str]:
    result = api_get(
        f"{instagram_api_base(version)}/{media_id}",
        token,
        params={
            "fields": "id,username,media_type,media_product_type,permalink,caption,timestamp",
        },
        opener=opener,
    )
    media_id_value = result.get("id")
    if not media_id_value:
        raise ValueError("Instagram read-back is missing media id")
    if str(media_id_value) != str(media_id):
        raise ValueError("Instagram read-back id does not match published media_id")
    username = result.get("username")
    if username != expected_username:
        raise ValueError("Instagram read-back username does not match the selected account")
    media_type = result.get("media_type")
    if str(media_type or "") != "VIDEO":
        raise ValueError("Instagram read-back media_type is not VIDEO")
    product_type = result.get("media_product_type")
    if str(product_type or "") != "REELS":
        raise ValueError("Instagram read-back media_product_type is not REELS")
    permalink = result.get("permalink")
    if not permalink or not str(permalink).startswith("https://"):
        raise ValueError("Instagram read-back permalink must be a non-empty HTTPS URL")
    timestamp = result.get("timestamp")
    if not timestamp:
        raise ValueError("Instagram read-back timestamp is missing")
    caption = result.get("caption")
    if caption != expected_caption:
        raise ValueError("Instagram read-back caption does not match the approved caption")
    return {
        "id": str(media_id_value),
        "username": str(username),
        "media_type": str(media_type),
        "media_product_type": str(product_type),
        "permalink": str(permalink),
        "caption": str(caption),
        "timestamp": str(timestamp),
    }


def safe_failure_payload(**fields) -> dict:
    payload = {"ok": False, "platform": "instagram"}
    for key, value in fields.items():
        if key == "access_token":
            continue
        payload[key] = value
    return payload


@contextmanager
def publication_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("Instagram publication lock directory must be a real directory")
    os.chmod(path.parent, 0o700)
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def publication_lock_path(record_path: Path, account_key: str | None, user_id: str, video_sha256: str) -> Path:
    del account_key  # local aliases are mutable; stable target identity is user_id
    identity = f"{user_id}\0{video_sha256}".encode("utf-8")
    name = hashlib.sha256(identity).hexdigest() + ".lock"
    return record_path.parent / ".instagram-publish-locks" / name


def publish(args, *, api_opener=None, media_opener=None, resolver=None, sleeper=time.sleep, monotonic=time.monotonic) -> dict:
    if not args.approved:
        raise SystemExit("Refusing publication without explicit --approved after the user command")
    try:
        video_sha256 = verify_local_package(args.video, args.verification)
        if args.account:
            selected_account, _ = credentials_for_account(args.account)
            user_id = selected_account["user_id"]
        else:
            user_id = legacy_environment_credentials()["INSTAGRAM_USER_ID"]
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    record_path = resolve_record_path(args.video, args.record, args.account)
    lock_path = publication_lock_path(record_path, args.account, user_id, video_sha256)
    with publication_lock(lock_path):
        return _publish_with_lock_held(
            args,
            api_opener=api_opener,
            media_opener=media_opener,
            resolver=resolver,
            sleeper=sleeper,
            monotonic=monotonic,
        )


def _publish_with_lock_held(args, *, api_opener=None, media_opener=None, resolver=None, sleeper=time.sleep, monotonic=time.monotonic) -> dict:
    if not args.approved:
        raise SystemExit("Refusing publication without explicit --approved after the user command")
    if resolver is None:
        resolver = resolve_host
    api_opener = api_opener or build_api_opener()
    media_opener = media_opener or build_media_opener(resolver)

    try:
        video_sha256 = verify_local_package(args.video, args.verification)
        caption = read_caption(args.caption_file)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    try:
        validate_public_https_url(args.video_url, resolve=True, resolver=resolver)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    account_key = args.account
    expected_username: str | None = None
    try:
        if account_key:
            selected_account, credentials = credentials_for_account(account_key)
            user_id = selected_account["user_id"]
            expected_username = selected_account["username"]
        else:
            credentials = legacy_environment_credentials()
            user_id = credentials["INSTAGRAM_USER_ID"]
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    version = credentials.get("INSTAGRAM_API_VERSION", DEFAULT_API_VERSION)
    try:
        validate_api_version(version)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    token = credentials["INSTAGRAM_ACCESS_TOKEN"]
    record_path = resolve_record_path(args.video, args.record, account_key)
    record_candidates = publish_record_candidates(args.video, account_key, args.record)
    try:
        blocking_path = find_blocking_publish_record(record_candidates, video_sha256, account_key, user_id)
        if blocking_path is not None:
            raise SystemExit("Refusing duplicate publication: matching publish record already exists")
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    try:
        download_remote_media(
            args.video_url,
            video_sha256,
            opener=media_opener,
            resolver=resolver,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    try:
        identity = verify_registered_identity(
            token,
            version,
            user_id,
            expected_username,
            opener=api_opener,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    container_id: str | None = None
    media_id: str | None = None
    published = False
    write_attempted = False
    try:
        write_attempted = True
        container_id = create_reels_container(
            token,
            user_id,
            version,
            args.video_url,
            caption,
            args.share_to_feed,
            opener=api_opener,
        )
        poll_container_status(
            token,
            container_id,
            version,
            timeout=args.status_timeout,
            interval=args.status_interval,
            sleeper=sleeper,
            monotonic=monotonic,
            opener=api_opener,
        )
        media_id = publish_container(token, user_id, version, container_id, opener=api_opener)
        published = True
        write_publish_record_atomic(
            record_path,
            build_publish_record(
                video_sha256,
                caption,
                identity,
                account_key,
                media_id,
                permalink=None,
                timestamp=None,
            ),
        )
        readback = read_back_published_media(
            token,
            media_id,
            version,
            expected_username=identity["username"],
            expected_caption=caption,
            opener=api_opener,
        )
    except TimeoutError as exc:
        payload = safe_failure_payload(
            container_created=container_id is not None,
            container_id=container_id,
            published=published,
            media_id=media_id,
            ambiguous=True,
            error_type=type(exc).__name__,
        )
        raise SystemExit(json.dumps(payload, ensure_ascii=False)) from None
    except ValueError as exc:
        message = str(exc)
        ambiguous = write_attempted
        if message.startswith("container failed:"):
            payload = safe_failure_payload(
                container_created=True,
                container_id=container_id,
                published=False,
                ambiguous=True,
                error_type="ContainerFailed",
            )
            raise SystemExit(json.dumps(payload, ensure_ascii=False)) from None
        payload = safe_failure_payload(
            container_created=container_id is not None,
            container_id=container_id,
            published=published,
            media_id=media_id,
            ambiguous=ambiguous,
            error_type=type(exc).__name__,
        )
        raise SystemExit(json.dumps(payload, ensure_ascii=False)) from None
    except OSError as exc:
        payload = safe_failure_payload(
            container_created=container_id is not None,
            container_id=container_id,
            published=published,
            media_id=media_id,
            ambiguous=write_attempted,
            error_type=type(exc).__name__,
        )
        raise SystemExit(json.dumps(payload, ensure_ascii=False)) from None

    try:
        write_publish_record_atomic(
            record_path,
            build_publish_record(
                video_sha256,
                caption,
                identity,
                account_key,
                readback["id"],
                permalink=readback["permalink"],
                timestamp=readback["timestamp"],
            ),
        )
    except OSError as exc:
        payload = safe_failure_payload(
            container_created=True,
            container_id=container_id,
            published=True,
            media_id=media_id,
            ambiguous=True,
            error_type=type(exc).__name__,
        )
        raise SystemExit(json.dumps(payload, ensure_ascii=False)) from None

    return {
        "ok": True,
        "platform": "instagram",
        "target": {
            "key": account_key or "legacy-env",
            "id": identity["id"],
            "username": identity["username"],
        },
        "id": readback["id"],
        "username": readback["username"],
        "media_type": readback["media_type"],
        "media_product_type": readback["media_product_type"],
        "permalink": readback["permalink"],
        "caption": readback["caption"],
        "timestamp": readback["timestamp"],
        "container_id": container_id,
        "sha256": video_sha256,
        "caption_sha256": caption_sha256(caption),
        "visibility": "public",
        "record": str(record_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--account",
        help="Key from manage_instagram_accounts.py list; omitted only for legacy environment credentials",
    )
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--video-url", required=True)
    parser.add_argument("--verification", required=True, type=Path)
    parser.add_argument("--caption-file", required=True, type=Path)
    parser.add_argument("--record", type=Path, help="Override the default target-specific publish record path")
    parser.add_argument("--share-to-feed", action="store_true")
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--status-timeout", type=float, default=300)
    parser.add_argument("--status-interval", type=float, default=5)
    args = parser.parse_args()
    result = publish(args)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
