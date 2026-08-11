import tempfile
import unittest
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # type: ignore

from artboard_cutter_gui_advanced import process_file
from artboard_cutter_gui_advanced import App
from src.artboard_cutter_core.profiles import ArtworkProfile
from src.artboard_cutter_core.units import pt_to_mm
from tests.helpers import make_grid_pdf


class GuiWrapperCompatibilityTests(unittest.TestCase):
    def test_all_queue_layers_are_registered_as_file_drop_targets(self):
        class FakeDropWidget:
            def __init__(self):
                self.types = []
                self.bindings = []

            def drop_target_register(self, drop_type):
                self.types.append(drop_type)

            def dnd_bind(self, event_name, callback):
                self.bindings.append((event_name, callback))

        widgets = [FakeDropWidget(), FakeDropWidget(), FakeDropWidget()]
        fake_app = type("FakeApp", (), {"on_drop": lambda self, event: None})()

        App._register_file_drop_targets(fake_app, *widgets)

        for widget in widgets:
            self.assertEqual(len(widget.types), 1)
            self.assertEqual(widget.bindings[0][0], "<<Drop>>")

    def test_process_file_wrapper_delegates_to_core_export(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "source.pdf"
            out = root / "out"
            make_grid_pdf(src, width_mm=120, height_mm=80)

            process_file(
                src,
                bleed_mm=5,
                widths_mm=[60, 60],
                height_mm=80,
                overlap_mm=10,
                dpi=72,
                output_root=out,
                output_name="Wrapped",
            )

            first = out / "Wrapped_1.pdf"
            second = out / "Wrapped_2.pdf"
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            doc = fitz.open(first)
            try:
                rect = doc.load_page(0).rect
                self.assertAlmostEqual(pt_to_mm(rect.width), 70, places=2)
                self.assertAlmostEqual(pt_to_mm(rect.height), 90, places=2)
            finally:
                doc.close()

    def test_pdf_preserve_validation_allows_blank_dpi(self):
        profile = ArtworkProfile(
            file_path="source.pdf",
            output_name="PdfPreserveBlankDpi",
            panel_widths="100 100",
            height_mm="100",
            bleed_mm="10",
            overlap_mm="20",
            dpi="",
            export_format="PDF",
            export_mode="PDF Preserve",
            color_mode="CMYK",
        )

        values = App._validate_profile_for_export(None, profile)

        self.assertEqual(values[5], 72)
        self.assertEqual(values[6], "pdf")
        self.assertTrue(values[7])
        self.assertEqual(values[8], "CMYK")

    def test_raster_validation_requires_dpi(self):
        profile = ArtworkProfile(
            file_path="source.pdf",
            output_name="RasterBlankDpi",
            panel_widths="100",
            height_mm="100",
            bleed_mm="10",
            overlap_mm="0",
            dpi="",
            export_format="PDF",
            export_mode="Raster",
        )

        with self.assertRaisesRegex(ValueError, "DPI is required"):
            App._validate_profile_for_export(None, profile)


if __name__ == "__main__":
    unittest.main()
