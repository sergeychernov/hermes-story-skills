import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from travel_brief import to_story_context, validate_travel_brief


class TravelBriefTests(unittest.TestCase):
    def base(self):
        return {
            "schema_version": 1,
            "id": "day-one",
            "title": "Day one",
            "status": "validated",
            "travelers": ["family"],
            "constraints": {"avoid_modes": ["ferry"]},
            "route": {
                "origin": "Hotel",
                "destination": "Museum",
                "legs": [{"mode": "walk", "from": "Hotel", "to": "Museum"}],
            },
            "capture_suggestions": [{"when": "arrival", "subject": "entrance", "story_hint": "first impression"}],
            "sources": [{"kind": "map", "url": "https://example.test/route", "observed_at": "2026-07-26T12:00:00Z"}],
        }

    def test_rejects_route_that_violates_avoid_modes(self):
        brief = self.base()
        brief["route"]["legs"][0]["mode"] = "ferry"
        with self.assertRaisesRegex(ValueError, "avoid_modes"):
            validate_travel_brief(brief)

    def test_rejects_route_that_violates_avoid_modes_case_insensitively(self):
        brief = self.base()
        brief["route"]["legs"][0]["mode"] = "FERRY"
        with self.assertRaisesRegex(ValueError, "avoid_modes"):
            validate_travel_brief(brief)

    def test_validated_brief_requires_real_https_url_and_timestamp(self):
        for field, value in (("url", "not-a-url"), ("observed_at", "yesterday")):
            brief = self.base()
            brief["sources"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                validate_travel_brief(brief)

    def test_projects_travel_only_inside_story_context_extension(self):
        context = to_story_context(validate_travel_brief(self.base()))
        self.assertIn("travel", context["extensions"])
        self.assertNotIn("route", context)
        self.assertEqual(context["source"], "travel-planning")

    def test_cli_validates_template(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "brief.json"
            output = Path(td) / "normalized.json"
            source.write_text(json.dumps(self.base()), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_travel_brief.py"), str(source), "--output", str(output)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "validated")


if __name__ == "__main__":
    unittest.main()
