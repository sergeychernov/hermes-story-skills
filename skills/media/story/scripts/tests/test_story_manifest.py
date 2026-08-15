import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from story_manifest import validate_story


class StoryManifestTests(unittest.TestCase):
    def test_accepts_non_travel_family_story(self):
        story = validate_story({
            "schema_version": 1,
            "id": "birthday-cake",
            "title": "Свечи погасли не сразу",
            "status": "collecting",
            "arc": {"beats": ["setup", "surprise", "reaction"]},
            "scenes": [],
            "context": {"occasion": "birthday", "people": ["family"]},
            "publication": {"status": "not-approved"},
        })
        self.assertEqual(story["context"]["places"], [])
        self.assertEqual(story["story_type"], "moment")

    def test_accepts_travel_only_as_optional_context(self):
        story = validate_story({
            "schema_version": 1,
            "id": "evening-walk",
            "title": "После концерта",
            "status": "collecting",
            "arc": {"beats": ["hook", "closing"]},
            "scenes": [],
            "context": {
                "source": "travel",
                "places": ["Belgrade"],
                "extensions": {"travel": {"route": ["venue", "hotel"]}},
            },
            "publication": {"status": "not-approved"},
        })
        self.assertEqual(story["context"]["extensions"]["travel"]["route"][0], "venue")

    def test_rejects_travel_specific_root_field(self):
        with self.assertRaisesRegex(ValueError, "unknown root fields: destination"):
            validate_story({
                "schema_version": 1,
                "id": "trip",
                "title": "Trip",
                "status": "collecting",
                "arc": {"beats": []},
                "scenes": [],
                "destination": "Belgrade",
                "publication": {"status": "not-approved"},
            })

    def test_render_ready_requires_every_scene_approved(self):
        story = validate_story({
            "schema_version": 1,
            "id": "tiny-story",
            "title": "Tiny",
            "status": "scene-review",
            "arc": {"beats": ["setup", "payoff"]},
            "scenes": [
                {"id": "s1", "media_id": "m1", "kind": "image", "approval": "approved"},
                {"id": "s2", "media_id": "m2", "kind": "video", "approval": "pending"},
            ],
            "publication": {"status": "not-approved"},
        })
        self.assertFalse(story["render_ready"])
        self.assertEqual(story["pending_scene_ids"], ["s2"])

    def test_accepts_scene_like_group_with_members_and_artifact(self):
        story = validate_story({
            "schema_version": 1,
            "id": "group-story",
            "title": "Grouped",
            "status": "scene-review",
            "arc": {"beats": ["development", "payoff"]},
            "scenes": [
                {"id": "s1", "media_id": "m1", "kind": "image", "approval": "approved"},
                {"id": "s2", "media_id": "m2", "kind": "video", "approval": "approved"},
                {
                    "id": "g1", "media_id": "m1+m2", "kind": "group", "approval": "pending",
                    "members": ["s1", "s2"], "artifact": "exports/g1.mp4", "report": "exports/g1.json"
                },
            ],
            "publication": {"status": "not-approved"},
        })
        self.assertEqual(story["scenes"][2]["kind"], "group")
        self.assertEqual(story["scenes"][2]["members"], ["s1", "s2"])
        self.assertEqual(story["pending_scene_ids"], ["g1"])

    def test_rejects_duplicate_self_or_unknown_group_members(self):
        base_scenes = [
            {"id": "s1", "media_id": "m1", "kind": "image", "approval": "approved"},
            {"id": "s2", "media_id": "m2", "kind": "video", "approval": "approved"},
        ]
        for members, message in (
            (["s1", "s1"], "unique"),
            (["s1", "g1"], "itself"),
            (["s1", "missing"], "unknown"),
        ):
            group = {
                "id": "g1", "media_id": "m1+m2", "kind": "group", "approval": "pending",
                "members": members, "artifact": "exports/g1.mp4",
            }
            with self.subTest(members=members), self.assertRaisesRegex(ValueError, message):
                validate_story({
                    "schema_version": 1,
                    "id": "group-story",
                    "title": "Grouped",
                    "status": "scene-review",
                    "arc": {"beats": []},
                    "scenes": [*base_scenes, group],
                    "publication": {"status": "not-approved"},
                })

    def test_rejects_group_without_two_members_or_artifact(self):
        base = {
            "schema_version": 1, "id": "bad-group", "title": "Bad", "status": "scene-review",
            "arc": {"beats": []}, "publication": {"status": "not-approved"},
        }
        for scene in (
            {"id": "g1", "media_id": "m1", "kind": "group", "approval": "pending", "members": ["s1"], "artifact": "g.mp4"},
            {"id": "g1", "media_id": "m1+m2", "kind": "group", "approval": "pending", "members": ["s1", "s2"]},
        ):
            with self.subTest(scene=scene), self.assertRaisesRegex(ValueError, "group"):
                validate_story({**base, "scenes": [scene]})

    def test_rejects_wrong_container_types(self):
        base = {
            "schema_version": 1,
            "id": "bad-types",
            "title": "Bad",
            "status": "collecting",
            "arc": {"beats": []},
            "scenes": [],
            "context": {},
            "publication": {"status": "not-approved"},
        }
        for field, wrong in (("arc", []), ("scenes", {}), ("context", []), ("publication", [])):
            case = dict(base)
            case[field] = wrong
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                validate_story(case)

    def test_rejects_non_string_text_and_normalizes_scene_ids(self):
        base = {
            "schema_version": 1,
            "id": "story",
            "title": "Title",
            "status": "scene-review",
            "arc": {"beats": []},
            "scenes": [{"id": " s1 ", "media_id": " m1 ", "kind": "image", "approval": "pending"}],
            "publication": {"status": "not-approved"},
        }
        normalized = validate_story(base)
        self.assertEqual(normalized["scenes"][0]["id"], "s1")
        self.assertEqual(normalized["scenes"][0]["media_id"], "m1")
        self.assertEqual(normalized["pending_scene_ids"], ["s1"])
        bad = dict(base)
        bad["title"] = 42
        with self.assertRaisesRegex(ValueError, "title"):
            validate_story(bad)

    def test_rejects_verified_or_published_story_without_approved_scenes(self):
        with self.assertRaisesRegex(ValueError, "verified.*render-ready"):
            validate_story({
                "schema_version": 1,
                "id": "contradiction",
                "title": "Contradiction",
                "status": "verified",
                "arc": {"beats": []},
                "scenes": [],
                "publication": {"status": "published"},
            })

    def test_cli_writes_normalized_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "draft.json"
            output = root / "story.json"
            source.write_text(json.dumps({
                "schema_version": 1,
                "id": "project-demo",
                "title": "First demo",
                "status": "collecting",
                "arc": {"beats": ["hook"]},
                "scenes": [],
                "publication": {"status": "not-approved"},
            }), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_story.py"), str(source), "--output", str(output)],
                check=True,
                text=True,
                capture_output=True,
            )
            report = json.loads(completed.stdout)
            normalized = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "ok")
            self.assertEqual(normalized["id"], "project-demo")
            self.assertEqual(normalized["context"]["source"], "conversation")


if __name__ == "__main__":
    unittest.main()
