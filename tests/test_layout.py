import unittest

from src.artboard_cutter_core.layout import compute_panel_layout, parse_widths_list


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


if __name__ == "__main__":
    unittest.main()
