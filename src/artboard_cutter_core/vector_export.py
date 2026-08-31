from __future__ import annotations

import logging
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # type: ignore

from .errors import ExportCancelled
from .layout import compute_panel_layout
from .logging_config import log_event
from .output_io import StagedOutputSet, build_output_paths
from .pdf_io import force_page_boxes, page_box_snapshot
from .units import mm_to_pt, pt_to_mm
from .verification import verify_pdf_output


def _ocg_objects(doc) -> list[tuple[int, str]]:
    """Return optional-content group xrefs and names in stable PDF object order."""
    groups = []
    for xref in range(1, doc.xref_length()):
        try:
            if doc.xref_get_key(xref, "Type")[1] != "/OCG":
                continue
            name_type, name = doc.xref_get_key(xref, "Name")
        except Exception:
            continue
        groups.append((xref, name if name_type == "string" else ""))
    return groups


def _ocg_default_states(doc) -> list[tuple[str, bool]]:
    """Capture each source layer's initial visibility without changing the document."""
    groups = _ocg_objects(doc)
    if not groups:
        return []
    try:
        layer = doc.get_layer() or {}
    except Exception:
        layer = {}
    explicitly_on = set(layer.get("on", ()))
    explicitly_off = set(layer.get("off", ()))
    defaults = []
    for xref, name in groups:
        if xref in explicitly_off:
            visible = False
        elif xref in explicitly_on:
            visible = True
        else:
            # PDF viewers treat an OCG as visible when the default configuration
            # does not explicitly place it in /OFF.
            visible = True
        defaults.append((name, visible))
    return defaults


def _restore_ocg_default_states(output_doc, source_states: list[tuple[str, bool]]) -> None:
    """Rebuild /OCProperties after show_pdf_page imports Illustrator layers.

    PyMuPDF imports the OCG objects referenced by page content but not the source
    catalog's /OCProperties entry. Without that entry, PDF viewers show every
    imported group, including Illustrator layers that were hidden at export time.
    """
    output_groups = _ocg_objects(output_doc)
    if not output_groups or not source_states:
        return

    states_by_name: dict[str, list[bool]] = {}
    for name, visible in source_states:
        states_by_name.setdefault(name, []).append(visible)
    name_offsets: dict[str, int] = {}
    all_refs = []
    on_refs = []
    off_refs = []
    for xref, name in output_groups:
        all_refs.append(f"{xref} 0 R")
        occurrences = states_by_name.get(name, ())
        occurrence = name_offsets.get(name, 0)
        visible = occurrences[occurrence] if occurrence < len(occurrences) else True
        name_offsets[name] = occurrence + 1
        (on_refs if visible else off_refs).append(f"{xref} 0 R")

    output_doc.xref_set_key(
        output_doc.pdf_catalog(),
        "OCProperties",
        "<< "
        f"/OCGs [{' '.join(all_refs)}] "
        "/D << "
        f"/ON [{' '.join(on_refs)}] "
        f"/OFF [{' '.join(off_refs)}] "
        f"/Order [{' '.join(all_refs)}] "
        "/RBGroups [] "
        ">> >>",
    )


def _pdf_clip_varies(doc, page_index: int, clip) -> bool:
    page = doc.load_page(page_index)
    longest = max(1.0, float(clip.width), float(clip.height))
    scale = min(1.0, 128.0 / longest)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, colorspace=fitz.csRGB, alpha=False)
    value = getattr(pix, "is_unicolor", False)
    return not bool(value() if callable(value) else value)


def export_artboards_vector_uniform(
    src_doc,
    widths_mm,
    height_mm,
    bleed_mm,
    overlap_mm,
    overlap_mode,
    base_name,
    outdir: Path,
    fit_mode: str = "stretch",
    page_index: int = 0,
    log_cb=None,
    structured_logger: logging.Logger | None = None,
    overwrite: bool = False,
    cleanup_stale: bool = False,
    cancel_check=None,
    verify_outputs: bool = True,
):
    fit_mode = str(fit_mode or "stretch").strip().lower()
    if fit_mode not in {"stretch", "width", "height"}:
        raise ValueError(f"Unsupported PDF Preserve fit mode: {fit_mode}")
    working_doc = src_doc
    converted_doc = None
    if not getattr(src_doc, "is_pdf", True):
        converted_doc = fitz.open("pdf", src_doc.convert_to_pdf())
        working_doc = converted_doc

    try:
        page = working_doc.load_page(page_index)
        src_rect = page.rect
        source_ocg_states = _ocg_default_states(working_doc)

        bleed_eff = max(0.0, float(bleed_mm))
        panel_layout, target_w_mm, overlap_mm = compute_panel_layout(widths_mm, bleed_eff, overlap_mm, overlap_mode)
        target_h_mm = height_mm + 2 * bleed_eff
        target_w_pt = mm_to_pt(target_w_mm)
        target_h_pt_requested = mm_to_pt(target_h_mm)
        final_paths = build_output_paths(outdir, base_name, len(panel_layout), "pdf", preserve_vectors=True)

        if fit_mode == "stretch":
            sx = (target_w_pt / float(src_rect.width)) if src_rect.width else 1.0
            sy = (target_h_pt_requested / float(src_rect.height)) if src_rect.height else 1.0
            target_h_pt = target_h_pt_requested
            scale_log = [sx, sy]
        elif fit_mode == "width":
            scale = (target_w_pt / float(src_rect.width)) if src_rect.width else 1.0
            target_h_pt = scale * float(src_rect.height)
            sx = scale
            sy = scale
            scale_log = scale
        else:
            target_h_pt = target_h_pt_requested
            scale = (target_h_pt / float(src_rect.height)) if src_rect.height else 1.0
            sx = scale
            sy = scale
            scale_log = scale

        log_event(
            structured_logger,
            logging.INFO,
            "vector_export_start",
            base_name=base_name,
            fit_mode=fit_mode,
            overlap_mode=overlap_mode,
            source_is_pdf=bool(getattr(src_doc, "is_pdf", True)),
            target_width_mm=target_w_mm,
            target_height_mm=pt_to_mm(target_h_pt),
            scale_factor=scale_log,
            page_boxes=page_box_snapshot(page),
        )

        if fit_mode == "stretch":
            _export_artboards_vector_stretch_from_master(
                src_doc=working_doc,
                page_index=page_index,
                src_rect=src_rect,
                panel_layout=panel_layout,
                target_w_pt=target_w_pt,
                target_h_pt=target_h_pt,
                target_w_mm=target_w_mm,
                target_h_mm=target_h_mm,
                base_name=base_name,
                outdir=outdir,
                sx=sx,
                sy=sy,
                log_cb=log_cb,
                structured_logger=structured_logger,
                final_paths=final_paths,
                overwrite=overwrite,
                cleanup_stale=cleanup_stale,
                cancel_check=cancel_check,
                verify_outputs=verify_outputs,
                source_ocg_states=source_ocg_states,
            )
            return final_paths

        with StagedOutputSet(final_paths, overwrite=overwrite, cleanup_stale=cleanup_stale) as outputs:
            for idx, panel in enumerate(panel_layout):
                if cancel_check and cancel_check():
                    raise ExportCancelled("Export cancelled.")
                left_mm = panel.outer_left
                right_mm = panel.outer_right
                x0_t = mm_to_pt(left_mm)
                x1_t = mm_to_pt(right_mm)
                w_t = x1_t - x0_t
                h_t = target_h_pt

                clip_src = fitz.Rect(
                    src_rect.x0 + x0_t / sx,
                    src_rect.y0,
                    src_rect.x0 + x1_t / sx,
                    src_rect.y0 + target_h_pt / sy,
                )

                log_event(
                    structured_logger,
                    logging.INFO,
                    "vector_compute_crop",
                    panel=idx + 1,
                    crop_rect_mm=[left_mm, 0.0, right_mm, pt_to_mm(h_t)],
                    source_clip_pt=[clip_src.x0, clip_src.y0, clip_src.x1, clip_src.y1],
                    output_size_pt=[w_t, h_t],
                    scale_factor=scale_log,
                )

                out = fitz.open()
                try:
                    out_page = out.new_page(width=w_t, height=h_t)
                    force_page_boxes(out_page)
                    out_page.show_pdf_page(out_page.rect, working_doc, page_index, clip=clip_src, keep_proportion=True)
                    _restore_ocg_default_states(out, source_ocg_states)
                    out_name = final_paths[idx].name
                    out.save(outputs.stage_paths[idx])
                finally:
                    out.close()

                if verify_outputs:
                    result = verify_pdf_output(outputs.stage_paths[idx], expected_size_pt=(w_t, h_t))
                    if _pdf_clip_varies(working_doc, page_index, clip_src) and result.uniform:
                        raise RuntimeError(
                            f"Output verification failed for {out_name}: output is blank/uniform but source contains artwork."
                        )
                    if log_cb:
                        log_cb(f"[VERIFY] {result.summary}")

                if log_cb:
                    log_cb(
                        f"[CROP] {out_name} (PDF PRESERVE {fit_mode.upper()}): x=[{pt_to_mm(x0_t):.3f},{pt_to_mm(x1_t):.3f}] mm  "
                        f"w={pt_to_mm(w_t):.3f} mm  h={pt_to_mm(h_t):.3f} mm  scale={sx:.6f}"
                    )
            if cancel_check and cancel_check():
                raise ExportCancelled("Export cancelled.")
            outputs.commit()
        return final_paths
    finally:
        if converted_doc is not None:
            converted_doc.close()


def _export_artboards_vector_stretch_from_master(
    src_doc,
    page_index: int,
    src_rect,
    panel_layout,
    target_w_pt: float,
    target_h_pt: float,
    target_w_mm: float,
    target_h_mm: float,
    base_name: str,
    outdir: Path,
    sx: float,
    sy: float,
    log_cb=None,
    structured_logger: logging.Logger | None = None,
    final_paths: list[Path] | None = None,
    overwrite: bool = False,
    cleanup_stale: bool = False,
    cancel_check=None,
    verify_outputs: bool = True,
    source_ocg_states: list[tuple[str, bool]] | None = None,
) -> None:
    """
    Vector stretch pipeline:
    1. Place the whole source page onto a full-size target master page with
       keep_proportion=False, applying the global X/Y stretch once.
    2. Clip each panel from that stretched master coordinate space.

    This mirrors the raster mental model: resize the whole artwork first, then
    dissect it into artboards.
    """
    final_paths = final_paths or build_output_paths(outdir, base_name, len(panel_layout), "pdf", preserve_vectors=True)
    master = fitz.open()
    try:
        master_page = master.new_page(width=target_w_pt, height=target_h_pt)
        force_page_boxes(master_page)
        master_page.show_pdf_page(master_page.rect, src_doc, page_index, clip=src_rect, keep_proportion=False)

        log_event(
            structured_logger,
            logging.INFO,
            "vector_stretch_master_created",
            target_size_mm=[target_w_mm, target_h_mm],
            target_size_pt=[target_w_pt, target_h_pt],
            scale_factor=[sx, sy],
            source_clip_pt=[src_rect.x0, src_rect.y0, src_rect.x1, src_rect.y1],
        )

        with StagedOutputSet(final_paths, overwrite=overwrite, cleanup_stale=cleanup_stale) as outputs:
            for idx, panel in enumerate(panel_layout):
                if cancel_check and cancel_check():
                    raise ExportCancelled("Export cancelled.")
                left_mm = panel.outer_left
                right_mm = panel.outer_right
                x0_t = mm_to_pt(left_mm)
                x1_t = mm_to_pt(right_mm)
                w_t = x1_t - x0_t
                h_t = target_h_pt
                master_clip = fitz.Rect(x0_t, 0.0, x1_t, target_h_pt)

                log_event(
                    structured_logger,
                    logging.INFO,
                    "vector_stretch_panel_clip",
                    panel=idx + 1,
                    crop_rect_mm=[left_mm, 0.0, right_mm, target_h_mm],
                    master_clip_pt=[master_clip.x0, master_clip.y0, master_clip.x1, master_clip.y1],
                    output_size_pt=[w_t, h_t],
                    scale_factor=[sx, sy],
                )

                out = fitz.open()
                try:
                    out_page = out.new_page(width=w_t, height=h_t)
                    force_page_boxes(out_page)
                    out_page.show_pdf_page(out_page.rect, master, 0, clip=master_clip, keep_proportion=False)
                    _restore_ocg_default_states(out, source_ocg_states or [])
                    out_name = final_paths[idx].name
                    out.save(outputs.stage_paths[idx])
                finally:
                    out.close()

                if verify_outputs:
                    result = verify_pdf_output(outputs.stage_paths[idx], expected_size_pt=(w_t, h_t))
                    if _pdf_clip_varies(master, 0, master_clip) and result.uniform:
                        raise RuntimeError(
                            f"Output verification failed for {out_name}: output is blank/uniform but source contains artwork."
                        )
                    if log_cb:
                        log_cb(f"[VERIFY] {result.summary}")

                if log_cb:
                    log_cb(
                        f"[CROP] {out_name} (PDF PRESERVE STRETCH): x=[{pt_to_mm(x0_t):.3f},{pt_to_mm(x1_t):.3f}] mm  "
                        f"w={pt_to_mm(w_t):.3f} mm  h={pt_to_mm(h_t):.3f} mm  sx={sx:.6f} sy={sy:.6f}"
                    )
            if cancel_check and cancel_check():
                raise ExportCancelled("Export cancelled.")
            outputs.commit()
    finally:
        master.close()
