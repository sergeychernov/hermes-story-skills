from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

MODULE_PATH = Path(__file__).resolve().parents[1] / "render_collage.py"
SPEC = importlib.util.spec_from_file_location("render_collage", MODULE_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class LayoutTests(unittest.TestCase):
    def sources(self, n: int, safe: tuple[int, ...] = ()):
        return [{"path": f"photos/{i}.jpg", "title_safe": i in safe} for i in range(n)]

    def test_five_images_choose_people_safe_2_plus_2_plus_1(self):
        name, order = mod.choose_layout(5, self.sources(5, (2,)), "Title", "auto")
        self.assertEqual(name, "2+2+1")
        self.assertEqual(order[-1], 2)

    def test_six_images_with_one_safe_source_uses_full_width_bottom(self):
        name, order = mod.choose_layout(6, self.sources(6, (1,)), "Title", "auto")
        self.assertEqual(name, "2+2+1+1")
        self.assertEqual(order[-1], 1)

    def test_six_images_with_two_safe_sources_choose_grid(self):
        name, order = mod.choose_layout(6, self.sources(6, (1, 4)), "Title", "auto")
        self.assertEqual(name, "2x3")
        self.assertEqual(order[-2:], [1, 4])

    def test_title_without_safe_source_fails(self):
        with self.assertRaisesRegex(ValueError, "title_safe"):
            mod.choose_layout(5, self.sources(5), "Title", "auto")

    def test_auto_animation_hero_last(self):
        selected = mod.choose_animation("auto", "2+2+1", [{}, {"hero": True}])
        self.assertEqual(selected, "hero_last")

    def test_title_wrap(self):
        self.assertEqual(mod.wrap_title("Опять мимо Запретного города", 15), "Опять мимо\nЗапретного\nгорода")

    def test_paths_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "escapes root"):
                mod.safe_path(Path(tmp).resolve(), "../secret.jpg")

    def test_layout_geometry_rejects_gap(self):
        with self.assertRaisesRegex(ValueError, "cover canvas"):
            mod.validate_layout_geometry([(0, 0, 100, 99)], 100, 100)
    def test_paper_edge_mask_is_seeded_and_varied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b, c = root / "a.pgm", root / "b.pgm", root / "c.pgm"
            mod.write_paper_edge_mask(a, 40, 30, 7, 3)
            mod.write_paper_edge_mask(b, 40, 30, 7, 3)
            mod.write_paper_edge_mask(c, 40, 30, 8, 3)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertNotEqual(a.read_bytes(), c.read_bytes())
            self.assertIn(0, a.read_bytes())
            self.assertIn(255, a.read_bytes())

    def test_paper_edge_requires_seed(self):
        raw = {"schema_version": 1, "sources": self.sources(2, (1,)), "output": "out.mp4", "paper_edge": True,
               "title": {"text": "T"}}
        with self.assertRaisesRegex(ValueError, "paper_edge_seed"):
            mod.validate_spec(raw)


class OverlapStackTests(unittest.TestCase):
    SCENE_002_BASE_CELLS = [
        [0, 0, 1080, 720],
        [0, 720, 540, 650],
        [540, 720, 540, 650],
        [0, 1370, 1080, 550],
    ]
    SCENE_005_BASE_CELLS = [
        [0, 0, 720, 500],
        [720, 0, 360, 500],
        [0, 500, 1080, 880],
        [0, 1380, 540, 540],
        [540, 1380, 540, 540],
    ]

    def sources(self, n: int, safe: tuple[int, ...] = ()):
        return [{"path": f"photos/{i}.jpg", "title_safe": i in safe} for i in range(n)]

    def _assert_no_full_canvas_expansion(
        self,
        expanded: list[tuple[int, int, int, int]],
        base_cells: list[tuple[int, int, int, int]],
        width: int = 1080,
        height: int = 1920,
    ) -> None:
        canvas_area = width * height
        for cell, base in zip(expanded, base_cells):
            if base[2] * base[3] < canvas_area:
                self.assertLess(cell[2] * cell[3], canvas_area)
                self.assertNotEqual(cell, (0, 0, width, height))

    def _five_panel_setup(self, base_layout: str = "2+2+1"):
        base_rows = mod._rows_for_layout(base_layout, 1080, 1920)
        base_cells = [cell for row in base_rows for cell in row]
        directions = mod.overlap_entrance_directions(base_rows)
        cells = mod.overlap_stack_cells(base_cells, base_rows, directions, 1080, 1920, 0.40)
        return base_rows, base_cells, cells

    def test_overlap_stack_geometry_count_and_overlap(self):
        base_rows, base_cells, cells = self._five_panel_setup("2+2+1")
        self.assertEqual(len(cells), 5)
        meta = mod.validate_overlap_stack_geometry(cells, base_cells, 1080, 1920, 0.40)
        self.assertEqual(meta["overlap_ratio"], 0.40)
        self.assertGreaterEqual(len(meta["orientation_signature"]), 2)
        self.assertGreater(len(meta["unique_widths"]), 1)
        self.assertTrue(any(mod._rect_contains(expanded, base) for expanded, base in zip(cells, base_cells)))
        for expanded, base in zip(cells, base_cells):
            self.assertTrue(mod._rect_contains(expanded, base))
        self._assert_no_full_canvas_expansion(cells, base_cells)

    def test_bottom_row_does_not_expand_to_full_canvas(self):
        _, base_cells, cells = self._five_panel_setup("2+2+1")
        bottom_base = base_cells[-1]
        above_h = base_cells[-2][3]
        bottom_expanded = cells[-1]
        extend = mod._unilateral_extend(above_h, 0.40)
        self.assertEqual(bottom_expanded, (0, bottom_base[1] - extend, 1080, bottom_base[3] + extend))
        self._assert_no_full_canvas_expansion(cells, base_cells)

    def test_scene_002_custom_base_cells(self):
        base_cells = mod.parse_base_cells(self.SCENE_002_BASE_CELLS, 1080, 1920)
        base_rows = mod._rows_from_base_cells(base_cells)
        directions = mod.overlap_entrance_directions(base_rows)
        cells = mod.overlap_stack_cells(base_cells, base_rows, directions, 1080, 1920, 0.40)
        meta = mod.validate_overlap_stack_geometry(
            cells, base_cells, 1080, 1920, 0.40, base_rows=base_rows
        )
        self.assertEqual(base_cells[0], (0, 0, 1080, 720))
        self.assertEqual(base_cells[-1], (0, 1370, 1080, 550))
        self.assertGreaterEqual(len(meta["orientation_signature"]), 2)
        self._assert_no_full_canvas_expansion(cells, base_cells)
        # Exact cross-row geometry: top full-width, two middle, bottom full-width.
        self.assertEqual(cells[0], (0, 0, 1080, 720))
        self.assertEqual(cells[1], (0, 432, 675, 938))
        self.assertEqual(cells[2], (405, 432, 675, 938))
        self.assertEqual(cells[3], (0, 1110, 1080, 810))
        cross = meta["cross_row_overlap_ratio"]
        self.assertEqual(len(cross), 3)
        for ratio in cross:
            self.assertGreater(ratio, 0.0)
        # Both middle cards overlap the top row; bottom overlaps the middle row.
        self.assertGreater(mod._overlap_fraction(cells[1], cells[0]), 0.0)
        self.assertGreater(mod._overlap_fraction(cells[2], cells[0]), 0.0)
        self.assertGreater(mod._overlap_fraction(cells[3], cells[2]), 0.0)
        self.assertIn("cross_row_overlap_ratio", meta)

    def test_scene_005_metro_custom_base_cells(self):
        base_cells = mod.parse_base_cells(self.SCENE_005_BASE_CELLS, 1080, 1920)
        base_rows = mod._rows_from_base_cells(base_cells)
        directions = mod.overlap_entrance_directions(base_rows)
        cells = mod.overlap_stack_cells(base_cells, base_rows, directions, 1080, 1920, 0.40)
        meta = mod.validate_overlap_stack_geometry(
            cells, base_cells, 1080, 1920, 0.40, base_rows=base_rows
        )
        widths = {w for _, _, w, _ in base_cells}
        self.assertIn(720, widths)
        self.assertIn(360, widths)
        self.assertIn(1080, widths)
        self.assertGreaterEqual(len(meta["orientation_signature"]), 2)
        self._assert_no_full_canvas_expansion(cells, base_cells)
        # Exact cross-row geometry: 720+360 top, full-width center, 540+540 bottom.
        self.assertEqual(cells[0], (0, 0, 900, 500))
        self.assertEqual(cells[1], (630, 0, 450, 500))
        self.assertEqual(cells[2], (0, 300, 1080, 1080))
        self.assertEqual(cells[3], (0, 1028, 675, 892))
        self.assertEqual(cells[4], (405, 1028, 675, 892))
        cross = meta["cross_row_overlap_ratio"]
        self.assertEqual(len(cross), 3)
        for ratio in cross:
            self.assertGreater(ratio, 0.0)
        # Center overlaps top row; bottom pair overlaps center.
        self.assertGreater(mod._overlap_fraction(cells[2], cells[0]), 0.0)
        self.assertGreater(mod._overlap_fraction(cells[3], cells[2]), 0.0)
        self.assertGreater(mod._overlap_fraction(cells[4], cells[2]), 0.0)
        self.assertIn("cross_row_overlap_ratio", meta)

    def test_base_cells_normalized_and_pixel_equivalent(self):
        normalized = mod.serialize_base_cells(
            [tuple(cell) for cell in self.SCENE_002_BASE_CELLS], 1080, 1920
        )
        pixel_cells = mod.parse_base_cells(self.SCENE_002_BASE_CELLS, 1080, 1920)
        norm_cells = mod.parse_base_cells(normalized, 1080, 1920)
        self.assertEqual(pixel_cells, norm_cells)

    def test_base_cells_must_cover_canvas(self):
        broken = [[0, 0, 540, 960], [540, 0, 540, 960]]
        with self.assertRaisesRegex(ValueError, "cover canvas"):
            mod.parse_base_cells(broken, 1080, 1920)

    def test_base_cells_count_must_match_sources(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(5),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
            "base_cells": self.SCENE_002_BASE_CELLS,
        }
        with self.assertRaisesRegex(ValueError, "must match source count"):
            mod.validate_spec(spec)

    def test_base_cells_rejects_explicit_base_layout(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(4),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
            "base_layout": "2+2+1",
            "base_cells": self.SCENE_002_BASE_CELLS,
        }
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            mod.validate_spec(spec)

    def test_validate_spec_accepts_scene_002_base_cells(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(4),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
            "base_cells": self.SCENE_002_BASE_CELLS,
        }
        normalized = mod.validate_spec(spec)
        self.assertEqual(normalized["base_layout"], "custom")
        self.assertEqual(len(normalized["base_cells"]), 4)

    def test_overlap_stack_preserves_mixed_orientations_for_2_plus_1_plus_2(self):
        _, base_cells, cells = self._five_panel_setup("2+1+2")
        self.assertGreaterEqual(len(mod._orientation_signature(base_cells)), 2)
        widths = {w for _, _, w, _ in cells}
        heights = {h for _, _, _, h in cells}
        self.assertGreater(len(widths), 1)
        self.assertGreater(len(heights), 1)
        self.assertNotEqual(widths, heights)

    def test_base_layout_only_for_overlap_stack(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(4),
            "output": "exports/out.mp4",
            "layout": "2x2",
            "base_layout": "2+1+1",
        }
        with self.assertRaisesRegex(ValueError, "only valid"):
            mod.validate_spec(spec)

    def test_default_base_layout_for_overlap_stack(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(5),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
        }
        normalized = mod.validate_spec(spec)
        self.assertEqual(normalized["base_layout"], "2+2+1")

    def test_explicit_base_layout_2_plus_1_plus_2(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(5),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
            "base_layout": "2+1+2",
        }
        normalized = mod.validate_spec(spec)
        self.assertEqual(normalized["base_layout"], "2+1+2")

    def test_overlap_ratio_bounds(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(4),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
            "overlap_ratio": 0.25,
        }
        with self.assertRaisesRegex(ValueError, "overlap_ratio"):
            mod.validate_spec(spec)

    def test_overlap_ratio_only_for_overlap_stack(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(4),
            "output": "exports/out.mp4",
            "layout": "2x2",
            "overlap_ratio": 0.40,
        }
        with self.assertRaisesRegex(ValueError, "only valid"):
            mod.validate_spec(spec)

    def test_default_entry_seconds_overlap_stack_five_sources(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(5),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
            "duration": 5.0,
        }
        normalized = mod.validate_spec(spec)
        self.assertEqual(normalized["entry_seconds"], 4.0)

    def test_explicit_entry_seconds_wins(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(5),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
            "duration": 5.0,
            "entry_seconds": 2.5,
        }
        normalized = mod.validate_spec(spec)
        self.assertEqual(normalized["entry_seconds"], 2.5)

    def test_legacy_auto_layout_keeps_two_second_entry(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(5),
            "output": "exports/out.mp4",
            "layout": "auto",
            "duration": 5.0,
        }
        normalized = mod.validate_spec(spec)
        self.assertEqual(normalized["entry_seconds"], 2.0)

    def test_choose_overlap_stack_moves_title_safe_to_top(self):
        name, order = mod.choose_layout(5, self.sources(5, (3,)), "Title", "overlap_stack")
        self.assertEqual(name, "overlap_stack")
        self.assertEqual(order[-1], 3)

    def test_overlap_stack_three_sources_is_supported(self):
        name, _ = mod.choose_layout(3, self.sources(3), "", "overlap_stack")
        self.assertEqual(name, "overlap_stack")

    def test_overlap_stack_three_sources_uses_2_plus_1_base_and_geometry(self):
        spec = {
            "schema_version": 1, "sources": self.sources(3, (2,)), "output": "exports/out.mp4",
            "layout": "overlap_stack", "duration": 5.0, "rotation_enabled": True, "seed": 19,
        }
        normalized = mod.validate_spec(spec)
        self.assertEqual(normalized["base_layout"], "2+1")
        self.assertEqual(normalized["entry_seconds"], 4.0)
        name, order = mod.choose_layout(3, self.sources(3, (2,)), "Title", "overlap_stack")
        self.assertEqual((name, order[-1]), ("overlap_stack", 2))
        rows = mod._rows_for_layout("2+1", 1080, 1920)
        base = [cell for row in rows for cell in row]
        directions = mod.overlap_entrance_directions(rows)
        expanded = mod.overlap_stack_cells(base, rows, directions, 1080, 1920, 0.40)
        meta = mod.validate_overlap_stack_geometry(expanded, base, 1080, 1920, 0.40, base_rows=rows)
        self.assertEqual(len(expanded), 3)
        self.assertGreater(meta["cross_row_overlap_ratio"][0], 0.0)

    def test_overlap_stack_rejects_two_sources(self):
        with self.assertRaisesRegex(ValueError, "3-6"):
            mod.choose_layout(2, self.sources(2), "", "overlap_stack")

    def test_rotation_defaults_disabled(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(5),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
        }
        normalized = mod.validate_spec(spec)
        self.assertFalse(normalized["rotation_enabled"])

    def test_rotation_requires_overlap_stack(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(4),
            "output": "exports/out.mp4",
            "layout": "2x2",
            "rotation_enabled": True,
            "seed": 42,
        }
        with self.assertRaisesRegex(ValueError, "only valid with layout overlap_stack"):
            mod.validate_spec(spec)

    def test_rotation_requires_seed_when_enabled(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(5),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
            "rotation_enabled": True,
        }
        with self.assertRaisesRegex(ValueError, "seed is required"):
            mod.validate_spec(spec)

    def test_rotation_fields_require_enabled(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(5),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
            "seed": 7,
        }
        with self.assertRaisesRegex(ValueError, "seed requires rotation_enabled"):
            mod.validate_spec(spec)

    def test_rotation_degree_bounds(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(5),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
            "rotation_enabled": True,
            "seed": 1,
            "rotation_min_deg": 30,
            "rotation_max_deg": 70,
        }
        with self.assertRaisesRegex(ValueError, "rotation degrees"):
            mod.validate_spec(spec)

    def test_assign_panel_rotations_range_and_sign(self):
        panels = mod.assign_panel_rotations(5, 12345, 25.0, 45.0)
        self.assertEqual(len(panels), 5)
        for panel in panels:
            angle = panel["start_angle_deg"]
            self.assertGreaterEqual(abs(angle), 25.0)
            self.assertLessEqual(abs(angle), 45.0)
            if angle > 0:
                self.assertEqual(panel["rotation_direction"], "counterclockwise")
            else:
                self.assertEqual(panel["rotation_direction"], "clockwise")
            self.assertEqual(panel["seed"], 12345)

    def test_assign_panel_rotations_repeatable(self):
        first = mod.assign_panel_rotations(5, 99, 25.0, 45.0)
        second = mod.assign_panel_rotations(5, 99, 25.0, 45.0)
        self.assertEqual(first, second)

    def test_assign_panel_rotations_different_seed(self):
        first = mod.assign_panel_rotations(5, 1, 25.0, 45.0)
        second = mod.assign_panel_rotations(5, 2, 25.0, 45.0)
        self.assertNotEqual(
            [p["start_angle_deg"] for p in first],
            [p["start_angle_deg"] for p in second],
        )

    def test_assign_panel_rotations_zero_final_preserves_legacy_start_angles(self):
        legacy = mod.assign_panel_rotations(5, 99, 25.0, 45.0)
        explicit = mod.assign_panel_rotations(5, 99, 25.0, 45.0, 0.0)
        self.assertEqual(
            [p["start_angle_deg"] for p in legacy],
            [p["start_angle_deg"] for p in explicit],
        )
        for panel in explicit:
            self.assertEqual(panel["final_angle_deg"], 0.0)

    def test_final_rotation_requires_rotation_enabled(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(5),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
            "final_rotation_max_deg": 5,
        }
        with self.assertRaisesRegex(ValueError, "final_rotation_max_deg requires rotation_enabled"):
            mod.validate_spec(spec)

    def test_final_rotation_max_deg_bounds(self):
        spec = {
            "schema_version": 1,
            "sources": self.sources(5),
            "output": "exports/out.mp4",
            "layout": "overlap_stack",
            "rotation_enabled": True,
            "seed": 1,
            "final_rotation_max_deg": 11,
        }
        with self.assertRaisesRegex(ValueError, "final_rotation_max_deg"):
            mod.validate_spec(spec)

    def test_assign_panel_rotations_final_angle_range(self):
        panels = mod.assign_panel_rotations(5, 4242, 25.0, 45.0, 8.0)
        self.assertEqual(len(panels), 5)
        for panel in panels:
            final = panel["final_angle_deg"]
            self.assertGreaterEqual(final, -8.0)
            self.assertLessEqual(final, 8.0)

    def test_assign_panel_rotations_alternates_nonzero_final_signs(self):
        panels = mod.assign_panel_rotations(5, 4242, 25.0, 45.0, 8.0)
        finals = [panel["final_angle_deg"] for panel in panels]
        self.assertTrue(all(abs(angle) >= 0.05 for angle in finals))
        self.assertTrue(all(left * right < 0 for left, right in zip(finals, finals[1:])))

    def test_rotation_safe_cells_keep_final_rotated_bbox_inside_canvas(self):
        cells = [(0, 320, 694, 917), (170, 900, 694, 917)]
        rotations = [
            {"final_angle_deg": -13.2857},
            {"final_angle_deg": 14.9738},
        ]
        safe = mod.rotation_safe_cells(cells, rotations, 1080, 1920, padding_px=6)
        self.assertGreater(safe[0][0], 0)
        for (x, y, w, h), rotation in zip(safe, rotations):
            bbox_w, bbox_h = mod.rotation_canvas_size(w, h, abs(rotation["final_angle_deg"]))
            self.assertGreaterEqual(x - math.ceil((bbox_w - w) / 2), 0)
            self.assertGreaterEqual(y - math.ceil((bbox_h - h) / 2), 0)
            self.assertLessEqual(x + w + math.ceil((bbox_w - w) / 2), 1080)
            self.assertLessEqual(y + h + math.ceil((bbox_h - h) / 2), 1920)

    def test_assign_panel_rotations_final_repeatable(self):
        first = mod.assign_panel_rotations(5, 77, 25.0, 45.0, 6.0)
        second = mod.assign_panel_rotations(5, 77, 25.0, 45.0, 6.0)
        self.assertEqual(first, second)

    def test_assign_panel_rotations_final_different_seed(self):
        first = mod.assign_panel_rotations(5, 10, 25.0, 45.0, 6.0)
        second = mod.assign_panel_rotations(5, 11, 25.0, 45.0, 6.0)
        self.assertNotEqual(
            [p["final_angle_deg"] for p in first],
            [p["final_angle_deg"] for p in second],
        )

    def test_rotation_angle_expr_animates_to_final(self):
        expr = mod.rotation_angle_expr(30.0, -5.0, (0.0, 1.0, "left"))
        self.assertIn("+(-0.08726646-0.52359878)*", expr)
        self.assertIn("-0.08726646", expr)

    def test_rotation_canvas_uses_max_start_and_final(self):
        w, h = 540, 650
        start_only = mod.rotation_canvas_size(w, h, 40.0)
        final_only = mod.rotation_canvas_size(w, h, 8.0)
        both = mod.rotation_canvas_size(w, h, max(40.0, 8.0))
        self.assertEqual(both, start_only)
        self.assertGreaterEqual(both[0], final_only[0])
        self.assertGreaterEqual(both[1], final_only[1])

    def test_rotation_canvas_fits_rotated_corners(self):
        for w, h in ((540, 650), (1080, 720), (675, 938)):
            for angle in (25.0, 35.0, 45.0):
                ow, oh = mod.rotation_canvas_size(w, h, angle)
                self.assertGreaterEqual(ow, w)
                self.assertGreaterEqual(oh, h)
                rad = math.radians(angle)
                cos_a = abs(math.cos(rad))
                sin_a = abs(math.sin(rad))
                expected_w = math.ceil(w * cos_a + h * sin_a)
                expected_h = math.ceil(w * sin_a + h * cos_a)
                self.assertEqual(ow, max(expected_w, w))
                self.assertEqual(oh, max(expected_h, h))
                half_w = w / 2.0
                half_h = h / 2.0
                corners = [
                    (-half_w, -half_h),
                    (half_w, -half_h),
                    (half_w, half_h),
                    (-half_w, half_h),
                ]
                rotated = []
                for cx, cy in corners:
                    rx = cx * math.cos(rad) - cy * math.sin(rad)
                    ry = cx * math.sin(rad) + cy * math.cos(rad)
                    rotated.append((rx, ry))
                xs = [p[0] for p in rotated]
                ys = [p[1] for p in rotated]
                bbox_w = max(xs) - min(xs)
                bbox_h = max(ys) - min(ys)
                self.assertLessEqual(math.ceil(bbox_w), ow)
                self.assertLessEqual(math.ceil(bbox_h), oh)


class EntranceGatingTests(unittest.TestCase):
    def test_renderer_background_uses_first_entered_source(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("bg_index = 0", source)
        self.assertNotIn("if src.get(\"title_safe\")", source[source.find("bg_index"):source.find("cards: list")])

    def _four_panel_rotation_setup(self) -> tuple[list, list, list[dict[str, Any]]]:
        base_rows = mod._rows_for_layout("2x2", 360, 640)
        base_cells = [cell for row in base_rows for cell in row]
        schedule = mod.entry_schedule(base_rows, "fly_in", 4.0)
        rotations = mod.assign_panel_rotations(4, 777, 35.0, 45.0)
        directions = mod.overlap_entrance_directions(base_rows)
        cells = mod.overlap_stack_cells(base_cells, base_rows, directions, 360, 640, 0.40)
        return cells, schedule, rotations

    def test_overlay_enable_option_immediate_for_start_zero(self):
        self.assertEqual(mod.overlay_enable_option((0.0, 0.7, "left")), "")

    def test_overlay_enable_option_gates_delayed_start(self):
        self.assertEqual(mod.overlay_enable_option((1.100, 1.800, "right")), ":enable='gte(t,1.100)'")

    def test_rotated_overlay_graph_first_panel_has_no_enable_gate(self):
        cells, schedule, rotations = self._four_panel_rotation_setup()
        graph, _ = mod.build_panel_overlay_graph(cells, schedule, rotations, 360, 640)
        self.assertEqual(schedule[0][0], 0.0)
        first_overlay = next(line for line in graph if line.startswith("[0:v][r1]overlay="))
        self.assertNotIn("enable=", first_overlay)

    def test_rotated_overlay_graph_later_panels_gate_before_entrance(self):
        cells, schedule, rotations = self._four_panel_rotation_setup()
        graph, _ = mod.build_panel_overlay_graph(cells, schedule, rotations, 360, 640)
        overlays = [line for line in graph if "overlay=" in line]
        self.assertEqual(len(overlays), 4)
        for panel_index, timing in enumerate(schedule, 1):
            overlay = overlays[panel_index - 1]
            start = timing[0]
            if start <= 0.0:
                self.assertNotIn("enable=", overlay, msg=f"panel {panel_index}")
            else:
                self.assertIn(f"enable='gte(t,{start:.3f})'", overlay, msg=f"panel {panel_index}")

    def test_non_rotated_overlay_graph_also_gates_delayed_panels(self):
        cells, schedule, _ = self._four_panel_rotation_setup()
        graph, _ = mod.build_panel_overlay_graph(cells, schedule, None, 360, 640)
        overlays = [line for line in graph if "overlay=" in line]
        delayed = [line for line, timing in zip(overlays, schedule) if timing[0] > 0.0]
        self.assertTrue(delayed)
        for line in delayed:
            self.assertIn("enable='gte(t,", line)


@unittest.skipUnless(subprocess.run(["sh", "-c", "command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null"]).returncode == 0, "ffmpeg required")
class IntegrationTests(unittest.TestCase):
    @staticmethod
    def _sample_frame_rgb(video: Path, seconds: float, x: int, y: int) -> tuple[int, int, int]:
        # yuv420p requires even crop origin/size; sample the top-left pixel of a 2x2 block.
        x_even = max(0, int(x) // 2 * 2)
        y_even = max(0, int(y) // 2 * 2)
        raw = subprocess.check_output([
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", str(video),
            "-ss", f"{seconds:.3f}",
            "-frames:v", "1",
            "-vf", f"crop=2:2:{x_even}:{y_even}",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:",
        ])
        return raw[0], raw[1], raw[2]

    @staticmethod
    def _is_magenta(rgb: tuple[int, int, int], *, min_channel: int = 180) -> bool:
        r, g, b = rgb
        return r >= min_channel and b >= min_channel and g <= 80
    def test_real_three_image_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "photos").mkdir()
            colors = ["red", "green", "blue"]
            for i, color in enumerate(colors):
                subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"color=c={color}:s=800x600:d=0.1",
                    "-frames:v", "1", "-update", "1", str(root / "photos" / f"{i}.png")
                ], check=True)
            spec = {
                "schema_version": 1,
                "sources": [
                    {"path": "photos/0.png", "focus_x": 0.5, "focus_y": 0.5},
                    {"path": "photos/1.png", "focus_x": 0.5, "focus_y": 0.5},
                    {"path": "photos/2.png", "focus_x": 0.5, "focus_y": 0.5, "title_safe": True, "hero": True},
                ],
                "output": "exports/test.mp4",
                "width": 360,
                "height": 640,
                "fps": 10,
                "duration": 2.0,
                "entry_seconds": 0.8,
                "gutter": 2,
                "title": {"text": "Test title", "max_chars": 12, "font_size": 20},
            }
            report = mod.render(root, spec)
            self.assertEqual(report["status"], "ok")
            self.assertEqual((report["width"], report["height"]), (360, 640))
            self.assertEqual(report["layout_selected"], "2+1")
            self.assertEqual(report["animation_selected"], "hero_last")
            self.assertTrue(report["decodable"])
            self.assertTrue(report["motion_detected"])
            self.assertEqual(report["renderer_version"], "1.5.0")
            self.assertEqual(report["pixel_format"], "yuv420p")
            self.assertEqual(len(report["source_hashes"]), 3)
            self.assertEqual(len(report["panels"]), 3)
            self.assertGreater(report["frame_count"], 0)
            self.assertEqual(report["visual_review"], "pending")
            self.assertTrue((root / report["output"]).is_file())
            self.assertTrue((root / report["last_frame"]).is_file())
            self.assertEqual(len(report["qa_frames"]), 3)
            saved = json.loads((root / "exports/test-report.json").read_text())
            self.assertEqual(saved["sha256"], report["sha256"])

    def test_real_overlap_stack_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "photos").mkdir()
            colors = ["red", "green", "blue", "orange", "purple"]
            for i, color in enumerate(colors):
                subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"color=c={color}:s=900x700:d=0.1",
                    "-frames:v", "1", "-update", "1", str(root / "photos" / f"{i}.png")
                ], check=True)
            spec = {
                "schema_version": 1,
                "sources": [
                    {"path": f"photos/{i}.png", "focus_x": 0.5, "focus_y": 0.5, "title_safe": i == 4}
                    for i in range(5)
                ],
                "output": "exports/overlap.mp4",
                "width": 360,
                "height": 640,
                "fps": 10,
                "duration": 5.0,
                "gutter": 2,
                "layout": "overlap_stack",
                "overlap_ratio": 0.40,
                "title": {"text": "Overlap", "max_chars": 12, "font_size": 20},
                "overwrite": True,
            }
            report = mod.render(root, spec)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["layout_selected"], "overlap_stack")
            self.assertEqual(report["base_layout"], "2+2+1")
            self.assertEqual(report["animation_selected"], "fly_in")
            self.assertEqual(report["entry_seconds"], 4.0)
            self.assertAlmostEqual(report["hold_seconds"], 1.0, places=1)
            self.assertTrue(report["entry_seconds_defaulted"])
            self.assertIn("overlap", report)
            self.assertEqual(report["overlap"]["overlap_ratio"], 0.40)
            self.assertTrue(all(v > 0 for v in report["overlap"]["cross_row_overlap_ratio"]))
            self.assertGreaterEqual(len(report["overlap"]["orientation_signature"]), 2)
            self.assertEqual(len(report["panels"]), 5)
            for panel in report["panels"]:
                self.assertIn("base_rect", panel)
                ex, ey, ew, eh = panel["rect"]
                bx, by, bw, bh = panel["base_rect"]
                self.assertLessEqual(ex, bx)
                self.assertLessEqual(ey, by)
                self.assertGreaterEqual(ex + ew, bx + bw)
                self.assertGreaterEqual(ey + eh, by + bh)
                if bw * bh < report["width"] * report["height"]:
                    self.assertLess(ew * eh, report["width"] * report["height"])
            widths = {panel["rect"][2] for panel in report["panels"]}
            heights = {panel["rect"][3] for panel in report["panels"]}
            self.assertGreater(len(widths), 1)
            self.assertGreater(len(heights), 1)
            self.assertEqual(report["source_order"][-1], "photos/4.png")

    def test_real_overlap_stack_rotation_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "photos").mkdir()
            colors = ["red", "green", "blue", "orange", "purple"]
            for i, color in enumerate(colors):
                subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"color=c={color}:s=900x700:d=0.1",
                    "-frames:v", "1", "-update", "1", str(root / "photos" / f"{i}.png")
                ], check=True)
            spec = {
                "schema_version": 1,
                "sources": [
                    {"path": f"photos/{i}.png", "focus_x": 0.5, "focus_y": 0.5, "title_safe": i == 4}
                    for i in range(5)
                ],
                "output": "exports/overlap-rot.mp4",
                "width": 360,
                "height": 640,
                "fps": 10,
                "duration": 5.0,
                "gutter": 2,
                "layout": "overlap_stack",
                "overlap_ratio": 0.40,
                "rotation_enabled": True,
                "seed": 4242,
                "rotation_min_deg": 25,
                "rotation_max_deg": 45,
                "title": {"text": "Rotate", "max_chars": 12, "font_size": 20},
                "overwrite": True,
            }
            report_a = mod.render(root, spec)
            report_b = mod.render(root, {**spec, "overwrite": True})
            self.assertEqual(report_a["status"], "ok")
            self.assertEqual(report_a["layout_selected"], "overlap_stack")
            self.assertEqual(report_a["entry_seconds"], 4.0)
            self.assertAlmostEqual(report_a["hold_seconds"], 1.0, places=1)
            self.assertIn("overlap", report_a)
            self.assertIn("rotation", report_a["overlap"])
            self.assertTrue(report_a["overlap"]["rotation"]["enabled"])
            self.assertEqual(report_a["overlap"]["rotation"]["seed"], 4242)
            self.assertEqual(len(report_a["panels"]), 5)
            angles_a = []
            for panel in report_a["panels"]:
                self.assertIn("rotation", panel)
                rot = panel["rotation"]
                self.assertEqual(rot["seed"], 4242)
                self.assertEqual(rot["final_angle_deg"], 0.0)
                angle = rot["start_angle_deg"]
                self.assertGreaterEqual(abs(angle), 25.0)
                self.assertLessEqual(abs(angle), 45.0)
                if angle > 0:
                    self.assertEqual(rot["rotation_direction"], "counterclockwise")
                else:
                    self.assertEqual(rot["rotation_direction"], "clockwise")
                cw, ch = panel["rotation"]["canvas"]
                pw, ph = panel["rect"][2], panel["rect"][3]
                expected_w, expected_h = mod.rotation_canvas_size(pw, ph, abs(angle))
                self.assertEqual([cw, ch], [expected_w, expected_h])
                angles_a.append(angle)
            angles_b = [p["rotation"]["start_angle_deg"] for p in report_b["panels"]]
            self.assertEqual(angles_a, angles_b)
            self.assertTrue(report_a["motion_detected"])
            self.assertTrue(report_a["title_rendered"])
            self.assertTrue((root / report_a["output"]).is_file())

    def test_real_overlap_stack_final_rotation_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "photos").mkdir()
            colors = ["red", "green", "blue", "orange", "purple"]
            for i, color in enumerate(colors):
                subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"color=c={color}:s=900x700:d=0.1",
                    "-frames:v", "1", "-update", "1", str(root / "photos" / f"{i}.png")
                ], check=True)
            spec = {
                "schema_version": 1,
                "sources": [
                    {"path": f"photos/{i}.png", "focus_x": 0.5, "focus_y": 0.5, "title_safe": i == 4}
                    for i in range(5)
                ],
                "output": "exports/overlap-final-rot.mp4",
                "width": 360,
                "height": 640,
                "fps": 10,
                "duration": 5.0,
                "gutter": 2,
                "layout": "overlap_stack",
                "overlap_ratio": 0.40,
                "rotation_enabled": True,
                "seed": 9001,
                "rotation_min_deg": 25,
                "rotation_max_deg": 45,
                "final_rotation_max_deg": 8,
                "title": {"text": "Final", "max_chars": 12, "font_size": 20},
                "overwrite": True,
            }
            report_a = mod.render(root, spec)
            report_b = mod.render(root, {**spec, "overwrite": True})
            self.assertEqual(report_a["status"], "ok")
            rotation_meta = report_a["overlap"]["rotation"]
            self.assertEqual(rotation_meta["final_rotation_max_deg"], 8.0)
            finals_a = []
            for panel in report_a["panels"]:
                rot = panel["rotation"]
                final = rot["final_angle_deg"]
                self.assertGreaterEqual(final, -8.0)
                self.assertLessEqual(final, 8.0)
                start_abs = abs(rot["start_angle_deg"])
                final_abs = abs(final)
                pw, ph = panel["rect"][2], panel["rect"][3]
                expected_w, expected_h = mod.rotation_canvas_size(pw, ph, max(start_abs, final_abs))
                self.assertEqual(panel["rotation"]["canvas"], [expected_w, expected_h])
                finals_a.append(final)
            finals_b = [p["rotation"]["final_angle_deg"] for p in report_b["panels"]]
            self.assertEqual(finals_a, finals_b)
            self.assertTrue(any(abs(v) > 0.0 for v in finals_a))
            self.assertTrue((root / report_a["output"]).is_file())

    def test_rotated_overlap_stack_hides_late_card_until_entrance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "photos").mkdir()
            colors = ["red", "green", "blue", "0xFF00FF"]
            for i, color in enumerate(colors):
                subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"color=c={color}:s=900x700:d=0.1",
                    "-frames:v", "1", "-update", "1", str(root / "photos" / f"{i}.png")
                ], check=True)
            spec = {
                "schema_version": 1,
                "sources": [
                    {"path": f"photos/{i}.png", "focus_x": 0.5, "focus_y": 0.5, "title_safe": i == 3}
                    for i in range(4)
                ],
                "output": "exports/overlap-rot-gate.mp4",
                "width": 360,
                "height": 640,
                "fps": 10,
                "duration": 5.0,
                "entry_seconds": 4.0,
                "gutter": 2,
                "layout": "overlap_stack",
                "overlap_ratio": 0.40,
                "rotation_enabled": True,
                "seed": 13579,
                "rotation_min_deg": 35,
                "rotation_max_deg": 45,
                "title": {"text": "", "max_chars": 12, "font_size": 20},
                "overwrite": True,
            }
            report = mod.render(root, spec)
            self.assertEqual(report["status"], "ok")
            last_panel = report["panels"][-1]
            last_start = float(last_panel["entrance"]["start"])
            self.assertGreater(last_start, 0.0)
            lx, ly, lw, lh = last_panel["rect"]
            sample_x = lx + lw // 2
            sample_y = ly + lh // 2
            video = root / report["output"]
            before = self._sample_frame_rgb(video, max(0.05, last_start - 0.25), sample_x, sample_y)
            after = self._sample_frame_rgb(video, min(4.8, last_start + 0.25), sample_x, sample_y)
            self.assertFalse(self._is_magenta(before), msg=f"late card leaked before entrance: rgb={before}")
            self.assertTrue(self._is_magenta(after), msg=f"late card missing after entrance: rgb={after}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
