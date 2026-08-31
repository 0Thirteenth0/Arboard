import tempfile
import unittest
from pathlib import Path

from src.artboard_cutter_core.settings import AppSettings, load_settings, save_settings


class SettingsTests(unittest.TestCase):
    def test_non_object_settings_json_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            path.write_text("[]", encoding="utf-8")

            settings = load_settings(path)

            self.assertEqual(settings, AppSettings())

    def test_wrong_settings_types_are_sanitized(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            path.write_text(
                '{"bleed_mm": [], "recent_files": ["good.pdf", [], ""], "recent_output_dirs": "bad"}',
                encoding="utf-8",
            )

            settings = load_settings(path)

            self.assertEqual(settings.bleed_mm, "0")
            self.assertEqual(settings.recent_files, ["good.pdf"])
            self.assertEqual(settings.recent_output_dirs, [])

    def test_invalid_window_geometry_is_discarded(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            path.write_text('{"window_geometry": "not geometry"}', encoding="utf-8")

            self.assertEqual(load_settings(path).window_geometry, "")

    def test_fresh_defaults_are_export_ready(self):
        settings = AppSettings()
        self.assertEqual(settings.bleed_mm, "0")
        self.assertEqual(settings.overlap_mm, "0")
        self.assertEqual(settings.dpi, "150")
        self.assertEqual(settings.color_mode, "RGB")
        self.assertEqual(settings.theme, "Soft Blue")

    def test_export_params_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            settings = AppSettings(
                last_output_dir="C:/Exports",
                bleed_mm="20",
                overlap_mm="40",
                overlap_mode="Left",
                dpi="300",
                color_mode="CMYK",
                export_format="TIFF",
                export_mode="PDF Preserve",
                theme="light",
                window_geometry="1000x800+10+20",
                presets={
                    "Wall": {
                        "panel_widths": "100 100",
                        "height_mm": "240",
                        "last_output_dir": "C:/ShouldNotBeInPreset",
                        "color_mode": "CMYK",
                    }
                },
            )
            save_settings(settings, path)
            self.assertEqual(list(path.parent.glob(".settings.json.*.tmp")), [])

            loaded = load_settings(path)
            self.assertEqual(loaded.last_output_dir, "C:/Exports")
            self.assertEqual(loaded.bleed_mm, "20")
            self.assertEqual(loaded.overlap_mm, "40")
            self.assertEqual(loaded.overlap_mode, "Left")
            self.assertEqual(loaded.dpi, "300")
            self.assertEqual(loaded.color_mode, "CMYK")
            self.assertEqual(loaded.export_format, "TIFF")
            self.assertEqual(loaded.export_mode, "PDF Preserve")
            self.assertEqual(loaded.theme, "light")
            self.assertEqual(loaded.window_geometry, "1000x800+10+20")
            self.assertEqual(loaded.presets["Wall"], {"color_mode": "CMYK"})

    def test_legacy_settings_missing_overlap_mode_get_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            path.write_text(
                '{"bleed_mm": "20", "overlap_mm": "40", "export_mode": "Vector", '
                '"layout_templates": {"Legacy": {"ratios": [1, 1]}}}',
                encoding="utf-8",
            )

            loaded = load_settings(path)

            self.assertEqual(loaded.bleed_mm, "20")
            self.assertEqual(loaded.overlap_mm, "40")
            self.assertEqual(loaded.export_mode, "PDF Preserve")
            self.assertEqual(loaded.overlap_mode, "Shared")
            self.assertFalse(hasattr(loaded, "layout_templates"))


if __name__ == "__main__":
    unittest.main()
