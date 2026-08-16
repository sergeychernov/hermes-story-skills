from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "layout_selector.py"
spec = importlib.util.spec_from_file_location("animated_collage_layout_selector", MODULE_PATH)
selector = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(selector)


class LayoutSelectorTests(unittest.TestCase):
    def test_unique_sequence_returns_canonical_layout_id(self):
        self.assertEqual(selector.select_layout("ppl"), "2+1")

    def test_unknown_sequence_reports_no_match_without_rejecting_its_length(self):
        with self.assertRaises(selector.UnsupportedLayoutSequenceError) as caught:
            selector.select_layout("ppllppl")
        self.assertEqual(caught.exception.sequence, "ppllppl")
        self.assertEqual(caught.exception.candidates, ())

    def test_production_six_portraits_offer_grouping_and_direction_choices(self):
        expected = (
            "portrait-pairs-descending",
            "portrait-pairs-ascending",
            "portrait-triples-descending",
            "portrait-triples-ascending",
        )
        with self.assertRaises(selector.AmbiguousLayoutSequenceError) as caught:
            selector.select_layout("pppppp")
        self.assertEqual(caught.exception.candidates, expected)
        self.assertEqual(
            selector.select_layout("pppppp", requested="portrait-triples-ascending"),
            "portrait-triples-ascending",
        )

    def test_multiple_compatible_layouts_require_user_choice(self):
        catalog = (
            selector.LayoutOption("pairs-descending", "pppppp", "Pairs from top to bottom"),
            selector.LayoutOption("pairs-ascending", "pppppp", "Pairs from bottom to top"),
            selector.LayoutOption("triples-descending", "pppppp", "Triples from top to bottom"),
        )
        with self.assertRaises(selector.AmbiguousLayoutSequenceError) as caught:
            selector.select_layout("pppppp", catalog=catalog)
        self.assertEqual(
            caught.exception.candidates,
            ("pairs-descending", "pairs-ascending", "triples-descending"),
        )

    def test_explicit_candidate_resolves_ambiguity(self):
        catalog = (
            selector.LayoutOption("pairs-descending", "pppppp", "Pairs from top to bottom"),
            selector.LayoutOption("pairs-ascending", "pppppp", "Pairs from bottom to top"),
        )
        self.assertEqual(
            selector.select_layout("pppppp", requested="pairs-ascending", catalog=catalog),
            "pairs-ascending",
        )

    def test_explicit_incompatible_layout_is_rejected(self):
        with self.assertRaises(selector.IncompatibleLayoutSequenceError) as caught:
            selector.select_layout("ppl", requested="2x2")
        self.assertEqual(caught.exception.requested, "2x2")
        self.assertEqual(caught.exception.expected_sequences, ("pppp",))

    def test_invalid_symbols_are_rejected_before_catalog_lookup(self):
        with self.assertRaisesRegex(ValueError, "only 'p' and 'l'"):
            selector.select_layout("plxp")

    def test_empty_sequence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            selector.select_layout("")

    def test_matching_layouts_returns_metadata_for_interactive_choice(self):
        catalog = (
            selector.LayoutOption("pairs", "pppppp", "Group portraits by two"),
            selector.LayoutOption("triples", "pppppp", "Group portraits by three"),
        )
        self.assertEqual(
            selector.matching_layouts("pppppp", catalog=catalog),
            catalog,
        )


if __name__ == "__main__":
    unittest.main()
