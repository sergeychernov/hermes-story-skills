import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SKILL_DIR = Path(__file__).resolve().parents[1]
DECISIONS_SCHEMA = SKILL_DIR / "templates" / "youtube-publication.schema.json"
MANIFEST_SCHEMA = SKILL_DIR / "templates" / "youtube-publication-preflight.schema.json"


def complete_target():
    return {
        "channel_key": "current",
        "audience": "everyone",
        "playlist_title": "Travel",
        "video_path": "exports/video.mp4",
        "cover_path": "exports/cover.jpg",
        "title_file": "youtube-title.txt",
        "description_file": "youtube-description.txt",
        "tags_file": "youtube-tags.txt",
        "verification_file": "exports/video.mp4.report.json",
        "cover_verification_file": "exports/cover.jpg.report.json",
        "category_id": "19",
        "default_language": "ru",
        "made_for_kids": False,
        "contains_synthetic_media": False,
        "notify_subscribers": False,
        "recording_date_decision": "omit",
        "location_decision": "description",
        "location_text": "Пекинский зоопарк, Пекин, Китай",
        "embeddable": True,
        "license": "youtube",
        "public_stats_viewable": True,
    }


def write_story_package(root: Path, target=None) -> Path:
    target = copy.deepcopy(target if target is not None else complete_target())
    (root / "exports").mkdir(parents=True, exist_ok=True)
    video = root / "exports/video.mp4"
    cover = root / "exports/cover.jpg"
    video.write_bytes(b"video")
    cover.write_bytes(b"cover")
    (root / "youtube-title.txt").write_text("Title\n", encoding="utf-8")
    (root / "youtube-description.txt").write_text(
        "Description\nПекинский зоопарк, Пекин, Китай\n", encoding="utf-8"
    )
    (root / "youtube-tags.txt").write_text("one\ntwo\n", encoding="utf-8")
    (root / "exports/video.mp4.report.json").write_text(json.dumps({
        "artifact": "exports/video.mp4",
        "status": "review-ready",
        "timeline": {"cover_frames": 4, "first_live_frame": 4},
        "video": {
            "full_decode": "passed",
            "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        },
    }), encoding="utf-8")
    (root / "exports/cover.jpg.report.json").write_text(json.dumps({
        "output": {
            "path": "exports/cover.jpg",
            "sha256": hashlib.sha256(cover.read_bytes()).hexdigest(),
        },
        "platform_contract": {
            "platform": "youtube",
            "surface": "standard_api_thumbnail",
        },
        "visual_review": "user-approved",
    }), encoding="utf-8")
    story = root / "story.json"
    story.write_text(json.dumps({
        "schema_version": 1,
        "id": "story-id",
        "publication": {"targets": {"youtube": target}},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return story


class YouTubeSchemaDrivenPreflightTests(unittest.TestCase):
    def test_jsonschema_runtime_enforces_non_required_then_constraints(self):
        from jsonschema_runtime import validate_or_raise

        schema = {
            "type": "object",
            "properties": {
                "mode": {"type": "string"},
                "value": {"type": "string"},
            },
            "allOf": [{
                "if": {"properties": {"mode": {"const": "strict"}}},
                "then": {"properties": {"value": {"const": "allowed"}}},
            }],
        }
        with self.assertRaisesRegex(ValueError, "must equal const"):
            validate_or_raise({"mode": "strict", "value": "denied"}, schema)
        validate_or_raise({"mode": "relaxed", "value": "denied"}, schema)

    def test_jsonschema_runtime_rejects_unknown_behavioral_extension(self):
        from jsonschema_runtime import validate_or_raise

        with self.assertRaisesRegex(ValueError, "unsupported JSON Schema keyword"):
            validate_or_raise({}, {"type": "object", "x-auto-resovle": {}})

    def test_schema_declares_every_publication_parameter(self):
        schema = json.loads(DECISIONS_SCHEMA.read_text(encoding="utf-8"))
        properties = schema["properties"]
        expected = {
            "channel_key", "audience", "playlist_title",
            "video_path", "cover_path", "title_file", "description_file",
            "tags_file", "verification_file", "cover_verification_file",
            "category_id", "default_language",
            "made_for_kids", "contains_synthetic_media", "notify_subscribers",
            "recording_date_decision", "recording_date",
            "location_decision", "location_text", "embeddable", "license",
            "public_stats_viewable",
        }
        self.assertTrue(expected.issubset(properties))
        self.assertTrue(expected - {"recording_date", "location_text"} <= set(schema["required"]))
        for name in (
            "channel_key", "audience", "playlist_title", "made_for_kids",
            "contains_synthetic_media", "notify_subscribers",
            "recording_date_decision", "location_decision",
        ):
            self.assertTrue(properties[name]["x-user-confirmation"])
            self.assertIn("x-question", properties[name])

    def test_assess_reads_story_applies_schema_defaults_and_returns_schema_questions(self):
        from youtube_metadata_preflight import assess_story

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = write_story_package(root, {"channel_key": "current"})
            result = assess_story(story, DECISIONS_SCHEMA, locale="ru")
        self.assertFalse(result["ready"])
        self.assertNotIn("video_path", result["missing_fields"])
        self.assertNotIn("video_path", result["confirmation_required"])
        self.assertEqual(result["normalized"]["video_path"], "exports/video.mp4")
        self.assertEqual(result["auto_resolution"]["blockers"], [])
        expected_user = [
            "audience", "playlist_title", "made_for_kids",
            "contains_synthetic_media", "notify_subscribers",
            "recording_date_decision", "location_decision",
        ]
        self.assertEqual(result["confirmation_required"], expected_user)
        self.assertEqual([q["field"] for q in result["questions"]], expected_user)
        self.assertEqual(result["normalized"]["category_id"], "19")
        self.assertEqual(result["normalized"]["default_language"], "ru")
        self.assertTrue(result["normalized"]["embeddable"])

    def test_question_text_and_choices_are_derived_from_schema(self):
        from youtube_metadata_preflight import assess_story

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = write_story_package(root, {})
            schema = json.loads(DECISIONS_SCHEMA.read_text(encoding="utf-8"))
            schema["properties"]["audience"]["x-question"]["ru"] = "CUSTOM PROMPT"
            schema["properties"]["audience"]["enum"] = ["everyone", "link"]
            custom = root / "custom.schema.json"
            custom.write_text(json.dumps(schema), encoding="utf-8")
            result = assess_story(story, custom, locale="ru")
        audience = next(q for q in result["questions"] if q["field"] == "audience")
        self.assertEqual(audience["prompt"], "CUSTOM PROMPT")
        self.assertEqual(audience["choices"], ["everyone", "link"])

    def test_schema_validation_rejects_invalid_types_enum_and_date(self):
        from youtube_metadata_preflight import assess_story

        cases = [
            ("made_for_kids", "no", "boolean"),
            ("audience", "world", "enum"),
            ("recording_date", "13 августа", "date format"),
        ]
        for field, value, message in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                target = complete_target()
                target[field] = value
                if field == "recording_date":
                    target["recording_date_decision"] = "set"
                story = write_story_package(Path(directory), target)
                with self.assertRaisesRegex(ValueError, message):
                    assess_story(story, DECISIONS_SCHEMA)

    def test_conditional_required_fields_come_from_schema(self):
        from youtube_metadata_preflight import assess_story

        with tempfile.TemporaryDirectory() as directory:
            target = complete_target()
            target["recording_date_decision"] = "set"
            target.pop("recording_date", None)
            target["location_decision"] = "description"
            target.pop("location_text", None)
            story = write_story_package(Path(directory), target)
            result = assess_story(story, DECISIONS_SCHEMA)
        self.assertEqual(result["missing_fields"], ["recording_date", "location_text"])
        self.assertEqual(result["confirmation_required"], ["recording_date", "location_text"])

    def test_unique_verified_artifacts_are_auto_resolved_from_schema_rules(self):
        from youtube_metadata_preflight import assess_story

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = complete_target()
            for field in (
                "video_path", "cover_path", "title_file", "description_file",
                "tags_file", "verification_file", "cover_verification_file",
            ):
                target.pop(field)
            story = write_story_package(root, target)
            video_report = root / "exports/video.mp4.report.json"
            video_report.write_text(json.dumps({
                "artifact": "exports/video.mp4",
                "status": "review-ready",
                "publication_approved": False,
                "timeline": {"cover_frames": 4, "first_live_frame": 4},
                "video": {
                    "full_decode": "passed",
                    "sha256": hashlib.sha256(
                        (root / "exports/video.mp4").read_bytes()
                    ).hexdigest(),
                },
            }), encoding="utf-8")
            cover_report = root / "exports/cover.jpg.report.json"
            cover_report.write_text(json.dumps({
                "platform_contract": {
                    "platform": "youtube",
                    "surface": "standard_api_thumbnail",
                },
                "output": {
                    "path": "exports/cover.jpg",
                    "sha256": hashlib.sha256(
                        (root / "exports/cover.jpg").read_bytes()
                    ).hexdigest(),
                },
                "visual_review": "user-approved",
            }), encoding="utf-8")
            result = assess_story(story, DECISIONS_SCHEMA)
        self.assertTrue(result["ready"])
        self.assertEqual(result["normalized"]["video_path"], "exports/video.mp4")
        self.assertEqual(
            result["normalized"]["verification_file"],
            "exports/video.mp4.report.json",
        )
        self.assertEqual(result["normalized"]["cover_path"], "exports/cover.jpg")
        self.assertEqual(
            result["normalized"]["cover_verification_file"],
            "exports/cover.jpg.report.json",
        )
        self.assertEqual(result["auto_resolution"]["ambiguities"], [])
        self.assertEqual(result["auto_resolution"]["blockers"], [])

    def test_multiple_verified_video_reports_return_ambiguity_not_mtime_choice(self):
        from youtube_metadata_preflight import assess_story

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = complete_target()
            target.pop("video_path")
            target.pop("verification_file")
            story = write_story_package(root, target)
            (root / "exports/video.mp4.report.json").unlink()
            for name in ("a", "b"):
                artifact = root / f"exports/{name}.mp4"
                artifact.write_bytes(name.encode())
                (root / f"exports/{name}.mp4.report.json").write_text(json.dumps({
                    "artifact": f"exports/{name}.mp4",
                    "status": "verified",
                    "timeline": {"cover_frames": 4, "first_live_frame": 4},
                    "video": {
                        "full_decode": "passed",
                        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    },
                }), encoding="utf-8")
            result = assess_story(story, DECISIONS_SCHEMA)
        ambiguity = next(
            item for item in result["auto_resolution"]["ambiguities"]
            if item["field"] == "video_path"
        )
        self.assertEqual(
            [candidate["value"] for candidate in ambiguity["candidates"]],
            ["exports/a.mp4", "exports/b.mp4"],
        )
        self.assertIn("video_path", result["missing_fields"])
        self.assertNotIn("video_path", result["confirmation_required"])

    def test_no_verified_video_report_is_technical_blocker(self):
        from youtube_metadata_preflight import assess_story

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = complete_target()
            target.pop("video_path")
            target.pop("verification_file")
            story = write_story_package(root, target)
            (root / "exports/video.mp4.report.json").write_text(json.dumps({
                "artifact": "exports/video.mp4",
                "status": "draft",
                "video": {"full_decode": "passed"},
            }), encoding="utf-8")
            result = assess_story(story, DECISIONS_SCHEMA)
        blocked = {item["field"] for item in result["auto_resolution"]["blockers"]}
        self.assertIn("video_path", blocked)
        self.assertIn("verification_file", blocked)

    def test_configured_paths_are_revalidated_against_resolver_contract(self):
        from youtube_metadata_preflight import assess_story

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = write_story_package(root)
            report_path = root / "exports/video.mp4.report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["status"] = "draft"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            result = assess_story(story, DECISIONS_SCHEMA)
        blocked = {item["field"] for item in result["auto_resolution"]["blockers"]}
        self.assertIn("video_path", blocked)
        self.assertIn("verification_file", blocked)
        self.assertFalse(result["ready"])

    def test_report_hash_mismatch_is_technical_blocker(self):
        from youtube_metadata_preflight import assess_story

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = write_story_package(root)
            (root / "exports/video.mp4").write_bytes(b"mutated-after-verification")
            result = assess_story(story, DECISIONS_SCHEMA)
        blocked = {item["field"] for item in result["auto_resolution"]["blockers"]}
        self.assertIn("video_path", blocked)
        self.assertFalse(result["ready"])

    def test_duplicate_reports_for_one_video_make_verification_ambiguous(self):
        from youtube_metadata_preflight import assess_story

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = complete_target()
            target.pop("video_path")
            target.pop("verification_file")
            story = write_story_package(root, target)
            original = root / "exports/video.mp4.report.json"
            duplicate = root / "exports/video-copy.mp4.report.json"
            duplicate.write_bytes(original.read_bytes())
            result = assess_story(story, DECISIONS_SCHEMA)
        self.assertEqual(result["normalized"]["video_path"], "exports/video.mp4")
        ambiguity = next(
            item for item in result["auto_resolution"]["ambiguities"]
            if item["field"] == "verification_file"
        )
        self.assertEqual(len(ambiguity["candidates"]), 2)
        self.assertIn("verification_file", result["missing_fields"])

    def test_configured_cover_must_be_platform_fit_and_user_approved(self):
        from youtube_metadata_preflight import assess_story

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = write_story_package(root)
            report_path = root / "exports/cover.jpg.report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["platform_contract"]["surface"] = "shorts_frame"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            result = assess_story(story, DECISIONS_SCHEMA)
        blocked = {item["field"] for item in result["auto_resolution"]["blockers"]}
        self.assertIn("cover_path", blocked)
        self.assertFalse(result["ready"])

    def test_cli_resolve_write_persists_only_unique_technical_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = complete_target()
            for field in (
                "video_path", "cover_path", "title_file", "description_file",
                "tags_file", "verification_file", "cover_verification_file", "category_id", "default_language",
                "embeddable", "license", "public_stats_viewable",
            ):
                target.pop(field)
            story = write_story_package(root, target)
            (root / "exports/video.mp4.report.json").write_text(json.dumps({
                "artifact": "exports/video.mp4",
                "status": "review-ready",
                "timeline": {"cover_frames": 4, "first_live_frame": 4},
                "video": {
                    "full_decode": "passed",
                    "sha256": hashlib.sha256(
                        (root / "exports/video.mp4").read_bytes()
                    ).hexdigest(),
                },
            }), encoding="utf-8")
            (root / "exports/cover.jpg.report.json").write_text(json.dumps({
                "platform_contract": {
                    "platform": "youtube",
                    "surface": "standard_api_thumbnail",
                },
                "output": {
                    "path": "exports/cover.jpg",
                    "sha256": hashlib.sha256(
                        (root / "exports/cover.jpg").read_bytes()
                    ).hexdigest(),
                },
                "visual_review": "user-approved",
            }), encoding="utf-8")
            command = [
                sys.executable, str(Path(__file__).with_name("youtube_metadata_preflight.py")),
                "resolve", "--story", str(story), "--schema", str(DECISIONS_SCHEMA),
                "--write",
            ]
            completed = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            target_after = json.loads(story.read_text(encoding="utf-8"))[
                "publication"
            ]["targets"]["youtube"]
        self.assertEqual(target_after["video_path"], "exports/video.mp4")
        self.assertEqual(target_after["cover_path"], "exports/cover.jpg")
        self.assertNotIn("category_id", target_after)

    def test_resolve_write_rejects_story_symlink_without_touching_target(self):
        from youtube_metadata_preflight import write_auto_resolved_paths

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual = write_story_package(root, complete_target())
            before = actual.read_bytes()
            linked = root / "linked-story.json"
            linked.symlink_to(actual.name)
            with self.assertRaisesRegex(ValueError, "symlink"):
                write_auto_resolved_paths(linked, DECISIONS_SCHEMA)
            self.assertEqual(actual.read_bytes(), before)
            self.assertTrue(linked.is_symlink())

    def test_complete_story_is_ready_and_does_not_need_separate_decisions_file(self):
        from youtube_metadata_preflight import assess_story

        with tempfile.TemporaryDirectory() as directory:
            story = write_story_package(Path(directory))
            result = assess_story(story, DECISIONS_SCHEMA)
        self.assertTrue(result["ready"])
        self.assertEqual(result["missing_fields"], [])
        self.assertEqual(result["questions"], [])

    def test_approved_manifest_is_schema_valid_and_bound_to_story_config_and_files(self):
        from youtube_metadata_preflight import build_approved_manifest, verify_approved_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = write_story_package(root)
            manifest = build_approved_manifest(
                story, DECISIONS_SCHEMA, MANIFEST_SCHEMA,
                approved_at="2026-08-16T04:00:00Z",
                approval_note="User approved exact publication summary",
            )
            path = root / "youtube-publication-preflight.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            config = verify_approved_manifest(path, story, DECISIONS_SCHEMA, MANIFEST_SCHEMA)
            self.assertEqual(config["channel_key"], "current")
            self.assertEqual(set(manifest["package"]), {
                "video", "cover", "title_file", "description_file", "tags_file",
                "verification_file", "cover_verification_file",
            })
            payload = json.loads(story.read_text(encoding="utf-8"))
            payload["publication"]["targets"]["youtube"]["notify_subscribers"] = True
            story.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "configuration hash"):
                verify_approved_manifest(path, story, DECISIONS_SCHEMA, MANIFEST_SCHEMA)

    def test_package_file_mutation_invalidates_manifest(self):
        from youtube_metadata_preflight import build_approved_manifest, verify_approved_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = write_story_package(root)
            manifest = build_approved_manifest(
                story, DECISIONS_SCHEMA, MANIFEST_SCHEMA,
                approved_at="2026-08-16T04:00:00Z", approval_note="approved",
            )
            path = root / "approved.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            (root / "youtube-title.txt").write_text("Changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "title_file hash"):
                verify_approved_manifest(path, story, DECISIONS_SCHEMA, MANIFEST_SCHEMA)

    def test_cover_approval_report_mutation_invalidates_manifest(self):
        from youtube_metadata_preflight import build_approved_manifest, verify_approved_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = write_story_package(root)
            manifest = build_approved_manifest(
                story, DECISIONS_SCHEMA, MANIFEST_SCHEMA,
                approved_at="2026-08-16T04:00:00Z", approval_note="approved",
            )
            path = root / "approved.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            report_path = root / "exports/cover.jpg.report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["review_note"] = "mutated after approval"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cover_verification_file hash"):
                verify_approved_manifest(path, story, DECISIONS_SCHEMA, MANIFEST_SCHEMA)

    def test_cli_assess_uses_story_and_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = write_story_package(root, {})
            completed = subprocess.run([
                sys.executable, str(Path(__file__).with_name("youtube_metadata_preflight.py")),
                "assess", "--story", str(story), "--schema", str(DECISIONS_SCHEMA),
                "--locale", "ru",
            ], text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertFalse(result["ready"])
            self.assertIn("audience", result["confirmation_required"])

    def test_non_exact_four_frame_reports_are_technical_blockers(self):
        from youtube_metadata_preflight import assess_story

        invalid_timelines = [
            {"cover_frames": 1, "first_live_frame": 1},
            {"cover_frames": 4, "first_live_frame": 1},
            {"cover_frames": 24, "first_live_frame": 24},
            None,
        ]
        for timeline in invalid_timelines:
            with self.subTest(timeline=timeline), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                story = write_story_package(root, complete_target())
                report_path = root / "exports/video.mp4.report.json"
                report = json.loads(report_path.read_text(encoding="utf-8"))
                if timeline is None:
                    report.pop("timeline", None)
                else:
                    report["timeline"] = timeline
                report_path.write_text(json.dumps(report), encoding="utf-8")
                result = assess_story(story, DECISIONS_SCHEMA)
                self.assertFalse(result["ready"])
                self.assertTrue(any(
                    blocker["field"] == "video_path"
                    for blocker in result["auto_resolution"]["blockers"]
                ))

    def test_cli_approve_requires_explicit_flag_and_writes_private_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            story = write_story_package(root)
            output = root / "approved.json"
            command = [
                sys.executable, str(Path(__file__).with_name("youtube_metadata_preflight.py")),
                "approve", "--story", str(story),
                "--schema", str(DECISIONS_SCHEMA),
                "--manifest-schema", str(MANIFEST_SCHEMA),
                "--approved-at", "2026-08-16T04:00:00Z",
                "--approval-note", "User approved exact summary",
                "--output", str(output),
            ]
            refused = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn("explicit --approved", refused.stderr)
            accepted = subprocess.run(command + ["--approved"], text=True, capture_output=True)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
            manifest = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(manifest["platform"], "youtube")


if __name__ == "__main__":
    unittest.main()
