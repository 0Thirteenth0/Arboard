import tempfile
import unittest
from pathlib import Path

import fitz

from src.artboard_cutter_core.export import ExportOptions, process_file
from src.artboard_cutter_core.units import pt_to_mm
from tests.helpers import make_grid_pdf, make_multipage_pdf, make_rotated_pdf, make_unusual_page_box_pdf, render_pdf_page_rgb


class ExportGeometryTests(unittest.TestCase):
    def assert_pdf_size_mm(self, pdf_path: Path, expected_w: float, expected_h: float, places=2):
        doc = fitz.open(pdf_path)
        try:
            rect = doc.load_page(0).rect
            self.assertAlmostEqual(pt_to_mm(rect.width), expected_w, places=places)
            self.assertAlmostEqual(pt_to_mm(rect.height), expected_h, places=places)
        finally:
            doc.close()

    def test_raster_pdf_panel_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src)
            options = ExportOptions(
                bleed_mm=10,
                widths_mm=[100, 100],
                height_mm=100,
                overlap_mm=20,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "grid_1.pdf", 120, 120)
            self.assert_pdf_size_mm(options.output_root / "grid_2.pdf", 120, 120)

    def test_vector_pdf_panel_dimensions_match_layout(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src)
            options = ExportOptions(
                bleed_mm=10,
                widths_mm=[100, 100],
                height_mm=100,
                overlap_mm=20,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
                vector_fit_mode="stretch",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "grid_1.pdf", 120, 120)
            self.assert_pdf_size_mm(options.output_root / "grid_2.pdf", 120, 120)

    def test_left_overlap_panel_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=320, height_mm=120)
            options = ExportOptions(
                bleed_mm=10,
                widths_mm=[100, 100, 100],
                height_mm=100,
                overlap_mm=20,
                overlap_mode="left",
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
                vector_fit_mode="stretch",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "grid_1.pdf", 110, 120)
            self.assert_pdf_size_mm(options.output_root / "grid_2.pdf", 120, 120)
            self.assert_pdf_size_mm(options.output_root / "grid_3.pdf", 130, 120)

    def test_vector_stretch_supports_non_uniform_target_size(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=220, height_mm=120)
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[80, 70],
                height_mm=100,
                overlap_mm=0,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
                vector_fit_mode="stretch",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "grid_1.pdf", 80, 100)
            self.assert_pdf_size_mm(options.output_root / "grid_2.pdf", 70, 100)

    def test_rotated_pdf_fixture_exports_expected_panel_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "rotated.pdf"
            make_rotated_pdf(src)
            options = ExportOptions(
                bleed_mm=5,
                widths_mm=[40, 40],
                height_mm=60,
                overlap_mm=10,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
                vector_fit_mode="stretch",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "rotated_1.pdf", 50, 70)
            self.assert_pdf_size_mm(options.output_root / "rotated_2.pdf", 50, 70)

    def test_unusual_page_boxes_export_expected_panel_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "page_boxes.pdf"
            make_unusual_page_box_pdf(src)
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[100, 100],
                height_mm=120,
                overlap_mm=0,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
                vector_fit_mode="stretch",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "page_boxes_1.pdf", 100, 120)
            self.assert_pdf_size_mm(options.output_root / "page_boxes_2.pdf", 100, 120)

    def test_custom_output_name_controls_export_filename(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "source.pdf"
            make_grid_pdf(src, width_mm=100, height_mm=80)
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[100],
                height_mm=80,
                overlap_mm=0,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                output_name="EditedQueueName",
            )
            process_file(src, options)
            self.assertTrue((options.output_root / "EditedQueueName_1.pdf").exists())
            self.assertFalse((options.output_root / "source_1.pdf").exists())

    def test_page_index_exports_requested_page_not_only_first_page(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "multipage.pdf"
            make_multipage_pdf(
                src,
                page_specs=[
                    (100, 80, (0.90, 0.05, 0.05)),
                    (100, 80, (0.05, 0.10, 0.90)),
                ],
            )
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[100],
                height_mm=80,
                overlap_mm=0,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                page_index=1,
                output_name="SecondPage",
            )
            process_file(src, options)
            _, _, samples = render_pdf_page_rgb(options.output_root / "SecondPage_1.pdf", dpi=36)
            red = sum(samples[0::3]) / (len(samples) // 3)
            blue = sum(samples[2::3]) / (len(samples) // 3)
            self.assertGreater(blue, red, "Export appears to use page 1 instead of the requested second page.")


if __name__ == "__main__":
    unittest.main()
