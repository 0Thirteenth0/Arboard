import unittest
from pathlib import Path
from subprocess import TimeoutExpired
from types import SimpleNamespace
from unittest import mock

from src.artboard_cutter_core.illustrator_integration import (
    _get_illustrator_artboard_names_subprocess,
    _illustrator_process_ids,
    get_illustrator_artboard_names,
)


class IllustratorIntegrationTests(unittest.TestCase):
    def test_non_ai_files_do_not_use_illustrator(self):
        self.assertIsNone(get_illustrator_artboard_names(Path("sample.pdf"), require_running=True))

    def test_require_running_returns_none_when_illustrator_is_not_running(self):
        with mock.patch("src.artboard_cutter_core.illustrator_integration.sys.platform", "win32"):
            with mock.patch("src.artboard_cutter_core.illustrator_integration._illustrator_process_ids", return_value=set()):
                self.assertIsNone(get_illustrator_artboard_names(Path("sample.ai"), require_running=True))

    def test_subprocess_artboard_names_are_parsed(self):
        result = SimpleNamespace(returncode=0, stdout='["Front", "Back"]')
        with mock.patch(
            "src.artboard_cutter_core.illustrator_integration._illustrator_process_ids",
            return_value={10},
        ), mock.patch(
            "src.artboard_cutter_core.illustrator_integration.subprocess.run",
            return_value=result,
        ):
            names = _get_illustrator_artboard_names_subprocess(Path("sample.ai"), 5, require_running=True)

        self.assertEqual(names, ["Front", "Back"])

    def test_timed_out_subprocess_triggers_automation_cleanup(self):
        with mock.patch(
            "src.artboard_cutter_core.illustrator_integration._illustrator_process_ids",
            return_value={10},
        ), mock.patch(
            "src.artboard_cutter_core.illustrator_integration.subprocess.run",
            side_effect=TimeoutExpired("python", 1),
        ), mock.patch(
            "src.artboard_cutter_core.illustrator_integration._terminate_new_illustrator_processes"
        ) as terminate:
            names = _get_illustrator_artboard_names_subprocess(Path("sample.ai"), 1)

        self.assertIsNone(names)
        terminate.assert_called_once_with({10})

    def test_illustrator_process_list_parser_filters_other_apps(self):
        tasklist = SimpleNamespace(
            returncode=0,
            stdout='"Illustrator.exe","123","Console","1","10,000 K"\n"python.exe","456","Console","1","1,000 K"\n',
        )
        with mock.patch("src.artboard_cutter_core.illustrator_integration.sys.platform", "win32"), mock.patch(
            "src.artboard_cutter_core.illustrator_integration.subprocess.run",
            return_value=tasklist,
        ):
            self.assertEqual(_illustrator_process_ids(), {123})


if __name__ == "__main__":
    unittest.main()
