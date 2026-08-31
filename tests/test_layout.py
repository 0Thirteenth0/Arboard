import unittest

from src.artboard_cutter_core.layout import (
    add_evenly_distributed_panel,
    compute_panel_layout,
    compute_preview_page_height,
    parse_widths_list,
    redistribute_panel_widths,
    resize_adjacent_panel_widths,
    split_last_panel_width,
)
from src.artboard_cutter_core.units import preview_render_scale


class PanelLayoutTests(unittest.TestCase):
    def test_outside_bleed_only_single_panel(self):
        panels, total, overlap = compute_panel_layout([1000], 20, 40)
        self.assertEqual(overlap, 40)
        self.assertEqual(total, 1040)
        self.assertEqual(panels[0].outer_left, 0)
        self.assertEqual(panels[0].outer_right, 1040)
        self.assertEqual(panels[0].content_left, 20)
        self.assertEqual(panels[0].content_right, 1020)

    def test_shared_overlap_between_panels(self):
        panels, total, overlap = compute_panel_layout([1000, 800], 20, 40)
        self.assertEqual(overlap, 40)
        self.assertEqual(total, 1840)
        self.assertEqual(panels[0].outer_left, 0)
        self.assertEqual(panels[0].outer_right, 1040)
        self.assertEqual(panels[1].outer_left, 1000)
        self.assertEqual(panels[1].outer_right, 1840)

    def test_custom_widths_three_panels(self):
        panels, total, overlap = compute_panel_layout([600, 1000, 400], 10, 20)
        self.assertEqual(total, 2020)
        self.assertEqual([p.outer_left for p in panels], [0, 600, 1600])
        self.assertEqual([p.outer_right for p in panels], [620, 1620, 2020])
        self.assertEqual(overlap, 20)

    def test_left_overlap_goes_on_right_hand_panel_only(self):
        panels, total, overlap = compute_panel_layout([100, 100, 100], 10, 20, overlap_mode="left")
        self.assertEqual(overlap, 20)
        self.assertEqual(total, 320)
        self.assertEqual([p.outer_left for p in panels], [0, 90, 190])
        self.assertEqual([p.outer_right for p in panels], [110, 210, 320])
        self.assertEqual(panels[0].outer_width, 110)
        self.assertEqual(panels[1].outer_width, 120)
        self.assertEqual(panels[2].outer_width, 130)

    def test_overlap_is_clamped_below_smallest_panel(self):
        panels, _total, overlap = compute_panel_layout([50, 100], 10, 80)
        self.assertAlmostEqual(overlap, 49.99)
        self.assertGreater(panels[0].outer_width, 0)
        self.assertGreater(panels[1].outer_width, 0)

    def test_parse_widths_accepts_commas_and_spaces(self):
        self.assertEqual(parse_widths_list("100, 200 300"), [100.0, 200.0, 300.0])

    def test_non_finite_panel_math_is_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finite"):
                    parse_widths_list(str(value))
                with self.assertRaisesRegex(ValueError, "finite"):
                    redistribute_panel_widths(value, 2)
                with self.assertRaisesRegex(ValueError, "finite"):
                    compute_panel_layout([100, value], 0, 0)

    def test_preview_height_rejects_non_finite_dimensions(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            compute_preview_page_height(100, float("nan"), 0, False, "stretch", None, None)

    def test_split_last_panel_preserves_total_width(self):
        widths = split_last_panel_width([1200, 1200, 1100])
        self.assertEqual(widths, [1200.0, 1200.0, 550.0, 550.0])
        self.assertEqual(sum(widths), 3500.0)

    def test_add_panel_redistributes_entire_artwork_evenly(self):
        widths = add_evenly_distributed_panel([1200, 800, 400])
        self.assertEqual(widths, [600.0, 600.0, 600.0, 600.0])
        self.assertEqual(sum(widths), 2400.0)

    def test_resize_adjacent_panel_widths_preserves_total_width(self):
        widths = resize_adjacent_panel_widths([1000, 800, 600], 0, 125)
        self.assertEqual(widths, [1125.0, 675.0, 600.0])
        self.assertEqual(sum(widths), 2400.0)

    def test_resize_adjacent_panel_widths_clamps_min_width(self):
        widths = resize_adjacent_panel_widths([1000, 800], 0, 900, min_width_mm=50)
        self.assertEqual(widths, [1750.0, 50.0])
        self.assertEqual(sum(widths), 1800.0)

    def test_resize_adjacent_panel_widths_can_reset_when_drag_exceeds_limit(self):
        widths = resize_adjacent_panel_widths([1000, 800], 0, 900, min_width_mm=50, clamp=False)
        self.assertEqual(widths, [1000.0, 800.0])

    def test_resize_adjacent_panel_widths_can_protect_overlap_value(self):
        start = [1000, 80]
        widths = resize_adjacent_panel_widths(start, 0, 50, min_width_mm=40.01, clamp=False)
        self.assertEqual(widths, [1000.0, 80.0])
        _panels, _total, overlap = compute_panel_layout(widths, 20, 40)
        self.assertEqual(overlap, 40)

    def test_resize_adjacent_panel_widths_rejects_bleed_edges(self):
        with self.assertRaises(IndexError):
            resize_adjacent_panel_widths([1000, 800], -1, 10)
        with self.assertRaises(IndexError):
            resize_adjacent_panel_widths([1000, 800], 1, 10)

    def test_resize_rejects_impossible_minimum_width(self):
        with self.assertRaisesRegex(ValueError, "too large"):
            resize_adjacent_panel_widths([10, 10], 0, 0, min_width_mm=11)

    def test_preview_render_scale_never_exceeds_pixel_budget(self):
        huge_dimension = 200_000.0
        scale = preview_render_scale(huge_dimension, max_pixels=1600)
        self.assertLessEqual(huge_dimension * scale, 1600.000001)
        self.assertGreater(scale, 0)


if __name__ == "__main__":
    unittest.main()
