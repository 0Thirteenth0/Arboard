import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.artboard_cutter_core.raster_images import save_raster_pil


class RasterImageWriterTests(unittest.TestCase):
    def test_compatibility_tiff_writer_produces_readable_pixels_and_dpi(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "compat.tif"
            source = Image.new("RGB", (24, 12), (20, 80, 160))

            save_raster_pil(source, output, "tiff", 144)

            with Image.open(output) as image:
                self.assertEqual(image.format, "TIFF")
                self.assertEqual(image.size, (24, 12))
                self.assertAlmostEqual(image.info["dpi"][0], 144, delta=1)

    def test_jpeg_writer_converts_unsupported_mode(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "compat.jpg"
            source = Image.new("RGBA", (16, 8), (20, 80, 160, 200))

            save_raster_pil(source, output, "jpeg", 96)

            with Image.open(output) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.mode, "RGB")
                self.assertAlmostEqual(image.info["dpi"][0], 96, delta=1)


if __name__ == "__main__":
    unittest.main()
