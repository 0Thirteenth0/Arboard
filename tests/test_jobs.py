import json
import tempfile
import unittest
from pathlib import Path

from src.artboard_cutter_core.jobs import load_job, save_job
from src.artboard_cutter_core.profiles import ArtworkProfile


class JobFileTests(unittest.TestCase):
    def test_job_round_trip_preserves_queue_profile_settings(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "wall.artboard-job.json"
            original = ArtworkProfile(
                file_path="C:/Artwork/wall.pdf",
                output_name="Lobby Wall",
                source_page_index=2,
                source_page_count=4,
                panel_widths="100 100 100",
                height_mm="240",
                bleed_mm="5",
                overlap_mm="10",
                dpi="300",
                color_mode="CMYK",
                export_format="TIFF",
                selected=True,
            )
            save_job(path, [original])

            loaded = load_job(path)

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0], original)
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

    def test_invalid_job_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.json"
            path.write_text(json.dumps({"version": 999, "profiles": []}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unsupported or invalid"):
                load_job(path)


if __name__ == "__main__":
    unittest.main()
