# Test Results

Track manual and automated test results here.

## 2026-05-19 - Baseline checks

- Prior syntax check passed for `artboard_cutter.py` and `artboard_cutter_gui_advanced.py` before this audit.
- No vector/raster alignment tests exist yet.
- No automated layout tests exist yet.

## 2026-05-19 - Engine extraction tests

- `python -m unittest discover -s tests`: passed, 7 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.

Coverage added:

- outside-only bleed
- shared internal overlap
- custom-width panel layout
- overlap clamping
- width parsing
- raster PDF output dimensions for generated fixture
- vector PDF output dimensions for generated fixture

Remaining test gaps:

- raster/vector pixel alignment comparison
- unusual page boxes
- rotated PDFs
- preview/export visual equivalence

## 2026-05-19 - Settings persistence tests

- `python -m unittest discover -s tests`: passed, 8 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.
- Added `tests/test_settings.py` to verify export parameter settings round-trip.

## 2026-05-19 - Manual TEST.pdf export checks

Source:

- `TEST.pdf`
- 1 page
- effective PyMuPDF page size: about `7000 x 2450 mm`
- rotation: `0`

Generated output folder:

- `test_outputs/`

Case 1:

- widths: `3500, 3500`
- height: `2450`
- bleed: `0`
- overlap: `0`
- DPI: `36`
- raster PDF and vector PDF outputs both produced two panels at `3500 x 2450 mm`.

Case 2:

- widths: `3500, 3500`
- height: `2450`
- bleed: `20`
- overlap: `40`
- DPI: `36`
- expected panel width: `3540 mm` because internal overlap is shared as `20 mm` on the adjoining side and outside bleed is `20 mm`.
- raster PDF and vector PDF outputs both produced two panels at `3540 x 2490 mm`.

Case 3:

- widths: `1200, 1200, 1100, 1230`
- total requested width: `4730 mm`
- height: `2000 mm`
- bleed: `0`
- overlap: `0`
- DPI: `36`
- raster PDF output page sizes:
  - `1200 x 2000 mm`
  - `1200 x 2000 mm`
  - `1100 x 2000 mm`
  - `1230 x 2000 mm`
- vector fit-by-height output page sizes matched the requested page sizes, but this does not prove content alignment because the source aspect ratio differs from the requested target aspect ratio.
- vector fit-by-width diagnostic output page height was about `1655.501 mm`, showing the uniform vector scale required to preserve full source width.

Case 4:

- same resize setup as Case 3
- vector fit mode: `stretch`
- output page sizes:
  - `1200 x 2000 mm`
  - `1200 x 2000 mm`
  - `1100 x 2000 mm`
  - `1230 x 2000 mm`
- This confirms non-uniform vector stretch now honors the same requested panel dimensions as raster mode.

Automated tests:

- `python -m unittest discover -s tests`: passed, 9 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.

Case 5:

- same resize setup as Case 4
- vector stretch pipeline changed to create a full-size stretched vector master before clipping panels
- output folder: `test_outputs/resize_vector_stretch_master/`
- output page sizes:
  - `1200 x 2000 mm`
  - `1200 x 2000 mm`
  - `1100 x 2000 mm`
  - `1230 x 2000 mm`
- `python -m unittest discover -s tests`: passed, 9 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.

## 2026-05-19 - Vector fit selector removal validation

- `python -m unittest discover -s tests`: passed, 9 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.
- Updated automated vector dimension test to use `stretch`.

## 2026-05-19 - Export mode selector validation

- `python -m unittest discover -s tests`: passed, 9 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.
- Settings round-trip now includes `export_mode`.

## 2026-05-19 - Modern UI validation

- `python -m unittest discover -s tests`: passed, 9 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.
- GUI smoke test attempted with `App()` creation, but this local Python/Tk install failed before app code with `TclError: Can't find a usable init.tcl`.
- The smoke test failure appears to be local Tcl/Tk installation/configuration, not a syntax failure.

## 2026-05-19 - Theme system validation

- `python -m unittest discover -s tests`: passed, 12 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.
- Added `tests/test_themes.py` to verify required themes, legacy fallback, invalid fallback, and preview overlay token coverage.

## 2026-05-19 - Current Test Status

Latest automated validation:

- `python -m unittest discover -s tests -v`: passed, 31 tests, 3 skipped.
- `python -m compileall -q artboard_cutter_gui_advanced.py src tests`: passed.

Current test files:

- `tests/test_layout.py`: panel layout, bleed, overlap, parsing.
- `tests/test_export_geometry.py`: generated PDF output dimensions for raster/vector paths.
- `tests/test_settings.py`: persisted settings round-trip.
- `tests/test_themes.py`: built-in theme registry and preview token coverage.
- `tests/test_profiles.py`: session profile reset behavior and vector mode rules.
- `tests/test_gui_smoke.py`: guarded interactive GUI launch, preview snapshot, and Windows scaling checks.
- `tests/test_export_visual_alignment.py`: rendered raster/vector pixel alignment comparison.

Most recent change validation:

- Added `ArtworkProfile` model tests.
- Verified reset-to-original uses per-profile original dimensions.
- Verified missing original dimensions do not overwrite current values.
- Verified vector profile rules force PDF and `stretch`.
- Added contrast-ratio checks for text and preview overlay token pairs across every built-in theme.
- Added generated rotated PDF and unusual page box fixture export tests.
- Added raster/vector rendered pixel comparison using generated stripe artwork.
- Added GUI smoke tests that skip cleanly when Tk cannot create an interactive root.
- Added multi-page import/profile tests.
- Added custom output-name export filename test.
- Added regression test verifying `page_index=1` exports the second page rather than the first page.
- Added output name validation tests.
- Added Illustrator artboard-name import tests using injected artboard names so tests do not require Illustrator.
- Manually verified optional Illustrator COM integration against `AI_TEST.ai`.
- Added left-overlap layout regression coverage.
- Added left-overlap vector export dimension coverage.
- Added overlap-mode settings/profile coverage.
- Added legacy settings regression coverage for files missing `overlap_mode`.
- Verified the current AppData settings file already contains `overlap_mode` and `export_mode`.

Latest automated run:

- `python -m compileall -q artboard_cutter_gui_advanced.py src tests` passed.
- `python -m unittest discover -s tests` passed: 38 tests run, 3 skipped.
- `python -m unittest tests.test_gui_smoke -v` confirmed all GUI tests skip with the explicit local Tcl/Tk `init.tcl` error.
- `git check-ignore -v TEST.pdf test_outputs logs\app.log logs\export.log gude-2026-05-19.log` confirmed local PDF, test output, and generated log artifacts are ignored.
- Added GUI wrapper compatibility coverage.
- Added Illustrator fallback coverage for non-AI files and `require_running=True` without an Illustrator process.
- Added blank-DPI validation coverage: Vector allows blank DPI, Raster rejects blank DPI with a clear message.

Most recent hotfix run:

- `python -m compileall -q artboard_cutter_gui_advanced.py src tests` passed.
- `python -m unittest discover -s tests` passed: 40 tests run, 3 skipped.

Executable/icon validation:

- `python tools\generate_icon.py` wrote `assets/artboard_cutter.ico` and `assets/artboard_cutter_icon.png`.
- `pyinstaller --clean --noconfirm ArtboardCutter.spec` completed successfully.
- Built executable: `dist/ArtboardCutter.exe`.
- PyInstaller reported `Copying icon to EXE`.
- Extracted the associated icon from the built executable successfully.
- Created shortcut: `dist/Artboard Cutter.lnk`, with `IconLocation` set to `dist/ArtboardCutter.exe,0`.

README/repo cleanup validation:

- README screenshots generated under `docs/screenshots/`.
- Build path consolidated to `ArtboardCutter.spec`.
- Generated `dist/` output remains ignored/local while icon assets and README screenshots are trackable.

Skipped tests:

- `tests.test_gui_smoke.GuiSmokeTests.test_interactive_app_can_launch_and_close`
- `tests.test_gui_smoke.GuiSmokeTests.test_preview_snapshot_across_themes`
- `tests.test_gui_smoke.GuiSmokeTests.test_high_dpi_windows_scaling_smoke`

Skip reason:

- Local Python/Tk cannot create `Tk()` because Tcl reports it cannot find a usable `init.tcl` under `C:\Users\jiahu\AppData\Local\Programs\Python\Python313\tcl\tcl8.6`.
- `init.tcl` exists at that path, so this is documented as a local Tcl/Tk runtime resolution issue rather than an application import or syntax issue.

Manual checks performed:

- `TEST.pdf` actual-size split.
- `TEST.pdf` resized raster split.
- `TEST.pdf` vector stretch split.
- `TEST.pdf` vector stretch-master split.

Remaining validation needs:

- Interactive GUI launch after local Tcl/Tk issue is resolved.
- Screenshot-based preview validation across themes.
- Hands-on queue profile behavior checks in a working GUI runtime.
- Hands-on preview/export equivalence review across themes and real artwork.
- High-DPI Windows scaling check.

Already covered by automated tests:

- Rendered raster/vector pixel alignment comparison with generated fixture artwork.
- Rotated PDF fixture behavior.
- Unusual page box fixture behavior.
- Theme contrast-token checks.
- Settings persistence and legacy settings fallback.
