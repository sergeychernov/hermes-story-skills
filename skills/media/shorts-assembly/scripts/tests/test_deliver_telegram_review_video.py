import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "deliver_telegram_review_video.py"


def load_module():
    spec = importlib.util.spec_from_file_location("deliver_telegram_review_video", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class TelegramDeliveryDiagnosticsTests(unittest.TestCase):
    def test_gateway_environment_parser_is_allowlisted_and_non_utf8_safe(self):
        module = load_module()
        raw = (
            b"TELEGRAM_BOT_TOKEN=token\0"
            b"TELEGRAM_PROXY=socks5://proxy\0"
            b"OAUTH_SECRET=must-not-escape\0"
            b"BROKEN=\xff\0"
        )
        self.assertEqual(
            module.parse_gateway_environment(raw),
            {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_PROXY": "socks5://proxy"},
        )

    def test_gateway_environment_parser_rejects_invalid_utf8_allowlisted_values(self):
        module = load_module()
        self.assertEqual(
            module.parse_gateway_environment(
                b"TELEGRAM_BOT_TOKEN=token\0TELEGRAM_PROXY=socks5://bad-\xff\0"
            ),
            {"TELEGRAM_BOT_TOKEN": "token"},
        )
        self.assertEqual(
            module.parse_gateway_environment(b"TELEGRAM_BOT_TOKEN=bad-\xff\0"),
            {},
        )

    def test_gateway_argv_requires_real_entrypoint_and_exact_subcommand_tokens(self):
        module = load_module()
        self.assertTrue(module.is_gateway_argv([
            "/opt/hermes/.venv/bin/python3", "/opt/hermes/.venv/bin/hermes",
            "gateway", "run", "--replace",
        ]))
        self.assertTrue(module.is_gateway_argv(["/usr/local/bin/hermes", "gateway", "run"]))
        self.assertFalse(module.is_gateway_argv([
            "python3", "-c", "import time; time.sleep(60)", "hermes gateway run",
        ]))
        self.assertFalse(module.is_gateway_argv([
            "python3", "-c", "import time; time.sleep(60)", "hermes", "gateway", "run",
        ]))

    def test_classifies_latest_failure_for_exact_artifact(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "gateway.log"
            artifact = "/tmp/review.mp4"
            log.write_text(
                f"Failed to send video: Request Entity Too Large\n"
                f"send_video fallback: native video send unavailable for {artifact}\n"
                f"Failed to send video: Timed out\n"
                f"send_video fallback: native video send unavailable for {artifact}\n",
                encoding="utf-8",
            )
            result = module.classify_latest_failure(log, Path(artifact))
            self.assertEqual(result["classification"], "timeout")
            self.assertIn("Timed out", result["error"])

    def test_diagnostic_does_not_match_artifact_path_prefix(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "gateway.log"
            artifact = Path("/tmp/review.mp4")
            log.write_text(
                "Failed to send video: Timed out\n"
                f"send_video fallback: native video send unavailable for {artifact}.v2.mp4\n",
                encoding="utf-8",
            )
            self.assertIsNone(module.classify_latest_failure(log, artifact)["classification"])

    def test_diagnostic_rejects_malformed_fallback_line(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "gateway.log"
            artifact = Path("/tmp/review.mp4")
            log.write_text(
                "Failed to send video: Timed out\n"
                f"unrelated payload containing send_video fallback and ending for {artifact}\n",
                encoding="utf-8",
            )
            self.assertIsNone(module.classify_latest_failure(log, artifact)["classification"])

    def test_diagnostic_reads_only_bounded_log_tail(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "gateway.log"
            artifact = Path("/tmp/review.mp4")
            with log.open("w", encoding="utf-8") as handle:
                handle.write("Failed to send video: Timed out\n")
                handle.write(f"send_video fallback: native video send unavailable for {artifact}\n")
                handle.write("x" * (module.GATEWAY_LOG_TAIL_BYTES + 1024))
            self.assertIsNone(module.classify_latest_failure(log, artifact)["classification"])

    def test_gateway_diagnostic_redacts_bot_token_and_proxy_credentials(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / "gateway.log"
            artifact = "/tmp/review.mp4"
            token = "123456789:" + ("A" * 35)
            log.write_text(
                "Failed to send video: Timed out at "
                f"https://api.telegram.org/bot{token}/sendVideo "
                "via socks5://proxy-user:proxy-pass@proxy.local:1080\n"
                f"send_video fallback: native video send unavailable for {artifact}\n",
                encoding="utf-8",
            )
            result = module.classify_latest_failure(log, Path(artifact))
            serialized = json.dumps(result)
            self.assertEqual(result["classification"], "timeout")
            self.assertNotIn(token, serialized)
            self.assertNotIn("proxy-user", serialized)
            self.assertNotIn("proxy-pass", serialized)
            self.assertIn("[REDACTED]", result["error"])

    def test_retry_delay_allows_rate_limit_and_connect_before_send(self):
        module = load_module()
        rate_limit = RuntimeError("rate limited")
        rate_limit.retry_after = 17
        self.assertEqual(module.safe_retry_delay(rate_limit, 1), 17.0)

        connect_type = type("ConnectTimeout", (Exception,), {"__module__": "httpx"})
        wrapped = RuntimeError("wrapped")
        wrapped.__cause__ = connect_type("connect failed")
        self.assertEqual(module.safe_retry_delay(wrapped, 2), 10.0)

    def test_retry_delay_rejects_ambiguous_read_or_write_timeout(self):
        module = load_module()
        for name in ("ReadTimeout", "WriteTimeout", "ReadError", "WriteError"):
            timeout_type = type(name, (Exception,), {"__module__": "httpx"})
            wrapped = RuntimeError("wrapped")
            wrapped.__cause__ = timeout_type("ambiguous")
            self.assertIsNone(module.safe_retry_delay(wrapped, 1), name)

    def test_write_report_does_not_follow_predictable_tmp_symlink(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = root / "delivery.json"
            victim = root / "victim.txt"
            victim.write_text("immutable", encoding="utf-8")
            Path(str(report) + ".tmp").symlink_to(victim)
            module.write_report(report, {"status": "ok"})
            self.assertEqual(victim.read_text(encoding="utf-8"), "immutable")
            self.assertEqual(json.loads(report.read_text(encoding="utf-8")), {"status": "ok"})
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)

    def test_report_path_rejects_final_symlink_and_media_aliases(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "master.mp4"
            delivery = root / "review.mp4"
            victim = root / "victim.json"
            source.write_bytes(b"master")
            delivery.write_bytes(b"review")
            victim.write_text("immutable", encoding="utf-8")
            report_link = root / "report.json"
            report_link.symlink_to(victim)
            with self.assertRaisesRegex(RuntimeError, "symlink"):
                module.validated_report_path(report_link, source, delivery)
            for alias in (source, delivery):
                with self.subTest(alias=alias), self.assertRaisesRegex(RuntimeError, "aliases"):
                    module.validated_report_path(alias, source, delivery)
            self.assertEqual(victim.read_text(encoding="utf-8"), "immutable")

    def test_create_derivative_reuses_matching_verified_copy(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.mp4"
            output = root / "review.mp4"
            source.write_bytes(b"source")
            output.write_bytes(b"review")
            report = {
                "status": "ok",
                "source": {"sha256": module.sha256(source)},
                "output": {
                    "sha256": module.sha256(output),
                    "max_mib_policy": 18.0,
                },
                "video": {"width": 720, "height": 1280},
            }
            Path(str(output) + ".report.json").write_text(json.dumps(report), encoding="utf-8")
            original_run = module.run
            module.run = lambda *args, **kwargs: self.fail("renderer must not run")
            try:
                self.assertEqual(module.create_derivative(source, output, 18.0, 720, 1280), output)
            finally:
                module.run = original_run


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg required")
class TelegramDeliveryDryRunTests(unittest.TestCase):
    def test_dry_run_writes_verified_review_only_report_without_token(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "preview.mp4"
            report = root / "delivery-report.json"
            subprocess.run(
                [
                    "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=360x640:rate=30:duration=1",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", str(source),
                ],
                check=True,
            )
            completed = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "--input", str(source),
                    "--chat-id", "123", "--dry-run", "--report", str(report),
                    "--gateway-log", str(root / "missing.log"),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            data = json.loads(report.read_text())
            self.assertEqual(data["status"], "preflight-ok")
            self.assertTrue(data["review_only"])
            self.assertFalse(data["publication_eligible"])
            self.assertEqual(data["telegram_contract"]["send_video_max_bytes"], 50_000_000)
            self.assertEqual(data["video"]["codec"], "h264")
            self.assertEqual(data["video"]["pixel_format"], "yuv420p")
            self.assertTrue(data["verification"]["full_video_decode"])
            self.assertTrue(data["verification"]["full_audio_decode"])
            self.assertIsNone(data["delivery"]["message_id"])


if __name__ == "__main__":
    unittest.main()
