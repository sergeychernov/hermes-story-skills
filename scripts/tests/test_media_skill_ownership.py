#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "skills/media"
SHORTS = MEDIA / "shorts-assembly"
SOUNDTRACK = MEDIA / "story-soundtrack"
STATIC_COVER = MEDIA / "static-cover-collage"
STORY = MEDIA / "story"


class MediaSkillOwnershipTests(unittest.TestCase):
    def test_soundtrack_policy_has_one_canonical_owner(self):
        diagnosis = SOUNDTRACK / "references/subjective-soundtrack-diagnosis.md"
        self.assertTrue(diagnosis.is_file())

        soundtrack_skill = (SOUNDTRACK / "SKILL.md").read_text(encoding="utf-8")
        shorts_skill = (SHORTS / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/subjective-soundtrack-diagnosis.md", soundtrack_skill)
        self.assertIn("load `story-soundtrack` and stop soundtrack work in this skill", shorts_skill)
        self.assertIn("mux the exact approved audio", shorts_skill)

    def test_cover_creation_and_timeline_insertion_have_distinct_owners(self):
        insertion = SHORTS / "references/platform-cover-timeline-insertion.md"
        frame_contract = SHORTS / "references/frame-exact-cover-timeline.md"
        self.assertTrue(insertion.is_file())
        self.assertTrue(frame_contract.is_file())

        insertion_text = insertion.read_text(encoding="utf-8")
        self.assertIn("approved static-cover-collage artifact", insertion_text)
        self.assertIn("`shorts-assembly` owns the exact cover-frame count", insertion_text)
        self.assertIn("`story-soundtrack` owns audio-only rendering", insertion_text)
        self.assertIn("never inherit its default duration or fade settings", insertion_text)

        frame_text = frame_contract.read_text(encoding="utf-8")
        self.assertIn("Hand the resulting cover-inclusive MP4 and exact frame contract to `story-soundtrack`", frame_text)

        static_skill = (STATIC_COVER / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`static-cover-collage` ownership ends at the approved hash-bound static artifact", static_skill)
        self.assertIn("`shorts-assembly` owns the target-specific cover-frame count", static_skill)

        story_skill = (STORY / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`shorts-assembly` for exact static cover-frame rendering", story_skill)
        self.assertIn("animated cover derivative", story_skill)

        shorts_skill = (SHORTS / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Approved static cover insertion is the exception", shorts_skill)


if __name__ == "__main__":
    unittest.main()
