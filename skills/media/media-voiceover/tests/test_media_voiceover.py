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


validate = load_module("validate_media_voiceover", "validate_media_voiceover.py")
render = load_module("render_media_voiceover", "render_media_voiceover.py")

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


def make_voiceover(path: Path, duration: float = 0.5) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=880:sample_rate=48000:duration={duration}",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
    )


class ValidateSpecTests(unittest.TestCase):
    def base_spec(self, **overrides) -> dict:
        spec = {
            "schema_version": 1,
            "target": {"kind": "scene", "path": "scenes/a.mp4"},
            "source_audio": "preserve",
            "voiceover": {"path": "voice/vo.m4a"},
            "output": "exports/out.mp4",
            "overwrite": False,
        }
        spec.update(overrides)
        return spec

    def test_rejects_unknown_source_audio(self):
        spec = self.base_spec(source_audio="mute")
        with self.assertRaisesRegex(ValueError, "source_audio"):
            validate.validate_spec(spec)

    def test_lower_requires_gain_db(self):
        spec = self.base_spec(source_audio="lower")
        with self.assertRaisesRegex(ValueError, "gain_db"):
            validate.validate_spec(spec)

    def test_boost_requires_positive_gain_db(self):
        with self.assertRaisesRegex(ValueError, "gain_db"):
            validate.validate_spec(self.base_spec(source_audio="boost"))
        with self.assertRaisesRegex(ValueError, "must be > 0"):
            validate.validate_spec(self.base_spec(source_audio="boost", gain_db=0.0))
        normalized = validate.validate_spec(self.base_spec(source_audio="boost", gain_db=9.0))
        self.assertEqual(normalized["gain_db"], 9.0)

    def test_accepts_group_target_kind(self):
        spec = self.base_spec(target={"kind": "group", "path": "exports/group.mp4"})
        normalized = validate.validate_spec(spec)
        self.assertEqual(normalized["target"]["kind"], "group")

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            spec = self.base_spec()
            spec["target"]["path"] = "../secret.mp4"
            with self.assertRaisesRegex(ValueError, "traversal|escapes"):
                validate.validate_spec(spec, root)

    def test_output_must_not_alias_target_or_voiceover(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "scenes").mkdir()
            (root / "voice").mkdir()
            (root / "scenes" / "a.mp4").write_bytes(b"video")
            (root / "voice" / "vo.m4a").write_bytes(b"voice")
            for output in ("scenes/a.mp4", "voice/vo.m4a"):
                spec = self.base_spec(output=output, overwrite=True)
                with self.subTest(output=output), self.assertRaisesRegex(ValueError, "output.*input"):
                    validate.validate_spec(spec, root)

    def test_report_must_not_alias_output_or_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "scenes").mkdir()
            (root / "voice").mkdir()
            (root / "scenes" / "a.mp4").write_bytes(b"video")
            (root / "voice" / "vo.m4a").write_bytes(b"voice")
            for report in ("exports/out.mp4", "scenes/a.mp4", "voice/vo.m4a"):
                spec = self.base_spec(report=report)
                with self.subTest(report=report), self.assertRaisesRegex(ValueError, "report.*(?:output|input)"):
                    validate.validate_spec(spec, root)


@unittest.skipUnless(FFMPEG_OK, "ffmpeg required")
class RenderIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.scenes_dir = self.root / "scenes"
        self.exports = self.root / "exports"
        self.voice_dir = self.root / "voice"
        self.exports.mkdir()
        make_video(self.scenes_dir / "a.mp4", color="red", with_audio=True, freq=440)
        make_video(self.scenes_dir / "b.mp4", color="blue", with_audio=True, freq=660)
        make_video(self.scenes_dir / "silent.mp4", color="green", with_audio=False)
        make_voiceover(self.voice_dir / "vo.m4a")

        scene_group_render = importlib.util.spec_from_file_location(
            "render_scene_group",
            Path(__file__).resolve().parents[2] / "scene-group" / "scripts" / "render_scene_group.py",
        )
        assert scene_group_render and scene_group_render.loader
        sg_module = importlib.util.module_from_spec(scene_group_render)
        scene_group_render.loader.exec_module(sg_module)
        sg_module.render(
            self.root,
            {
                "schema_version": 1,
                "id": "g1",
                "members": [
                    {"ref": "a", "path": "scenes/a.mp4", "type": "scene"},
                    {"ref": "b", "path": "scenes/b.mp4", "type": "scene"},
                ],
                "output": "exports/group.mp4",
                "overwrite": True,
            },
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def render_spec(self, spec: dict) -> dict:
        return render.render(self.root, spec)

    def test_preserve_on_scene_target(self):
        report = self.render_spec(
            {
                "schema_version": 1,
                "target": {"kind": "scene", "path": "scenes/a.mp4"},
                "source_audio": "preserve",
                "voiceover": {"path": "voice/vo.m4a", "gain_db": -3.0},
                "output": "exports/scene-preserve.mp4",
                "overwrite": True,
            }
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["target"]["kind"], "scene")
        self.assertEqual(report["source_audio"], "preserve")
        self.assertFalse(report["audio"]["ducking"])
        filtergraph, _, _ = render.build_filtergraph(
            validate.validate_spec(
                {
                    "schema_version": 1,
                    "target": {"kind": "scene", "path": "scenes/a.mp4"},
                    "source_audio": "preserve",
                    "voiceover": {"path": "voice/vo.m4a"},
                    "output": "exports/check.mp4",
                }
            ),
            report["source_probe"],
        )
        self.assertIn("normalize=0", filtergraph)
        self.assertTrue(report["full_decode_verification"]["ok"])
        self.assertEqual(report["audio"]["sample_rate"], 48000)
        self.assertEqual(report["audio"]["channels"], 2)

    def test_preserve_on_group_target(self):
        report = self.render_spec(
            {
                "schema_version": 1,
                "target": {"kind": "group", "path": "exports/group.mp4"},
                "source_audio": "preserve",
                "voiceover": {"path": "voice/vo.m4a"},
                "output": "exports/group-preserve.mp4",
                "overwrite": True,
            }
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["target"]["kind"], "group")

    def test_remove_replaces_source_audio(self):
        report = self.render_spec(
            {
                "schema_version": 1,
                "target": {"kind": "scene", "path": "scenes/a.mp4"},
                "source_audio": "remove",
                "voiceover": {"path": "voice/vo.m4a"},
                "output": "exports/scene-remove.mp4",
                "overwrite": True,
            }
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["source_audio"], "remove")

    def test_lower_applies_gain_db(self):
        report = self.render_spec(
            {
                "schema_version": 1,
                "target": {"kind": "scene", "path": "scenes/a.mp4"},
                "source_audio": "lower",
                "gain_db": -18.0,
                "voiceover": {"path": "voice/vo.m4a"},
                "output": "exports/scene-lower.mp4",
                "overwrite": True,
            }
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["gain_db"], -18.0)

    def test_boost_applies_positive_gain_db(self):
        report = self.render_spec(
            {
                "schema_version": 1,
                "target": {"kind": "scene", "path": "scenes/a.mp4"},
                "source_audio": "boost",
                "gain_db": 9.0,
                "voiceover": {"path": "voice/vo.m4a"},
                "output": "exports/scene-boost.mp4",
                "overwrite": True,
            }
        )
        self.assertEqual(report["source_audio"], "boost")
        self.assertEqual(report["gain_db"], 9.0)

    def test_silent_target_with_preserve(self):
        report = self.render_spec(
            {
                "schema_version": 1,
                "target": {"kind": "scene", "path": "scenes/silent.mp4"},
                "source_audio": "preserve",
                "voiceover": {"path": "voice/vo.m4a"},
                "output": "exports/silent-preserve.mp4",
                "overwrite": True,
            }
        )
        self.assertEqual(report["status"], "ok")
        self.assertFalse(report["source_probe"]["has_audio"])

    def test_originals_remain_immutable(self):
        before = (self.scenes_dir / "a.mp4").read_bytes()
        self.render_spec(
            {
                "schema_version": 1,
                "target": {"kind": "scene", "path": "scenes/a.mp4"},
                "source_audio": "preserve",
                "voiceover": {"path": "voice/vo.m4a"},
                "output": "exports/immutable.mp4",
                "overwrite": True,
            }
        )
        self.assertEqual((self.scenes_dir / "a.mp4").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
