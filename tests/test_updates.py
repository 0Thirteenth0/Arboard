import unittest
from unittest.mock import MagicMock, patch

from src.artboard_cutter_core.updates import UpdateInfo, check_for_update
from src.artboard_cutter_core.version import APP_VERSION


class UpdateVersionTests(unittest.TestCase):
    def test_equivalent_short_version_is_not_newer(self):
        self.assertFalse(UpdateInfo("1.2", "https://example.invalid/download").is_newer)

    def test_patch_release_is_newer(self):
        parts = [int(part) for part in APP_VERSION.split(".")]
        parts[-1] += 1
        next_patch = ".".join(str(part) for part in parts)
        self.assertTrue(UpdateInfo(next_patch, "https://example.invalid/download").is_newer)

    def test_invalid_version_is_not_newer(self):
        self.assertFalse(UpdateInfo("not-a-version", "https://example.invalid/download").is_newer)

    def test_update_manifest_requires_https(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            check_for_update("http://example.invalid/manifest.json")

    def test_valid_update_manifest_is_parsed(self):
        response = MagicMock()
        response.read.return_value = (
            b'{"version":"1.3.0","download_url":"https://example.invalid/app.exe",'
            b'"notes_url":"https://example.invalid/notes","sha256":"ABCDEF"}'
        )
        context = MagicMock()
        context.__enter__.return_value = response
        context.__exit__.return_value = False

        with patch("src.artboard_cutter_core.updates.urlopen", return_value=context):
            update = check_for_update("https://example.invalid/manifest.json")

        self.assertEqual(update.version, "1.3.0")
        self.assertEqual(update.sha256, "abcdef")
        self.assertTrue(update.is_newer)

    def test_non_object_update_manifest_is_rejected(self):
        response = MagicMock()
        response.read.return_value = b"[]"
        context = MagicMock()
        context.__enter__.return_value = response
        context.__exit__.return_value = False

        with patch("src.artboard_cutter_core.updates.urlopen", return_value=context):
            with self.assertRaisesRegex(ValueError, "JSON object"):
                check_for_update("https://example.invalid/manifest.json")


if __name__ == "__main__":
    unittest.main()
