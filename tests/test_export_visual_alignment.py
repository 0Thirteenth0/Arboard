import tempfile
import unittest
from pathlib import Path

from src.artboard_cutter_core.export import ExportOptions, process_file
from tests.helpers import (
    make_color_stripe_pdf,
    pixel_diff_stats,
    render_pdf_page_rgb,
    save_ppm_diff_artifact,
)


class ExportVisualAlignmentTests(unittest.TestCase):
    def test_raster_and_vector_rendered_pixels_align(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "stripes.pdf"
            make_color_stripe_pdf(src, width_mm=200, height_mm=100)

            base_options = dict(
                bleed_mm=0,
                widths_mm=[80, 70, 50],
                height_mm=120,
                overlap_mm=0,
                dpi=96,
                export_fmt="pdf",
                vector_fit_mode="stretch",
            )
            raster_options = ExportOptions(
                **base_options,
                output_root=root / "raster",
                preserve_vectors=False,
            )
            vector_options = ExportOptions(
                **base_options,
                output_root=root / "vector",
                preserve_vectors=True,
            )

            process_file(src, raster_options)
            process_file(src, vector_options)

            for panel in (1, 2, 3):
                raster = render_pdf_page_rgb(raster_options.output_root / f"stripes_{panel}.pdf", dpi=96)
                vector = render_pdf_page_rgb(vector_options.output_root / f"stripes_{panel}.pdf", dpi=96)
                stats = pixel_diff_stats(raster, vector)
                try:
                    self.assertLessEqual(
                        stats["mean_abs"],
                        2.0,
                        f"panel {panel}: mean_abs={stats['mean_abs']:.3f}, stats={stats}",
                    )
                    self.assertLessEqual(
                        stats["different_ratio"],
                        0.02,
                        f"panel {panel}: different_ratio={stats['different_ratio']:.5f}, stats={stats}",
                    )
                except AssertionError:
                    artifact = save_ppm_diff_artifact(f"raster_vector_alignment_panel_{panel}", raster, vector)
                    if artifact:
                        self.fail(f"panel {panel} raster/vector alignment failed; diff artifact: {artifact}; stats={stats}")
                    raise


if __name__ == "__main__":
    unittest.main()
