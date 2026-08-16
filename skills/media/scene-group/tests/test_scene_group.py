from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_module(name: str, filename: str):
    path = SCRIPTS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate = load_module("validate_scene_group", "validate_scene_group.py")
render = load_module("render_scene_group", "render_scene_group.py")

FFMPEG_OK = subprocess.run(
    ["sh", "-c", "command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null"]
).returncode == 0


def make_video(
    path: Path,
    *,
    color: str,
    duration: float = 0.2,
    with_audio: bool = True,
    freq: int = 440,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=160x120:r=10:d={duration}",
    ]
    if with_audio:
        cmd += [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq}:sample_rate=48000:duration={duration}",
            "-shortest",
            "-c:a",
            "aac",
        ]
    else:
        cmd += ["-an"]
    cmd += [
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-frames:v",
        str(max(1, int(duration * 10))),
        str(path),
    ]
    subprocess.run(cmd, check=True)


class ValidateSpecTests(unittest.TestCase):
    def base_spec(self, members: list[dict] | None = None) -> dict:
        return {
            "schema_version": 1,
            "id": "group-test",
            "members": members
            or [
                {"ref": "a", "path": "scenes/a.mp4", "type": "scene"},
                {"ref": "b", "path": "scenes/b.mp4", "type": "scene"},
            ],
            "output": "exports/out.mp4",
            "overwrite": False,
        }

    def test_requires_at_least_two_members(self):
        spec = self.base_spec([{"ref": "a", "path": "scenes/a.mp4", "type": "scene"}])
        with self.assertRaisesRegex(ValueError, "at least 2"):
            validate.validate_spec(spec)

    def test_rejects_audio_policy_fields(self):
        spec = self.base_spec()
        spec["audio_default"] = "preserve"
        with self.assertRaisesRegex(ValueError, "audio-policy"):
            validate.validate_spec(spec)

    def test_rejects_member_audio_mode(self):
        spec = self.base_spec(
            [
                {"ref": "a", "path": "scenes/a.mp4", "type": "scene", "audio_mode": "remove"},
                {"ref": "b", "path": "scenes/b.mp4", "type": "scene"},
            ]
        )
        with self.assertRaisesRegex(ValueError, "audio-policy"):
            validate.validate_spec(spec)

    def test_group_type_without_path_allowed_at_schema_level(self):
        spec = self.base_spec(
            [
                {"ref": "a", "path": "scenes/a.mp4", "type": "scene"},
                {"ref": "nested", "type": "group"},
            ]
        )
        normalized = validate.validate_spec(spec)
        self.assertEqual(normalized["members"][1]["type"], "group")
        self.assertIsNone(normalized["members"][1]["path"])

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            spec = self.base_spec()
            spec["members"][0]["path"] = "../secret.mp4"
            with self.assertRaisesRegex(ValueError, "traversal|escapes"):
                validate.validate_spec(spec, root)

    def test_existing_output_requires_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "exports").mkdir()
            (root / "exports" / "out.mp4").write_bytes(b"exists")
            spec = self.base_spec()
            with self.assertRaisesRegex(ValueError, "overwrite=false"):
                validate.validate_spec(spec, root)

    def test_output_must_not_alias_a_member_even_with_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "scenes").mkdir()
            (root / "scenes" / "a.mp4").write_bytes(b"a")
            (root / "scenes" / "b.mp4").write_bytes(b"b")
            spec = self.base_spec()
            spec["output"] = "scenes/a.mp4"
            spec["overwrite"] = True
            with self.assertRaisesRegex(ValueError, "output.*member"):
                validate.validate_spec(spec, root)

    def test_report_must_not_alias_output_or_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "scenes").mkdir()
            (root / "scenes" / "a.mp4").write_bytes(b"a")
            (root / "scenes" / "b.mp4").write_bytes(b"b")
            for report in ("exports/out.mp4", "scenes/a.mp4"):
                spec = self.base_spec()
                spec["report"] = report
                with self.subTest(report=report), self.assertRaisesRegex(ValueError, "report.*(?:output|member)"):
                    validate.validate_spec(spec, root)


@unittest.skipUnless(FFMPEG_OK, "ffmpeg required")
class RenderIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.scenes_dir = self.root / "scenes"
        self.exports = self.root / "exports"
        self.exports.mkdir()
        make_video(self.scenes_dir / "a.mp4", color="red", with_audio=True, freq=440)
        make_video(self.scenes_dir / "b.mp4", color="blue", with_audio=True, freq=660)
        make_video(self.scenes_dir / "silent.mp4", color="green", with_audio=False)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def render_spec(self, spec: dict) -> dict:
        return render.render(self.root, spec)

    def test_concatenates_members_preserving_audio(self):
        report = self.render_spec(
            {
                "schema_version": 1,
                "id": "g1",
                "members": [
                    {"ref": "a", "path": "scenes/a.mp4", "type": "scene"},
                    {"ref": "b", "path": "scenes/b.mp4", "type": "scene"},
                ],
                "output": "exports/group.mp4",
                "overwrite": True,
            }
        )
        self.assertEqual(report["status"], "ok")
        artifact = report["artifact"]
        self.assertEqual(artifact["kind"], "group")
        self.assertEqual(artifact["id"], "g1")
        self.assertEqual(len(artifact["members"]), 2)
        self.assertTrue(report["full_decode_verification"]["ok"])
        self.assertEqual(artifact["streams"]["video"]["codec"], "h264")
        self.assertEqual(artifact["streams"]["audio"]["codec"], "aac")
        self.assertEqual(artifact["streams"]["audio"]["sample_rate"], 48000)
        self.assertEqual(artifact["streams"]["audio"]["channels"], 2)
        self.assertNotIn("audio_policy", report)
        self.assertNotIn("audio_default", report)
        self.assertGreater(report["authoritative_duration_seconds"], 0)
        self.assertEqual(len(artifact["boundaries"]), 2)

    def test_silent_member_gets_explicit_silence_for_concat(self):
        report = self.render_spec(
            {
                "schema_version": 1,
                "id": "g-silent",
                "members": [
                    {"ref": "silent", "path": "scenes/silent.mp4", "type": "scene"},
                    {"ref": "a", "path": "scenes/a.mp4", "type": "scene"},
                ],
                "output": "exports/silent-group.mp4",
                "overwrite": True,
            }
        )
        self.assertEqual(report["status"], "ok")
        self.assertFalse(report["artifact"]["boundaries"][0]["source_has_audio"])
        self.assertTrue(report["artifact"]["boundaries"][1]["source_has_audio"])

    def test_group_member_with_rendered_path_concatenates(self):
        subgroup = self.render_spec(
            {
                "schema_version": 1,
                "id": "sub",
                "members": [
                    {"ref": "a", "path": "scenes/a.mp4", "type": "scene"},
                    {"ref": "b", "path": "scenes/b.mp4", "type": "scene"},
                ],
                "output": "exports/subgroup.mp4",
                "overwrite": True,
            }
        )
        self.assertEqual(subgroup["status"], "ok")
        report = self.render_spec(
            {
                "schema_version": 1,
                "id": "parent",
                "members": [
                    {"ref": "sub", "path": "exports/subgroup.mp4", "type": "group"},
                    {"ref": "a", "path": "scenes/a.mp4", "type": "scene"},
                ],
                "output": "exports/parent.mp4",
                "overwrite": True,
            }
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["artifact"]["members"][0]["type"], "group")

    def test_unresolved_nested_group_rejected(self):
        with self.assertRaisesRegex(ValueError, "unresolved nested group"):
            self.render_spec(
                {
                    "schema_version": 1,
                    "id": "bad",
                    "members": [
                        {"ref": "a", "path": "scenes/a.mp4", "type": "scene"},
                        {"ref": "nested", "type": "group"},
                    ],
                    "output": "exports/bad.mp4",
                    "overwrite": True,
                }
            )

    def test_originals_remain_immutable(self):
        before = {
            path: path.read_bytes()
            for path in (self.scenes_dir / "a.mp4", self.scenes_dir / "b.mp4")
        }
        self.render_spec(
            {
                "schema_version": 1,
                "id": "immutable",
                "members": [
                    {"ref": "a", "path": "scenes/a.mp4", "type": "scene"},
                    {"ref": "b", "path": "scenes/b.mp4", "type": "scene"},
                ],
                "output": "exports/immutable.mp4",
                "overwrite": True,
            }
        )
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
