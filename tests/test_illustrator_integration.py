import unittest
from pathlib import Path
from unittest import mock

from src.artboard_cutter_core.illustrator_integration import get_illustrator_artboard_names


class IllustratorIntegrationTests(unittest.TestCase):
    def test_non_ai_files_do_not_use_illustrator(self):
        self.assertIsNone(get_illustrator_artboard_names(Path("sample.pdf"), require_running=True))

    def test_require_running_returns_none_when_illustrator_is_not_running(self):
        with mock.patch("src.artboard_cutter_core.illustrator_integration.sys.platform", "win32"):
            with mock.patch("src.artboard_cutter_core.illustrator_integration._illustrator_process_ids", return_value=set()):
                self.assertIsNone(get_illustrator_artboard_names(Path("sample.ai"), require_running=True))


if __name__ == "__main__":
    unittest.main()
