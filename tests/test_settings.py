import tempfile
import unittest
from pathlib import Path

from src.artboard_cutter_core.settings import AppSettings, load_settings, normalize_layout_templates, save_settings


class SettingsTests(unittest.TestCase):
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
                '{"bleed_mm": "20", "overlap_mm": "40", "export_mode": "Vector"}',
                encoding="utf-8",
            )

            loaded = load_settings(path)

            self.assertEqual(loaded.bleed_mm, "20")
            self.assertEqual(loaded.overlap_mm, "40")
            self.assertEqual(loaded.export_mode, "PDF Preserve")
            self.assertEqual(loaded.overlap_mode, "Shared")

    def test_layout_templates_are_normalized_as_proportions(self):
        templates = normalize_layout_templates({"Triptych": {"ratios": [1, 2, 1]}, "Bad": {"ratios": [0]}})
        self.assertEqual(templates["Triptych"]["ratios"], [0.25, 0.5, 0.25])
        self.assertNotIn("Bad", templates)


if __name__ == "__main__":
    unittest.main()
