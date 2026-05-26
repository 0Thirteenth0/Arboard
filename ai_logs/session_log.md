# Session Log

Track AI-assisted work sessions here.

## 2026-05-19 - Rebuild audit kickoff

- Read the current source of truth: `artboard_cutter_gui_advanced.py`.
- Read supporting files: `artboard_cutter.py`, `build_exe.bat`, `requirements.txt`, `ArtboardCutter.spec`, and `artboard_cutter_gui_advanced.spec`.
- Compared deleted historical GUI files from Git history only; did not restore them.
- Confirmed current working tree has uncommitted deletions for `artboard_cutter_gui.py` and `artboard_cutter_gui_v1.py` from the prior cleanup.
- No commit or push was performed.

## 2026-05-19 - First modular extraction

- Added `src/artboard_cutter_core/` as the first engine package.
- Extracted units, layout, PDF opening/page boxes, raster image saving, raster export, vector export, export orchestration, settings, and structured logging modules.
- Bound `artboard_cutter_gui_advanced.py` to the extracted engine while keeping existing GUI structure and public helper names intact.
- Added `tests/` with layout tests and generated-PDF export dimension tests.
- Added `logs/.gitkeep`; generated runtime `.log` files are ignored.
- No commit or push was performed.

## 2026-05-19 - Persist last-used export parameters

- Added persisted settings fields for bleed, overlap, DPI, export format, and output folder.
- Updated the GUI to load those values on launch and save them on close/export.
- Added a non-GUI settings round-trip test.
- No commit or push was performed.

## 2026-05-19 - Session Rollup

- Tested `TEST.pdf` with actual-size and resized panel configurations.
- Confirmed raster non-uniform resize behavior and diagnosed vector uniform-fit mismatch.
- Implemented vector stretch-to-fit by creating a full-size stretched vector master and clipping panels from that master.
- Removed user-facing vector fit-by-height/fit-by-width choices.
- Added explicit Raster/Vector mode selection.
- Reworked the UI into a more polished production-tool layout.
- Added live preview labels and overlays for panels, bleed, overlap, and export edges.
- Added professional theme system with 8 themes and persistent selection.
- Prevented combobox values from changing through mouse-wheel scrolling.
- Ran automated tests and compile checks successfully after major changes.
- No commit or push was performed.

## 2026-05-19 - Queue profile and UI state cleanup

- Added session-only `ArtworkProfile` objects for queued files.
- Queue rows now store per-artwork settings in memory: original size, current panel widths/height, bleed, overlap, DPI, export format, export mode, vector preservation, fit mode, status, and validation state.
- Changed queue columns to separate `Select`, `File Name`, `Original Size`, `Current Size`, `Output Status`, and `Actions`.
- Replaced the old mixed checkbox/path display with a dedicated select column and row status column.
- Added `Reset Size`, which restores only the selected artwork from its stored original dimensions.
- Changed the label `Target height` to `Height`.
- Export now validates and runs each checked artwork using that artwork's saved profile settings, not the currently selected row's global form values.
- Removed aggressive Tk palette assignment that made labels and text look constantly highlighted in several themes.
- Kept app-level persisted settings limited to global defaults such as output folder, theme, and last-used parameter defaults.
- No commit or push was performed.

## 2026-05-19 - GUI/export testing backlog

- Added GUI smoke tests with explicit Tcl/Tk skip handling.
- Verified local Python 3.13 still cannot create a Tk root due Tcl `init.tcl` resolution, even though the file exists on disk.
- Added theme contrast-ratio tests across all built-in themes.
- Added preview overlay contrast checks.
- Added preview snapshot validation across themes, guarded by Tk availability.
- Added rendered raster/vector pixel alignment test.
- Added rotated PDF and unusual page box fixture tests.
- Added guarded Windows high-DPI scaling smoke test.
- Added `docs/testing.md` to document the Tcl/Tk blocker and test behavior.
- Ran the full suite: 23 tests passed/skipped cleanly, with 3 GUI tests skipped due local Tcl/Tk.
- No commit or push was performed.

## 2026-05-19 - Export settings row layout fix

- Replaced the `Export Settings` grid layout with explicit horizontal rows.
- Fixed a visual issue where a text field could occupy the label area above `Bleed (mm)`.
- Kept `Height (mm)`, the height input, and `Reset Size` on one row.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Multi-page import and queue output names

- Added page-aware artwork profile creation.
- Import now creates one `ArtworkProfile` per source page/artboard instead of using only page 1.
- Multi-page queue names use the source stem plus ascending page number, such as `Poster1`, `Poster2`, `Poster3`.
- Single-page queue names use the source stem.
- Added editable queue output names through double-clicking the File Name cell.
- Added output-name validation for empty names, Windows-invalid filename characters, and `.` / `..`.
- Export now passes both `source_page_index` and editable `output_name` into the core export pipeline.
- Raster and vector exporters now load the requested source page instead of hardcoding page 0.
- Replaced text `[ ]` / `[x]` queue selection values with checkbox images in the Select column.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Illustrator artboard name integration

- Added optional Windows Adobe Illustrator COM integration for `.ai` artboard names.
- Verified `AI_TEST.ai` through Illustrator COM returns:
  - `Artboard 1`
  - `Artboard 2`
  - `Artboard 2 copy`
  - `Artboard 2 copy 2`
  - `Artboard 2 copy 3`
  - `Artboard 2 copy 4`
- `create_artwork_profiles()` now uses Illustrator artboard names when available and falls back to stem-plus-page numbering otherwise.
- Added output-name sanitization for Windows-invalid filename characters.
- Added duplicate-name disambiguation.
- Added `pywin32` as a Windows-only dependency.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Grouped multi-page queue and manual artboard names

- Changed default multi-page import to use numbered names first instead of automatically asking Illustrator.
- Added parent queue rows for multi-page files; the parent row is named with the original filename and can be expanded/collapsed through the Treeview arrow.
- Child rows remain one `ArtworkProfile` per page/artboard.
- Parent rows show a `Get Names` action that manually reads Illustrator artboard names for `.ai` files.
- Single-page imports remain flat and do not get a group row.
- Group check/uncheck toggles all child profiles.
- Export remains profile-based and only exports child artwork profiles.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Queue group column and Illustrator alert handling

- Moved the Treeview hierarchy/expand arrow into the File Name column.
- Kept a separate Select column for parent and child selection state.
- Parent Select toggles all child profiles.
- Parent File Name now has the native expand/collapse arrow with a wider click target.
- Illustrator artboard-name lookup now sets Illustrator to no-alert mode before opening the `.ai` file, then restores the prior interaction level.
- Re-verified `AI_TEST.ai` artboard names through the updated Illustrator integration.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Illustrator name lookup timeout

- Moved manual Illustrator name lookup onto a background thread so the Artboard Cutter UI does not block.
- Wrapped Illustrator COM name lookup in a subprocess timeout for source/development runs.
- If Illustrator hangs while opening a document, the lookup returns unavailable instead of waiting forever.
- Verified a 5-second timeout returns cleanly when Illustrator is stuck.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Avoid fresh Illustrator startup for name lookup

- Changed GUI `Get Names` to require Illustrator to already be running.
- This avoids launching Illustrator from Artboard Cutter, which can freeze during Illustrator startup/loading on this machine.
- If Illustrator is not running or is unresponsive, the app keeps numbered names and shows a warning.
- Existing Illustrator processes are not force-closed by Artboard Cutter.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Left overlap mode

- Added `Overlap Mode` to the export settings with `Shared` and `Left` choices.
- `Shared` keeps the original half-overlap-on-each-side behavior.
- `Left` makes panel 2 and later overlap left by the full overlap amount; panel 1 has outside bleed only and no internal overlap.
- Passed overlap mode through preview, profile state, settings persistence, raster export, and vector export.
- Added tests for left-overlap layout, exported panel dimensions, settings persistence, and profile creation.
- Reconfirmed that `ttk.Treeview` cannot put a separate Select checkbox column before File Name while keeping the native expand/collapse arrow inside File Name.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Mode controls moved above bleed

- Moved `Export Mode` and `Overlap Mode` to the top of Export Settings before Bleed.
- Replaced both two-option dropdowns with radio selections because each setting only has two valid choices.
- Placed both mode selectors on the same line to reduce vertical space and make the main export behavior visible first.
- Kept the same backing variables so profile state, preview updates, export logic, and settings persistence continue to work.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Radio/check highlight fix

- Added explicit theme maps for `TRadiobutton` and `TCheckbutton`.
- Active, pressed, selected, and disabled toggle states now keep the theme panel background instead of using the operating-system default highlight color.
- This prevents mode selections from appearing as bright highlighted text blocks in dark themes such as Midnight.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Theme combobox and queue header hover polish

- Added combobox selection clearing for the theme selector so the current theme name does not stay visibly highlighted.
- Added combobox select-background tokens so readonly combobox text uses normal entry colors.
- Locked Treeview heading active/pressed colors to the normal heading colors so artwork queue column names do not change on hover.
- Updated button hover maps to use theme-aware hover backgrounds, readable foregrounds, and accent borders.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Settings persistence verification

- Verified `AppSettings` includes the new `overlap_mode` value along with existing export/session defaults.
- Verified the local AppData settings file already contains `overlap_mode: Left` and `export_mode: Vector`.
- Added a regression test confirming older settings files without `overlap_mode` load with the safe `Shared` default.
- Updated all AI journal files with the persistence check.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Known issues cleanup

- Removed the settings persistence verification block from `known_issues.md`.
- Kept the Tcl/Tk runtime limitation as the active issue because it still affects local automated GUI smoke/screenshot tests.
- Left settings persistence documented in progress/test/session logs as verified behavior.
- No commit or push was performed.

## 2026-05-19 - Current known limitations pass

- Rechecked the Tcl/Tk blocker and kept GUI smoke/screenshot tests guarded with the exact Tk exception in skip output.
- Removed unreachable legacy export bodies after GUI compatibility wrapper delegation.
- Added `Open Logs Folder` to the Run panel with platform-specific folder opening and error handling.
- Added wrapper compatibility and Illustrator fallback tests.
- Expanded `docs/testing.md` with local Tk setup checks, manual GUI verification, preview/export equivalence checks, queue widget constraints, Illustrator requirements, and runtime log access.
- Verified `TEST.pdf`, `test_outputs/`, and generated `logs/*.log*` remain ignored.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - AI log refresh

- Reclassified old audit bullets in `known_issues.md` so resolved findings are not presented as current blockers.
- Updated `rebuild_progress.md` next steps to focus on the actual remaining validation work: local Tcl/Tk repair, manual GUI checks, preview/export review, and Windows executable testing.
- Confirmed the latest validation baseline remains 38 tests with 3 GUI/Tk skips.
- No commit or push was performed.

## 2026-05-19 - Blank DPI vector export fix

- Fixed export validation failing with `invalid literal for int() with base 10: ''` when Vector mode is selected and DPI is blank.
- Vector export does not use DPI, so blank or nonnumeric DPI now falls back to an internal placeholder value of 72 during validation.
- Raster export still requires a nonblank positive DPI and now reports `DPI is required for Raster export.` for an empty field.
- Added regression tests for blank-DPI Vector validation and blank-DPI Raster validation.
- Ran compile and tests successfully: 40 tests, 3 GUI/Tk skips.
- No commit or push was performed.

## 2026-05-19 - Application icon and executable build

- Added `tools/generate_icon.py` to generate a unique Artboard Cutter icon.
- Generated `assets/artboard_cutter.ico` and `assets/artboard_cutter_icon.png`.
- The icon concept uses staggered artboard panels, production colors, and a diagonal cutter blade.
- Embedded the icon into PyInstaller builds through both spec files and `build_exe.bat`.
- Added the icon as bundled data so the tkinter window can use it at runtime.
- Updated `artboard_cutter_gui_advanced.py` to set the window icon from `assets/artboard_cutter.ico` when available.
- Built `dist/ArtboardCutter.exe` successfully with PyInstaller.
- Verified Windows could extract an associated icon from the built executable.
- Created `dist/Artboard Cutter.lnk` with `IconLocation` pointing at `ArtboardCutter.exe,0`, so the shortcut uses the embedded executable icon.
- Ran compile and tests successfully before the build: 40 tests, 3 GUI/Tk skips.
- No commit or push was performed.

## 2026-05-19 - README screenshots and repository cleanup

- Added README screenshots under `docs/screenshots/`.
- Updated README with current feature summary, screenshots, project layout, development setup, test command, build command, and icon/shortcut notes.
- Consolidated PyInstaller configuration to `ArtboardCutter.spec` and removed the duplicate `artboard_cutter_gui_advanced.spec`.
- Updated `build_exe.bat` to regenerate the icon and build from `ArtboardCutter.spec`.
- Cleaned generated cache/test-output/build-log artifacts while keeping the finished `dist/ArtboardCutter.exe` available locally.
- Updated `.gitignore` so local `.ai` artwork and root `.log` files remain ignored, while documentation screenshots and icon assets are trackable.
- No commit or push was performed yet in this entry.

## 2026-05-26 - Interactive preview editor foundation

- Added pure layout helpers for interactive panel editing: split the last panel into two equal panels and resize adjacent panel widths while preserving total content width.
- Added layout tests covering Add Panel behavior, total-width preservation, min-width clamping, and rejection of non-internal bleed-edge indices.
- Reworked live preview input handling so middle mouse drag pans the canvas and left mouse drag is reserved for valid internal panel boundaries only.
- Added hover cursor feedback and cached preview transform/edge targets for overlap-edge hit detection.
- Added an `Add Panel` button inside the Live Preview header; it appends a panel by splitting the last panel width without changing overall artwork size.
- Dragging an internal boundary updates the Panel Widths field live, saves the active `ArtworkProfile`, and redraws the preview through the same layout path used by export.
- Validation run: compile passed; full unit suite passed with 44 tests and the existing 3 guarded GUI/Tk skips.

## 2026-05-26 - Preview seam overlap protection

- Updated interactive seam dragging so a drag cannot create panel widths smaller than the requested overlap value.
- When the dragged seam crosses that protected limit, the preview width list resets to the widths from before the drag movement instead of letting `compute_panel_layout()` shrink the effective overlap.
- Kept export/layout behavior unchanged for manually typed extreme values; the protection is specific to interactive preview editing.
- Added tests for non-clamping drag reset behavior and overlap-preserving minimum width behavior.
- Validation run: compile passed; full unit suite passed with 46 tests and the existing 3 guarded GUI/Tk skips.
