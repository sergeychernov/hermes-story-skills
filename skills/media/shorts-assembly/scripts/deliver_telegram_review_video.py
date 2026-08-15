#!/usr/bin/env python3
"""Prepare and deliver a review-only video through Telegram Bot API safely."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEND_VIDEO_MAX_BYTES = 50_000_000
OFFICIAL_CONTRACT_URL = "https://core.telegram.org/bots/api#sendvideo"
DEFAULT_GATEWAY_LOG = Path("/opt/data/logs/gateway.log")
GATEWAY_LOG_TAIL_BYTES = 1024 * 1024
TELEGRAM_ENV_ALLOWLIST = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_PROXY")


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def probe(path: Path) -> dict[str, Any]:
    result = run(
        [
            "ffprobe", "-v", "error", "-count_frames", "-show_streams",
            "-show_format", "-of", "json", str(path),
        ],
        capture=True,
    )
    return json.loads(result.stdout)


def sanitize_diagnostic(value: str) -> str:
    value = re.sub(r"(?<!\d)\d{6,12}:[A-Za-z0-9_-]{20,}", "[REDACTED]", value)
    value = re.sub(
        r"(?i)([a-z][a-z0-9+.-]*://)[^/@\s]+@",
        r"\1[REDACTED]@",
        value,
    )
    value = re.sub(
        r"(?i)([?&](?:token|password|secret)=)[^&\s]+",
        r"\1[REDACTED]",
        value,
    )
    return value


def classify_latest_failure(log_path: Path, artifact: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"classification": None, "error": None, "log": str(log_path)}
    if not log_path.is_file():
        return result
    with log_path.open("rb") as handle:
        size = log_path.stat().st_size
        offset = max(0, size - GATEWAY_LOG_TAIL_BYTES)
        handle.seek(offset)
        raw = handle.read(GATEWAY_LOG_TAIL_BYTES)
    if offset:
        _, separator, raw = raw.partition(b"\n")
        if not separator:
            raw = b""
    lines = raw.decode("utf-8", errors="replace").splitlines()
    artifact_text = str(artifact)
    matches: list[str] = []
    for index, line in enumerate(lines):
        if "send_video fallback" not in line or not line.rstrip().endswith(f" for {artifact_text}"):
            continue
        for previous in reversed(lines[max(0, index - 8):index]):
            if "Failed to send video:" in previous:
                matches.append(previous.split("Failed to send video:", 1)[1].strip())
                break
    if not matches:
        return result
    error = matches[-1]
    lowered = error.lower()
    if "entity too large" in lowered or "file is too big" in lowered:
        classification = "too_large"
    elif "timed out" in lowered or "timeout" in lowered:
        classification = "timeout"
    else:
        classification = "other"
    return {
        "classification": classification,
        "error": sanitize_diagnostic(error),
        "log": str(log_path),
    }


def full_decode(path: Path, selector: str) -> None:
    run(["ffmpeg", "-v", "error", "-i", str(path), "-map", selector, "-f", "null", "-"])


def preflight(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"video missing or empty: {path}")
    if path.stat().st_size > SEND_VIDEO_MAX_BYTES:
        raise RuntimeError(
            f"video exceeds official sendVideo cap: {path.stat().st_size} > {SEND_VIDEO_MAX_BYTES}"
        )
    data = probe(path)
    videos = [s for s in data["streams"] if s.get("codec_type") == "video"]
    audios = [s for s in data["streams"] if s.get("codec_type") == "audio"]
    if len(videos) != 1:
        raise RuntimeError(f"expected exactly one video stream, got {len(videos)}")
    if len(audios) > 1:
        raise RuntimeError(f"expected zero or one audio stream, got {len(audios)}")
    video = videos[0]
    audio = audios[0] if audios else None
    format_name = str(data.get("format", {}).get("format_name") or "")
    if "mp4" not in format_name and "mov" not in format_name:
        raise RuntimeError(f"native sendVideo requires MPEG4-compatible container, got {format_name}")
    if video.get("codec_name") != "h264":
        raise RuntimeError(f"native sendVideo baseline requires H.264, got {video.get('codec_name')}")
    if video.get("pix_fmt") != "yuv420p":
        raise RuntimeError(f"native sendVideo baseline requires yuv420p, got {video.get('pix_fmt')}")
    if audio and audio.get("codec_name") != "aac":
        raise RuntimeError(f"native sendVideo baseline requires AAC audio, got {audio.get('codec_name')}")
    frames_raw = video.get("nb_read_frames") or video.get("nb_frames")
    if not frames_raw or frames_raw == "N/A":
        raise RuntimeError("decoded frame count unavailable")
    full_decode(path, "0:v:0")
    if audio:
        full_decode(path, "0:a:0")
    return {
        "path": str(path.resolve()),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "container": format_name,
        "video": {
            "codec": video.get("codec_name"),
            "pixel_format": video.get("pix_fmt"),
            "width": int(video["width"]),
            "height": int(video["height"]),
            "frame_count": int(frames_raw),
            "fps": video.get("avg_frame_rate") or video.get("r_frame_rate"),
            "duration_seconds": float(video.get("duration") or data["format"]["duration"]),
        },
        "audio": {
            "present": bool(audio),
            "codec": audio.get("codec_name") if audio else None,
            "sample_rate": int(audio["sample_rate"]) if audio else None,
            "channels": int(audio["channels"]) if audio else None,
        },
    }


def parse_gateway_environment(raw: bytes) -> dict[str, str]:
    allowed = {key.encode(): key for key in TELEGRAM_ENV_ALLOWLIST}
    result: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        if key in allowed:
            result[allowed[key]] = value.decode("utf-8", errors="replace")
    return result


def _is_gateway_process(pid: int) -> bool:
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ")
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return False
    return b"hermes gateway run" in cmdline


def find_gateway_environment(explicit_pid: int | None) -> dict[str, str]:
    if explicit_pid is not None and not _is_gateway_process(explicit_pid):
        raise RuntimeError("--gateway-pid does not belong to a live Hermes gateway")
    pids: list[int] = [explicit_pid] if explicit_pid else []
    if not pids:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ")
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
            if b"hermes gateway run" in cmdline:
                pids.append(int(entry.name))
    for pid in sorted(pids, reverse=True):
        try:
            raw = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        env = parse_gateway_environment(b"\0".join(raw))
        if env.get("TELEGRAM_BOT_TOKEN"):
            return env
    env = {key: os.environ[key] for key in TELEGRAM_ENV_ALLOWLIST if key in os.environ}
    if env.get("TELEGRAM_BOT_TOKEN"):
        return env
    raise RuntimeError("TELEGRAM_BOT_TOKEN unavailable in environment or live gateway process")


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        dir_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        dir_fd = os.open(path.parent, dir_flags)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        tmp.unlink(missing_ok=True)


def _matching_derivative_report(
    source: Path, output: Path, max_mib: float, width: int, height: int
) -> bool:
    report_path = Path(str(output) + ".report.json")
    if not output.is_file() or not report_path.is_file():
        return False
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        return (
            report.get("status") == "ok"
            and report["source"]["sha256"] == sha256(source)
            and report["output"]["sha256"] == sha256(output)
            and float(report["output"]["max_mib_policy"]) == float(max_mib)
            and int(report["video"]["width"]) == width
            and int(report["video"]["height"]) == height
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
        return False


def create_derivative(source: Path, output: Path, max_mib: float, width: int, height: int) -> Path:
    report_path = Path(str(output) + ".report.json")
    if output.exists() or report_path.exists():
        if _matching_derivative_report(source, output, max_mib, width, height):
            return output
        raise RuntimeError("existing derivative or report does not match requested source and policy")
    maker = Path(__file__).with_name("make_review_delivery_copy.py")
    run(
        [
            sys.executable, str(maker), "--input", str(source), "--output", str(output),
            "--width", str(width), "--height", str(height), "--max-mib", str(max_mib),
        ]
    )
    return output


def safe_retry_delay(exc: Exception, attempt: int) -> float | None:
    """Return a delay only when Telegram definitely did not accept the upload."""
    retry_after = getattr(exc, "retry_after", None)
    if isinstance(retry_after, (int, float)) and retry_after >= 0:
        return float(retry_after)

    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        error_type = type(current)
        if error_type.__module__.startswith("httpx") and error_type.__name__ in {
            "ConnectError", "ConnectTimeout",
        }:
            return float(5 * attempt)
        current = current.__cause__ or current.__context__
    return None


async def send_video(
    path: Path,
    chat_id: int,
    caption: str,
    env: dict[str, str],
    retries: int,
    connect_timeout: float,
    read_timeout: float,
    media_write_timeout: float,
) -> int:
    from telegram import Bot
    from telegram.request import HTTPXRequest

    token = env["TELEGRAM_BOT_TOKEN"]
    proxy = env.get("TELEGRAM_PROXY") or None
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        request = HTTPXRequest(
            proxy=proxy,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            write_timeout=20,
            media_write_timeout=media_write_timeout,
        )
        bot = Bot(token=token, request=request)
        try:
            async with bot:
                with path.open("rb") as video:
                    message = await bot.send_video(
                        chat_id=chat_id,
                        video=video,
                        caption=caption[:1024] or None,
                        supports_streaming=True,
                        connect_timeout=connect_timeout,
                        read_timeout=read_timeout,
                        write_timeout=media_write_timeout,
                    )
            if not message.message_id:
                raise RuntimeError("Telegram returned no message_id")
            return int(message.message_id)
        except Exception as exc:
            last_error = exc
            delay = safe_retry_delay(exc, attempt)
            if attempt < retries and delay is not None:
                await asyncio.sleep(delay)
                continue
            raise
    raise last_error or RuntimeError("Telegram delivery failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="canonical master or existing preview")
    parser.add_argument("--chat-id", required=True, type=int)
    parser.add_argument("--derivative-output", type=Path)
    parser.add_argument("--review-max-mib", type=float, default=18.0)
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=1280)
    parser.add_argument("--caption", default="Превью для проверки — review-only копия, master не изменён.")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--gateway-log", type=Path, default=DEFAULT_GATEWAY_LOG)
    parser.add_argument("--gateway-pid", type=int)
    parser.add_argument("--connect-timeout", type=float, default=60.0)
    parser.add_argument("--read-timeout", type=float, default=60.0)
    parser.add_argument("--media-write-timeout", type=float, default=120.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for binary in ("ffmpeg", "ffprobe"):
        if not shutil.which(binary):
            raise SystemExit(f"missing required command: {binary}")
    source = args.input.resolve()
    if not source.is_file():
        raise SystemExit(f"input not found: {source}")
    if not 1 <= args.retries <= 5:
        raise SystemExit("retries must be between 1 and 5")
    review_budget_bytes = int(args.review_max_mib * 1024 * 1024)
    delivery = source
    derivative_created = False
    if source.stat().st_size > review_budget_bytes:
        if not args.derivative_output:
            raise SystemExit("input exceeds review budget; --derivative-output is required")
        delivery = create_derivative(
            source, args.derivative_output.resolve(), args.review_max_mib, args.width, args.height
        )
        derivative_created = True

    media = preflight(delivery)
    diagnosis = classify_latest_failure(args.gateway_log, delivery)
    report_path = (args.report or Path(str(delivery) + ".telegram-delivery.report.json")).resolve()
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "preflight-ok",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_only": True,
        "publication_eligible": False,
        "source_master": {"path": str(source), "sha256": sha256(source), "bytes": source.stat().st_size},
        "delivery_artifact": media,
        "derivative_created": derivative_created,
        "telegram_contract": {
            "method": "sendVideo",
            "official_source": OFFICIAL_CONTRACT_URL,
            "container": "MPEG4",
            "send_video_max_bytes": SEND_VIDEO_MAX_BYTES,
        },
        "video": media["video"],
        "audio": media["audio"],
        "gateway_diagnosis": diagnosis,
        "timeouts_seconds": {
            "connect": args.connect_timeout,
            "read": args.read_timeout,
            "media_write": args.media_write_timeout,
        },
        "verification": {
            "size_within_official_cap": media["bytes"] <= SEND_VIDEO_MAX_BYTES,
            "full_video_decode": True,
            "full_audio_decode": bool(media["audio"]["present"]),
        },
        "delivery": {"chat_id": args.chat_id, "message_id": None, "attempted": False},
    }
    write_report(report_path, report)
    if args.dry_run:
        print(json.dumps({"status": "preflight-ok", "artifact": str(delivery), "report": str(report_path)}))
        return 0

    env = find_gateway_environment(args.gateway_pid)
    try:
        message_id = asyncio.run(
            send_video(
                delivery, args.chat_id, args.caption, env, args.retries,
                args.connect_timeout, args.read_timeout, args.media_write_timeout,
            )
        )
    except Exception as exc:
        report["status"] = "delivery-failed"
        report["delivery"] = {
            "chat_id": args.chat_id,
            "message_id": None,
            "attempted": True,
            "error_type": type(exc).__name__,
            "retry_suppressed_if_ambiguous": safe_retry_delay(exc, 1) is None,
        }
        write_report(report_path, report)
        print(f"Telegram delivery failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    report["status"] = "delivered"
    report["delivery"] = {"chat_id": args.chat_id, "message_id": message_id, "attempted": True}
    write_report(report_path, report)
    print(json.dumps({"status": "delivered", "message_id": message_id, "artifact": str(delivery), "report": str(report_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
