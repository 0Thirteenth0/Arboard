# Rebuild Progress

Track rebuild, packaging, and executable generation progress here.

## 2026-05-19 - Audit phase

- Current codebase has been audited.
- No rebuild code changes have been made yet.
- Next recommended step: create modular engine/test structure while keeping the current GUI runnable.

## 2026-05-19 - Engine extraction phase 1

- Created the initial modular engine package under `src/artboard_cutter_core`.
- Added `tests/test_layout.py`.
- Added `tests/test_export_geometry.py`.
- Wired current GUI to call the extracted engine.
- The app remains runnable through `artboard_cutter_gui_advanced.py`.

## 2026-05-19 - Session settings persistence

- Extended `AppSettings` to persist bleed, overlap, DPI, export format, output folder, theme, and window geometry.
- Wired `artboard_cutter_gui_advanced.py` to restore these values at startup.
- Settings are saved when the app closes, when output folder is changed, and when export starts.

## 2026-05-19 - Vector stretch mode

- Added vector `stretch` mode to match raster's non-uniform user-dimension fit.
- Exposed `stretch` in the GUI vector fit dropdown and made it the default.
- Added automated coverage for non-uniform vector target dimensions.

## 2026-05-19 - Removed vector fit selector

- Removed the visible vector fit dropdown.
- GUI now always passes `stretch` when vector preservation is enabled.
- Output folder controls moved up to fill the removed row.

## 2026-05-19 - Explicit raster/vector export mode

- Replaced the old `Preserve vectors` checkbox with an explicit `Export mode` dropdown.
- User-facing modes are now `Raster` and `Vector`.
- `Vector` always uses stretch-to-fit internally.
- Selecting `Vector` forces PDF export because vector-preserving output is PDF-only.

## 2026-05-19 - Modern tkinter UI pass

- Routed startup through a new modern UI builder while keeping the existing export engine stable.
- Reworked the main layout into a large live preview area and a right-side production control panel.
- Added clearer sections: `Artwork Queue`, `Export Settings`, `Run`, and `Activity Log`.
- Added preview controls for fit, zoom in, zoom out, mouse wheel zoom, and drag panning.
- Added panel labels, bleed bands, overlap shading, final artwork outline, and panel export edges to the live preview.
- Added clearer validation/status messages before and during export.

## 2026-05-19 - Professional theme system

- Added 8 built-in themes.
- Replaced `Dark mode` checkbox in the modern UI with a `Theme` dropdown.
- Theme preference persists through existing app settings.
- Combobox mouse-wheel changes are blocked globally for `TCombobox` widgets.
- Preview overlay colors now use theme-specific tokens.

## 2026-05-19 - Queue profile/state cleanup

- Added `src/artboard_cutter_core/profiles.py`.
- Replaced the queue's mixed checkbox/path display with dedicated columns for selection, file name, original size, current size, output status, and actions.
- Added session-only per-artwork profile storage for original dimensions and current export settings.
- Switching selected artwork now saves the previous profile and loads the newly selected profile.
- Added `Reset Size` to restore the selected profile's original width and height only.
- Batch export now validates and uses each checked profile's saved values.
- Removed the old constructor dead branch from `artboard_cutter_gui_advanced.py`.
- Removed broad palette styling that caused normal text to look highlighted.

## 2026-05-19 - Testing backlog coverage

- Added `docs/testing.md` with local Tcl/Tk runtime notes and test coverage notes.
- Added guarded interactive GUI smoke tests.
- Added guarded preview snapshot validation across themes.
- Added guarded Windows high-DPI scaling smoke test.
- Added WCAG contrast-ratio checks for theme text/control token pairs.
- Added preview overlay contrast checks for every built-in theme.
- Added rendered raster/vector pixel alignment comparison.
- Added rotated PDF fixture export validation.
- Added unusual page box fixture export validation.
- GUI-dependent tests now skip cleanly when Tk cannot create a root window.

## 2026-05-19 - Multi-page/artboard queue import

- Added page-aware profile generation for supported source files.
- Added queue naming for multi-page files using source stem plus page number.
- Added editable queue output names.
- Added page-aware raster/vector export by passing `page_index` through `ExportOptions`.
- Added output-name validation and tests.
- Replaced literal `[ ]` / `[x]` select text with checkbox images in the Treeview select column.
- Added grouped parent queue rows for multi-page imports.
- Added manual optional Illustrator COM artboard-name lookup for `.ai` files on Windows.
- Added Windows-only `pywin32` dependency for Illustrator integration.

## 2026-05-19 - Rebuild Status Summary

Completed in this phase:

- Initial source audit.
- AI log structure and ongoing journal updates.
- Cleanup of generated build/export/cache folders.
- Extraction of core modules under `src/artboard_cutter_core/`.
- Runtime JSON logging support.
- Settings persistence for export parameters, output folder, theme, window geometry, and export mode.
- Settings persistence now also covers `overlap_mode`, with legacy settings defaulting to `Shared`.
- Raster/Vector export mode UI.
- Vector stretch-to-fit implementation using a full-size stretched vector master before clipping panels.
- Modern tkinter UI pass with clearer layout and production-oriented controls.
- Live preview improvements: panel labels, bleed regions, overlap zones, export edges, zoom, fit, and pan.
- Professional multi-theme system.
- Combobox wheel-change prevention.
- Session-only per-artwork queue profiles.
- Automated tests increased to 35, with 3 GUI-dependent tests skipped in the current local Tcl/Tk environment.

Latest settings verification:

- Verified `%LOCALAPPDATA%/ArtboardCutter/settings.json` already contains `overlap_mode` and `export_mode`.
- Added regression coverage for loading older settings files that do not yet contain `overlap_mode`.
- Removed the settings persistence verification note from `known_issues.md` because it is confirmed behavior, not an active issue.

## 2026-05-19 - Known limitation cleanup

- Removed unreachable old export bodies from compatibility wrapper functions in `artboard_cutter_gui_advanced.py`.
- Added wrapper compatibility test coverage to confirm the GUI-level `process_file()` wrapper still delegates correctly.
- Added `Open Logs Folder` to the Run panel for quick access to generated structured JSON logs.
- Expanded `docs/testing.md` with Tcl/Tk setup checks, manual GUI validation, preview/export equivalence guidance, queue widget limitations, Illustrator requirements, and log access notes.
- Added Illustrator fallback tests covering non-AI files and `require_running=True` when Illustrator is not running.
- Verified ignore rules for `TEST.pdf`, `test_outputs/`, and generated `logs/*.log*`.
- Automated tests increased to 38, with 3 GUI-dependent tests skipped in the current local Tcl/Tk environment.

Next recommended work:

- Fix the local Tcl/Tk runtime outside the repo so interactive GUI smoke/screenshot tests can run.
- Manually verify queue profile behavior in the GUI once Tk launches.
- Manually compare preview/export equivalence across themes with real production artwork.
- Build and manually test the Windows executable.

Current validation baseline:

- Core/layout/export/profile/theme/settings tests pass.
- GUI smoke, preview screenshot, and high-DPI tests exist but skip with the explicit local Tcl/Tk `init.tcl` error.
- Generated log/PDF/test-output artifacts are ignored.

## 2026-05-19 - Windows executable build

- Added generated application icon assets under `assets/`.
- Added icon generation script under `tools/`.
- Embedded the icon into PyInstaller spec files and the batch build.
- Built `dist/ArtboardCutter.exe` successfully.
- Created `dist/Artboard Cutter.lnk` with its icon explicitly set to the executable resource.
- Verified the executable exposes an associated icon through Windows icon extraction.

## 2026-05-19 - README and repository cleanup

- Added README screenshots for the application UI and exported panel outputs.
- Updated README with feature list, project layout, development setup, test command, Windows build command, and icon behavior.
- Consolidated executable builds around `ArtboardCutter.spec`.
- Removed duplicate `artboard_cutter_gui_advanced.spec`.
- Kept generated executable output local under ignored `dist/`.
- Added ignore coverage for local `.ai` artwork and root `.log` files.

## 2026-05-26 - Interactive live preview editing

- Added the first editable preview layer without changing export engine contracts.
- Middle mouse drag now pans the preview canvas.
- Mouse wheel remains the zoom control.
- Left mouse drag is limited to cached internal panel boundary hit targets; outside bleed edges are not draggable.
- Dragging a valid internal edge updates the two adjacent panel widths while preserving total content width.
- Added `Add Panel` in the Live Preview block; it splits the last panel width in half and appends the new panel without changing overall artwork size.
- Added core tests for the panel-editing math so future preview tools can reuse the same behavior.

Current validation baseline:

- `python -m compileall -q artboard_cutter_gui_advanced.py src tests` passed.
- `python -m unittest discover -s tests` passed: 44 tests, 3 skipped.
- The 3 skipped tests remain the known local Tcl/Tk GUI-runtime skips.

## 2026-05-26 - PDF Preserve for image inputs

- Renamed the visible fast PDF mode to `PDF Preserve`.
- Preserved backward compatibility for existing `Vector` settings and profile values.
- Allowed raster image inputs to use the fast PDF preserve pipeline by converting non-PDF PyMuPDF documents to an in-memory PDF before clipping.
- Updated README wording so raster images are described as embedded raster content inside PDF panels, not true vector artwork.
- Added tests for PNG source export through PDF Preserve mode.
- Rebuilt the Windows executable after the PDF Preserve and interactive preview changes.
- Refreshed README and `docs/testing.md` to document PDF Preserve terminology and interactive preview validation.

Current validation baseline:

- `python -m compileall -q artboard_cutter_gui_advanced.py src tests` passed.
- `python -m unittest discover -s tests` passed: 47 tests, 3 skipped.
- The 3 skipped tests remain the known local Tcl/Tk GUI-runtime skips.
## 2026-05-26 - UI reference polish

- Implemented a UI-only polish pass toward the provided Soft Blue reference.
- Added bundled local UI icons in `assets/icons/` and included them in the
  PyInstaller spec.
- Converted major UI sections toward soft card frames with lighter borders,
  cleaner headers, and icon-based actions.
- Expanded theme tokens for app/card/canvas/button/input/table/scrollbar
  styling and kept existing theme persistence behavior.
- Preserved export, geometry, PDF/raster, and file-processing logic.

## 2026-08-08 - Improvement pass complete

- Fixed JPG/TIFF routing and requested-DPI rendering.
- Changed Add Panel to divide complete artwork width evenly across the increased panel count.
- Added shared validation, collision checks, atomic replacement, stale-panel cleanup, and cancellation.
- Moved import inspection and preview rendering off the Tk thread.
- Added aspect warnings, AppData logs/defaults, recent paths, RGB/CMYK, presets, and queue job save/load.
- Reduced GUI/export duplication through focused core modules and lazy public imports.
- Pinned dependencies, added build metadata, rebuilt the Windows executable, and smoke-launched it successfully.
