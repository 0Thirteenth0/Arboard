# Testing Notes

## Local Tcl/Tk Runtime

Interactive GUI smoke tests are guarded because the current local Python 3.13
Tk runtime cannot create a Tcl interpreter in this environment.

Observed command:

```powershell
python -m unittest tests.test_gui_smoke -v
```

Observed skip reason:

```text
Tk unavailable for interactive GUI smoke tests: Can't find a usable init.tcl in the following directories:
    {C:\Users\jiahu\AppData\Local\Programs\Python\Python313\tcl\tcl8.6}

This probably means that Tcl wasn't installed properly.
```

The file `init.tcl` exists at that path, so this appears to be a local Python/Tcl
installation/runtime resolution issue rather than an application import or syntax
failure. The tests skip with the exact exception until Tk can create `Tk()`.

Local setup checks:

```powershell
python -c "import tkinter as tk; root=tk.Tk(); print(root.tk.call('info','patchlevel')); root.destroy()"
python -m unittest tests.test_gui_smoke -v
```

If the first command fails before application code runs, repair or reinstall the
local Python Tcl/Tk runtime. On Windows, also check that `TCL_LIBRARY` and
`TK_LIBRARY` are not pointing at stale Tcl/Tk folders from another Python
installation. The guarded GUI tests are designed to report the exact exception
instead of failing unrelated CI jobs.

## Test Coverage Added

- Theme WCAG contrast checks for all built-in theme foreground/background pairs.
- Preview overlay contrast checks for all built-in themes.
- Interactive GUI launch smoke test, skipped when Tk is unavailable.
- Preview screenshot/snapshot smoke test across themes, skipped when Tk or screenshot capture is unavailable.
- Windows high-DPI scaling smoke test, skipped outside Windows or when Tk is unavailable.
- Raster/vector rendered pixel alignment test.
- Rotated PDF fixture export test.
- Unusual page box fixture export test.
- GUI wrapper compatibility test that verifies legacy public wrappers still
  delegate into the extracted export engine.
- Illustrator integration fallback tests that do not require Illustrator.

## Manual GUI Validation

Run these checks after `tkinter.Tk()` works locally:

- Launch `python artboard_cutter_gui_advanced.py`.
- Add one single-page file and one multi-page/AI-compatible file.
- Confirm selecting different queue rows restores each row's independent width,
  height, bleed, overlap, overlap mode, DPI, export format, and export mode.
- Confirm parent queue selection toggles all child rows and child row selection
  updates the parent `n/n selected` status.
- Use `Reset Size` on one child row and confirm no other child row changes.
- Switch every built-in theme and confirm labels, radio selections, buttons,
  queue rows, queue headings, and preview overlays remain readable.
- Export both Raster and Vector with `Shared` and `Left` overlap modes; compare
  panel dimensions and visible overlap zones against the live preview.

## Preview/Export Equivalence

The preview and export paths share `compute_panel_layout()`, so geometry should
match for panel boundaries, outside-only bleed, and overlap zones. Screenshot
validation is guarded by Tk availability in `tests/test_gui_smoke.py`.

Manual visual checks should include:

- Equal-width and custom-width panels.
- Outside bleed visible only on the full artwork's outside edges.
- `Shared` overlap split between neighbors.
- `Left` overlap where only the right/later panel extends left.
- Raster and Vector output rendered back to pixels for visible alignment.
- Theme changes without preview overlay loss.

## Runtime Logs

JSON runtime logs are written under:

```text
logs/
```

The GUI includes an `Open Logs Folder` button in the Run panel. The action
creates the folder if needed and opens it with the platform file browser. If the
platform opener fails, the GUI shows a readable error dialog.

## Queue Widget Limits

The queue uses `ttk.Treeview` for native row grouping, selection, scrolling, and
editing behavior. `Treeview` cells cannot embed real native ttk checkbox widgets,
so the Select column uses checkbox glyph/image indicators and click handling.

`ttk.Treeview` also always places the hierarchy expand/collapse arrow in the
special tree column `#0`, which is the leftmost tree column. Keeping the arrow in
File Name means File Name must remain the first visible column. Moving Select to
the first visible column while keeping the arrow in File Name would require a
custom queue widget or a different UI framework.

## Illustrator-Dependent Behavior

Default import does not require Illustrator. PyMuPDF reads the PDF-compatible
content and the app falls back to deterministic numbered names such as
`Poster1`, `Poster2`, `Poster3`.

Real `.ai` artboard names require all of the following:

- Windows
- Adobe Illustrator installed and already running
- `pywin32`

The `Get Names` queue action runs Illustrator lookup in the background with a
timeout and does not cold-start Illustrator. If Illustrator is unavailable,
unresponsive, or blocked by its own missing-link/modal state, the app keeps the
numbered names and shows a user-facing warning.

## Diff Artifacts

Raster/vector alignment failures write a PPM diff image under:

```text
test_outputs/failures/
```

`test_outputs/` is intentionally ignored by Git.

Other local artifacts intentionally ignored by Git:

- `TEST.pdf`
- generated files under `logs/`
- generated PDF/image exports
