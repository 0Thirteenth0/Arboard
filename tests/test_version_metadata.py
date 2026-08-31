import unittest
from pathlib import Path

from src.artboard_cutter_core.version import APP_VERSION
from tools.generate_version_metadata import version_parts


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class VersionMetadataTests(unittest.TestCase):
    def test_generated_release_metadata_matches_application_version(self):
        version_info = (PROJECT_ROOT / "version_info.txt").read_text(encoding="utf-8")
        installer_version = (PROJECT_ROOT / "installer" / "version.iss").read_text(encoding="utf-8")
        self.assertIn(f"FileVersion', '{APP_VERSION}'", version_info)
        self.assertIn(f'"{APP_VERSION}"', installer_version)

    def test_version_requires_numeric_components(self):
        self.assertEqual(version_parts("1.2.3"), (1, 2, 3, 0))
        with self.assertRaises(ValueError):
            version_parts("1.2-beta")

    def test_installer_registers_dedicated_job_extension(self):
        installer = (PROJECT_ROOT / "installer" / "ArtboardCutter.iss").read_text(encoding="utf-8")
        self.assertIn('Software\\Classes\\.artboard-job', installer)
        self.assertIn('""%1""', installer)
        self.assertNotIn('Software\\Classes\\.json', installer)


if __name__ == "__main__":
    unittest.main()
