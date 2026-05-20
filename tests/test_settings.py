import tempfile
import unittest
from pathlib import Path

from src.artboard_cutter_core.settings import AppSettings, load_settings, save_settings


class SettingsTests(unittest.TestCase):
    def test_export_params_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            settings = AppSettings(
                last_output_dir="C:/Exports",
                bleed_mm="20",
                overlap_mm="40",
                overlap_mode="Left",
                dpi="300",
                export_format="TIFF",
                export_mode="Vector",
                theme="light",
                window_geometry="1000x800+10+20",
            )
            save_settings(settings, path)

            loaded = load_settings(path)
            self.assertEqual(loaded.last_output_dir, "C:/Exports")
            self.assertEqual(loaded.bleed_mm, "20")
            self.assertEqual(loaded.overlap_mm, "40")
            self.assertEqual(loaded.overlap_mode, "Left")
            self.assertEqual(loaded.dpi, "300")
            self.assertEqual(loaded.export_format, "TIFF")
            self.assertEqual(loaded.export_mode, "Vector")
            self.assertEqual(loaded.theme, "light")
            self.assertEqual(loaded.window_geometry, "1000x800+10+20")

    def test_legacy_settings_missing_overlap_mode_get_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            path.write_text(
                '{"bleed_mm": "20", "overlap_mm": "40", "export_mode": "Vector"}',
                encoding="utf-8",
            )

            loaded = load_settings(path)

            self.assertEqual(loaded.bleed_mm, "20")
            self.assertEqual(loaded.overlap_mm, "40")
            self.assertEqual(loaded.export_mode, "Vector")
            self.assertEqual(loaded.overlap_mode, "Shared")


if __name__ == "__main__":
    unittest.main()
