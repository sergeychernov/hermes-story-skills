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
