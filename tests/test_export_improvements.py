import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageCms
try:
    import pymupdf as fitz
except ImportError:
    import fitz  # type: ignore

from src.artboard_cutter_core.export import ExportOptions, process_file
from src.artboard_cutter_core.preflight import estimate_export_job
from src.artboard_cutter_core.raster_export import should_use_bigtiff
from src.artboard_cutter_core.verification import verify_raster_output


class ExportImprovementTests(unittest.TestCase):
    def test_streaming_tiff_embeds_selected_rgb_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "gradient.jpg"
            image = Image.new("RGB", (120, 80))
            for x in range(image.width):
                for y in range(image.height):
                    image.putpixel((x, y), (x * 2, y * 3, (x + y) % 256))
            image.save(source, quality=95)
            profile_bytes = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            profile_path = root / "sRGB.icc"
            profile_path.write_bytes(profile_bytes)

            result = process_file(
                source,
                ExportOptions(
                    bleed_mm=0,
                    widths_mm=[120],
                    height_mm=80,
                    overlap_mm=0,
                    dpi=100,
                    output_root=root / "out",
                    export_fmt="tiff",
                    icc_mode="Convert",
                    icc_profile_path=str(profile_path),
                ),
            )

            with Image.open(result.output_paths[0]) as output:
                self.assertEqual(output.mode, "RGB")
                self.assertTrue(output.info.get("icc_profile"))

    def test_raster_pdf_embeds_output_intent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.jpg"
            Image.new("RGB", (40, 30), (20, 80, 160)).save(source)
            profile_path = root / "sRGB.icc"
            profile_path.write_bytes(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
            result = process_file(
                source,
                ExportOptions(
                    0, [40], 30, 0, 72, root / "out",
                    export_fmt="pdf",
                    icc_mode="Embed only",
                    icc_profile_path=str(profile_path),
                ),
            )
            doc = fitz.open(result.output_paths[0])
            try:
                kind, value = doc.xref_get_key(doc.pdf_catalog(), "OutputIntents")
                self.assertEqual(kind, "array")
                self.assertIn(" R", value)
            finally:
                doc.close()

    def test_verifier_rejects_uniform_output_for_varying_source(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "blank.tif"
            Image.new("RGB", (20, 10), "white").save(path, dpi=(100, 100))
            with self.assertRaisesRegex(RuntimeError, "blank/uniform"):
                verify_raster_output(
                    path,
                    expected_size=(20, 10),
                    expected_dpi=100,
                    expected_mode="RGB",
                    source_varies=True,
                )

    def test_tiff_preflight_retains_requested_dpi_and_flags_large_jobs(self):
        estimate = estimate_export_job(
            widths_mm=[5000, 5000],
            height_mm=4000,
            bleed_mm=0,
            overlap_mm=0,
            overlap_mode="shared",
            dpi=300,
            color_mode="CMYK",
            export_format="TIFF",
            preserve_vectors=False,
        )
        self.assertEqual(estimate.effective_dpi, 300)
        self.assertTrue(estimate.uses_streaming_tiff)
        self.assertTrue(estimate.warnings)

    def test_bigtiff_decision_uses_uncompressed_sample_size(self):
        self.assertFalse(should_use_bigtiff(1000, 1000, 4))
        self.assertTrue(should_use_bigtiff(50_000, 20_000, 4))


if __name__ == "__main__":
    unittest.main()
