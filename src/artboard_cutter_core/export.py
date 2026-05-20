from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .layout import compute_panel_layout
from .logging_config import get_logger, log_event
from .pdf_io import open_pdf_robust
from .profiles import validate_output_name
from .raster_export import export_artboards_streaming_from_src
from .units import mm_to_pt, pt_to_mm
from .vector_export import export_artboards_vector_uniform


@dataclass(frozen=True)
class ExportOptions:
    bleed_mm: float
    widths_mm: list[float]
    height_mm: float
    overlap_mm: float
    dpi: int
    output_root: Path
    overlap_mode: str = "shared"
    export_fmt: str = "pdf"
    preserve_vectors: bool = False
    vector_fit_mode: str = "stretch"
    page_index: int = 0
    output_name: str | None = None


def process_file(file_path: Path, options: ExportOptions, log_cb=None) -> None:
    app_logger = get_logger("export", filename="export.log")
    vector_logger = get_logger("vector_export", filename="vector_mode.log")

    try:
        src = open_pdf_robust(file_path)
    except Exception as e:
        log_event(app_logger, 40, "source_open_failed", file=str(file_path), error=str(e))
        if log_cb:
            log_cb(f"[ERROR] {file_path}: {e}")
            log_cb("Tip: If this is a OneDrive file, right-click -> 'Always keep on this device'.")
        return

    try:
        bleed_eff = max(0.0, float(options.bleed_mm))
        panel_layout, target_w_mm, overlap_mm = compute_panel_layout(
            options.widths_mm,
            bleed_eff,
            options.overlap_mm,
            options.overlap_mode,
        )
        target_h_mm = options.height_mm + 2 * bleed_eff
        target_w_pt = mm_to_pt(target_w_mm)
        target_h_pt = mm_to_pt(target_h_mm)

        export_fmt = options.export_fmt
        if options.preserve_vectors and export_fmt.lower() != "pdf":
            export_fmt = "pdf"
            if log_cb:
                log_cb("[NOTE] Preserve vectors is ON -> forcing PDF output.")

        if log_cb:
            log_cb("")
            log_cb("=" * 60)
            log_cb(f"Input: {file_path}")
            log_cb(
                f"Bleed: {options.bleed_mm:.1f} mm   Overlap: {overlap_mm:.1f} mm   "
                f"Mode: {options.overlap_mode}   Height: {options.height_mm:.1f} mm   Artboards: {len(options.widths_mm)}"
            )
            log_cb(f"Widths: {', '.join(str(int(w)) if float(w).is_integer() else str(w) for w in options.widths_mm)} mm")
            if options.preserve_vectors and options.vector_fit_mode == "width":
                page = src.load_page(options.page_index)
                scale = (target_w_pt / float(page.rect.width)) if page.rect.width else 1.0
                calc_h_mm = pt_to_mm(scale * float(page.rect.height))
                log_cb(f"Target full size (vector/fit WIDTH): {pt_to_mm(target_w_pt):.1f} x {calc_h_mm:.1f} mm")
            else:
                log_cb(f"Target full size: {pt_to_mm(target_w_pt):.1f} x {pt_to_mm(target_h_pt):.1f} mm")
            vector_mode = "VECTOR (non-uniform stretch)" if options.vector_fit_mode == "stretch" else f"VECTOR (uniform, fit {options.vector_fit_mode})"
            mode = vector_mode if options.preserve_vectors else "RASTER (non-uniform)"
            log_cb(f"Mode: {mode}  Export as: {export_fmt.upper()}  Output dir: {options.output_root}")

        log_event(
            app_logger,
            20,
            "export_file_start",
            file=str(file_path),
            page_index=options.page_index,
            panels=len(panel_layout),
            target_size_mm=[target_w_mm, target_h_mm],
            preserve_vectors=options.preserve_vectors,
        )

        base_name = validate_output_name(options.output_name or file_path.stem)
        outdir = options.output_root
        outdir.mkdir(parents=True, exist_ok=True)

        if options.preserve_vectors:
            export_artboards_vector_uniform(
                src,
                options.widths_mm,
                options.height_mm,
                options.bleed_mm,
                options.overlap_mm,
                options.overlap_mode,
                base_name,
                outdir,
                fit_mode=options.vector_fit_mode,
                page_index=options.page_index,
                log_cb=log_cb,
                structured_logger=vector_logger,
            )
        else:
            export_artboards_streaming_from_src(
                src,
                options.widths_mm,
                options.height_mm,
                options.bleed_mm,
                options.overlap_mm,
                options.overlap_mode,
                base_name,
                outdir,
                options.dpi,
                export_fmt,
                log_cb,
                page_index=options.page_index,
                structured_logger=app_logger,
            )

        log_event(app_logger, 20, "export_file_done", file=str(file_path))
        if log_cb:
            log_cb(f"Done: {file_path.name}")
    finally:
        try:
            src.close()
        except Exception:
            pass
