# Vector Mode Investigation

Track findings related to vector-preserving PDF export here.

## 2026-05-19 - Initial vector-mode audit

Current vector export is implemented by `export_artboards_vector_uniform()` in `artboard_cutter_gui_advanced.py`.

Findings:

- Vector mode uses `page.rect` as the source coordinate space.
- Fit-by-height uses `scale = target_h_pt / src_rect.height`.
- Fit-by-width uses `scale = target_w_pt / src_rect.width` and derives output height from the source aspect ratio.
- Each panel computes target-space x positions from `compute_panel_layout()`, then maps them back to source space by dividing x coordinates by `scale`.
- The output page is created at the panel target size and `show_pdf_page(out_page.rect, src_doc, 0, clip=clip_src)` places the clipped source into the full page rectangle.

Likely risks:

- `show_pdf_page()` fits the clipped rectangle into `out_page.rect`; this can introduce subtle behavior differences from the raster path if the source clip aspect ratio and output page aspect ratio are not exactly equivalent after rounding.
- Source page boxes are not inspected or normalized before calculating `page.rect`; unusual CropBox/MediaBox/TrimBox/ArtBox configurations may shift or scale results.
- Rotation is not explicitly handled.
- Raster mode can use non-uniform scaling (`sx`, `sy`), while vector mode intentionally uses uniform scaling. Therefore vector output cannot match raster output in every mode unless the source aspect ratio matches the requested target aspect ratio, or raster behavior is explicitly switched to a vector-compatible uniform mode.
- Preview renders a resized raster background into the computed target rectangle, but it does not use the exact PyMuPDF crop/transformation pipeline. It is a geometry preview, not a full export-equivalent render preview.

Investigation priority:

1. Create deterministic geometry tests for `compute_panel_layout()`.
2. Create generated PDF fixtures with known page boxes and visible grid marks.
3. Export raster and vector panels from the same fixture.
4. Re-render both outputs to images and compare dimensions/visual alignment.
5. Log page boxes, source clips, target rects, and transformation assumptions.

## 2026-05-19 - Instrumented vector export extraction

- Vector export now lives in `src/artboard_cutter_core/vector_export.py`.
- It logs `vector_export_start` and `vector_compute_crop` events to `logs/vector_mode.log`.
- Logged data includes fit mode, scale factor, page box snapshot, crop rectangle in mm, source clip in points, and output page size in points.
- Behavior is intentionally preserved for this phase; the goal was to make the math observable before changing it.

## 2026-05-19 - TEST.pdf resize finding

Source `TEST.pdf` is about `7000 x 2450 mm`, aspect ratio about `2.857`.

Requested resize test:

- widths: `1200, 1200, 1100, 1230`
- total width: `4730 mm`
- target height: `2000 mm`
- target aspect ratio: about `2.365`

This target aspect does not match the source aspect. Raster mode can match the requested rectangle by non-uniform scaling:

- x scale: about `4730 / 7000 = 0.676`
- y scale: about `2000 / 2450 = 0.816`

Vector mode currently uses uniform scaling:

- fit height scale: about `0.816`, which would make the full source width about `5714 mm`; exporting only `4730 mm` worth of panels cannot include the full source width.
- fit width scale: about `0.676`, which makes the output height about `1655.5 mm`, not the requested `2000 mm`.

Conclusion: vector-preserving export cannot exactly match raster non-uniform resize unless the PDF content itself is transformed non-uniformly in vector space, or the product explicitly uses a uniform-fit vector mode with auto width/height. This is the central vector-mode design decision to resolve.

## 2026-05-19 - Vector stretch implementation

Implemented a new vector fit mode: `stretch`.

Mechanics:

- Compute independent vector scale factors:
  - `sx = target_total_width_pt / source_rect.width`
  - `sy = target_total_height_pt / source_rect.height`
- Compute each panel's source clip with the same X/Y mapping as raster mode.
- Call `show_pdf_page(..., keep_proportion=False)` so PyMuPDF places the clipped PDF page content into the output panel rectangle with non-uniform scaling.

This preserves PDF content as vector/Form XObject content where PyMuPDF supports it, while allowing the overall artwork to stretch to user-input width and height like raster mode.

The old uniform modes remain available as `height` and `width`.

## 2026-05-19 - Vector stretch master-page refinement

Updated `stretch` mode to follow the production mental model more directly:

1. Create an in-memory PDF master page at the full requested target size.
2. Place the whole source page onto that master with `keep_proportion=False`.
3. Clip each output panel from the already-stretched master page.

This avoids reasoning about each panel clip in original source coordinates during the final cut. The panel crop rectangles are now in the same target coordinate space used by preview and raster export. It should also be easier to debug because the logs can distinguish:

- `vector_stretch_master_created`
- `vector_stretch_panel_clip`

This still preserves vector content via PDF page/Form placement rather than rasterizing.

## 2026-05-19 - Current Vector Mode Summary

Final user-facing vector behavior:

- The app exposes `Vector` as an export mode.
- Vector output is always PDF.
- Vector output always stretches to the user-requested total width and height.
- The implementation creates a full-size stretched vector master page first, then clips panel outputs from that master.
- Batch export now reads vector/raster mode per queued `ArtworkProfile`, so one selected row no longer controls all checked rows.
- Multi-page imports now pass each profile's `source_page_index` into vector export, so vector mode no longer hardcodes page 0.

Why:

- Raster mode stretches artwork non-uniformly to match the requested production dimensions.
- The user's screenshot showed that uniform vector fit-by-height/fit-by-width did not match production expectations.
- The master-page stretch pipeline matches the mental model: resize the whole artwork, then dissect it.

Current implementation:

- `src/artboard_cutter_core/vector_export.py`
- `export_artboards_vector_uniform(... fit_mode="stretch")`
- `_export_artboards_vector_stretch_from_master()`
- `show_pdf_page(... keep_proportion=False)` for the full-size master placement.
- Panel outputs use `show_pdf_page(... keep_proportion=False)` from the stretched master clip.
- Vector export now also receives `overlap_mode` from each `ArtworkProfile`, so `Shared` and `Left` overlap geometry use the same layout source as raster export and preview.
- `export_mode` and `overlap_mode` are persisted as AppData defaults for future launches, while page/profile-specific values remain session-only.

Open investigation items:

- Confirm vector objects remain editable/selectable as expected in target production tools.
- Continue manual preview/export visual equivalence checks in a working GUI runtime.
- Confirm vector/raster alignment with customer artwork that includes linked raster assets and Illustrator-specific content.

Latest status:

- Automated raster/vector pixel alignment exists for generated fixture artwork.
- Rotated and unusual page box fixtures are covered by export geometry tests.
- Remaining vector validation is primarily production-artwork/manual review, especially files with missing Illustrator links or Illustrator-only document behavior.
