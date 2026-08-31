import json
import tempfile
import unittest
from pathlib import Path

from src.artboard_cutter_core.jobs import is_job_file_path, load_job, save_job, startup_job_path
from src.artboard_cutter_core.profiles import ArtworkProfile


class JobFileTests(unittest.TestCase):
    def test_startup_job_path_accepts_new_and_legacy_extensions(self):
        self.assertEqual(
            startup_job_path([r"C:\Artwork Jobs\wall.artboard-job"]),
            Path(r"C:\Artwork Jobs\wall.artboard-job"),
        )
        self.assertEqual(
            startup_job_path([r"C:\Artwork Jobs\legacy.artboard-job.json"]),
            Path(r"C:\Artwork Jobs\legacy.artboard-job.json"),
        )
        self.assertIsNone(startup_job_path(["--self-test", r"C:\Artwork Jobs\notes.json"]))
        self.assertTrue(is_job_file_path("WALL.ARTBOARD-JOB"))

    def test_non_object_job_json_is_rejected_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.artboard-job.json"
            path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "invalid Artboard Cutter job"):
                load_job(path)

    def test_job_round_trip_preserves_queue_profile_settings(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "wall.artboard-job"
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

    def test_inconsistent_page_index_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad-page.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "profiles": [
                            {"file_path": "source.pdf", "output_name": "source", "source_page_index": 2, "source_page_count": 1}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "source page values"):
                load_job(path)

    def test_non_boolean_selection_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad-selection.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "profiles": [{"file_path": "source.pdf", "output_name": "source", "selected": "false"}],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "selected must"):
                load_job(path)

    def test_invalid_original_dimension_type_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad-dimension.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "profiles": [{"file_path": "source.pdf", "original_width_mm": "not-a-number"}],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "original_width_mm"):
                load_job(path)


if __name__ == "__main__":
    unittest.main()
