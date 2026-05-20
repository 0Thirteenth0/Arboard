from __future__ import annotations

import logging
from pathlib import Path

import fitz

from .layout import compute_panel_layout
from .logging_config import log_event
from .pdf_io import force_page_boxes
from .raster_images import PIL_AVAILABLE, Image, pixmap_to_pil, save_raster_pil
from .units import compute_scale_matrix, estimate_pixels, mm_to_pt, pt_to_mm

MAX_MP = 150


def export_artboards_streaming_from_src(
    src_doc,
    widths_mm,
    height_mm,
    bleed_mm,
    overlap_mm,
    overlap_mode,
    base_name,
    outdir: Path,
    dpi: int,
    export_fmt: str = "pdf",
    log_cb=None,
    page_index: int = 0,
    structured_logger: logging.Logger | None = None,
):
    page = src_doc.load_page(page_index)
    src_rect = page.rect

    bleed_eff = max(0.0, float(bleed_mm))
    panel_layout, target_w_mm, overlap_mm = compute_panel_layout(widths_mm, bleed_eff, overlap_mm, overlap_mode)
    target_h_mm = height_mm + 2 * bleed_eff
    target_w_pt = mm_to_pt(target_w_mm)
    target_h_pt = mm_to_pt(target_h_mm)

    sx, sy = compute_scale_matrix(src_rect, target_w_pt, target_h_pt)
    matrix = fitz.Matrix(sx, sy)
    clip_h_pt = mm_to_pt(target_h_mm)

    log_event(
        structured_logger,
        logging.INFO,
        "raster_export_start",
        base_name=base_name,
        target_size_mm=[target_w_mm, target_h_mm],
        overlap_mode=overlap_mode,
        scale=[sx, sy],
        dpi=dpi,
    )

    for idx, panel in enumerate(panel_layout):
        left_mm = panel.outer_left
        right_mm = panel.outer_right
        x0_t = mm_to_pt(left_mm)
        x1_t = mm_to_pt(right_mm)
        w_t = x1_t - x0_t
        h_t = clip_h_pt

        x0_s = x0_t / sx
        x1_s = x1_t / sx
        clip_src = fitz.Rect(x0_s, 0.0 / sy, x1_s, clip_h_pt / sy)

        total_pixels = estimate_pixels(w_t, h_t, dpi)
        eff_dpi = dpi
        if total_pixels > MAX_MP * 1e6:
            scale = (MAX_MP * 1e6 / total_pixels) ** 0.5
            eff_dpi = max(72, int(dpi * scale))
            if log_cb:
                log_cb(f"[SAFE] {base_name}_{idx+1}: requested ~{total_pixels / 1e6:.1f} MP @ {dpi} dpi; using {eff_dpi} dpi")

        log_event(
            structured_logger,
            logging.INFO,
            "raster_compute_crop",
            panel=idx + 1,
            crop_rect_mm=[left_mm, 0.0, right_mm, target_h_mm],
            source_clip_pt=[clip_src.x0, clip_src.y0, clip_src.x1, clip_src.y1],
            output_size_pt=[w_t, h_t],
            dpi=eff_dpi,
        )

        pix = page.get_pixmap(matrix=matrix, clip=clip_src, dpi=eff_dpi, alpha=False)

        target_w_px = max(1, int(round((w_t / 72.0) * eff_dpi)))
        target_h_px = max(1, int(round((h_t / 72.0) * eff_dpi)))

        pil_im = None
        if PIL_AVAILABLE:
            pil_im = pixmap_to_pil(pix)
            if pil_im.size != (target_w_px, target_h_px):
                pil_im = pil_im.resize((target_w_px, target_h_px), resample=Image.BICUBIC)

        export_fmt_lc = (export_fmt or "pdf").lower()
        if export_fmt_lc == "pdf":
            out = fitz.open()
            out_page = out.new_page(width=w_t, height=h_t)
            force_page_boxes(out_page)
            out_page.insert_image(out_page.rect, pixmap=pix, keep_proportion=False)
            out_name = f"{base_name}_{idx+1}.pdf"
            out.save(outdir / out_name)
            out.close()
        else:
            ext = "jpg" if export_fmt_lc in ("jpg", "jpeg") else ("tif" if export_fmt_lc in ("tif", "tiff") else export_fmt_lc)
            out_name = f"{base_name}_{idx+1}.{ext}"
            out_path = outdir / out_name

            if pil_im is None:
                pix.save(str(out_path))
            elif export_fmt_lc in ("tif", "tiff"):
                trial_dpi = eff_dpi
                while True:
                    try:
                        save_raster_pil(pil_im, out_path, export_fmt_lc, trial_dpi, log_cb)
                        break
                    except Exception as e:
                        if log_cb:
                            log_cb(f"[TIFF] save failed @ {trial_dpi} dpi: {e}")
                        next_dpi = int(trial_dpi * 0.85)
                        if next_dpi < 100 or next_dpi == trial_dpi:
                            raise
                        trial_dpi = next_dpi
                if log_cb and trial_dpi != eff_dpi:
                    log_cb(f"[TIFF] succeeded after DPI fallback: {trial_dpi} dpi")
            else:
                save_raster_pil(pil_im, out_path, export_fmt_lc, eff_dpi, log_cb)

        if log_cb:
            log_cb(
                f"[CROP] {out_name}: x=[{pt_to_mm(x0_t):.3f},{pt_to_mm(x1_t):.3f}] mm  "
                f"w={pt_to_mm(w_t):.3f} mm  h={pt_to_mm(h_t):.3f} mm  dpi={eff_dpi}"
            )
