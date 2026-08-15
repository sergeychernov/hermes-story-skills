#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHORTS = ROOT / "skills/media/shorts-assembly"
SOUNDTRACK = ROOT / "skills/media/story-soundtrack"

LEGACY_SHORTS_PATHS = (
    "references/deterministic-story-music.md",
    "references/subjective-soundtrack-diagnosis.md",
    "scripts/encode_story_audio_preview.py",
    "scripts/render_pentatonic_story_score.py",
    "scripts/tests/test_story_music_tools.py",
    "templates/pentatonic-story-score.json",
    "templates/story-audio-approval-preview.json",
)
LEGACY_IDENTIFIERS = (
    "render_pentatonic_story_score",
    "encode_story_audio_preview",
    "chinese_travel_pentatonic_v1",
    "pentatonic-story-score.json",
    "story-audio-approval-preview.json",
    "deterministic-story-music.md",
    "test_story_music_tools",
)


class SoundtrackOwnershipTests(unittest.TestCase):
    def test_soundtrack_policy_has_one_owner_and_legacy_bundle_is_retired(self):
        for relative in LEGACY_SHORTS_PATHS:
            self.assertFalse((SHORTS / relative).exists(), relative)

        diagnosis = SOUNDTRACK / "references/subjective-soundtrack-diagnosis.md"
        self.assertTrue(diagnosis.is_file())
        soundtrack_skill = (SOUNDTRACK / "SKILL.md").read_text(encoding="utf-8")
        shorts_skill = (SHORTS / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/subjective-soundtrack-diagnosis.md", soundtrack_skill)
        self.assertIn("version: 1.0.2", soundtrack_skill)
        self.assertIn("version: 1.5.2", shorts_skill)
        self.assertIn("stop soundtrack work in this skill", shorts_skill)
        self.assertNotIn("Render generated accompaniment", shorts_skill)
        self.assertNotIn("Audio-only approval files", shorts_skill)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("deterministic music helpers", readme)

        active_text = "\n".join(
            path.read_text(encoding="utf-8", errors="strict")
            for base in (SHORTS, SOUNDTRACK)
            for path in base.rglob("*")
            if path.is_file()
            and path != Path(__file__).resolve()
            and path.suffix in {".md", ".py", ".json"}
        )
        for identifier in LEGACY_IDENTIFIERS:
            self.assertNotIn(identifier, active_text)

    def test_cover_creation_and_timeline_insertion_have_distinct_owners(self):
        old_reference = SHORTS / "references/youtube-cover-insertion.md"
        insertion = SHORTS / "references/platform-cover-timeline-insertion.md"
        frame_contract = SHORTS / "references/frame-exact-cover-timeline.md"
        self.assertFalse(old_reference.exists())
        self.assertTrue(insertion.is_file())

        insertion_text = insertion.read_text(encoding="utf-8")
        self.assertIn("approved static-cover-collage artifact", insertion_text)
        self.assertIn("`shorts-assembly` owns the exact cover-frame count", insertion_text)
        self.assertNotIn("Build the cover as a standalone", insertion_text)
        self.assertNotIn("compose/render one new soundtrack", insertion_text)

        frame_text = frame_contract.read_text(encoding="utf-8")
        self.assertIn("story-soundtrack", frame_text)
        self.assertNotIn("Compose after the final visual timeline", frame_text)

        static_skill = (ROOT / "skills/media/static-cover-collage/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("version: 1.3.1", static_skill)
        self.assertIn("`static-cover-collage` ownership ends", static_skill)
        self.assertNotIn("default cover-scene duration", static_skill)
        self.assertNotIn("load `still-image-animation` and create", static_skill)


if __name__ == "__main__":
    unittest.main()
